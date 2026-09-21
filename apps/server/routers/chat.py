"""提弗洛斯 AI 对话：/chat（文本，RAG + LLM）与 /chat/tts（提弗洛斯语音回复）。"""
from __future__ import annotations

import json
import os
import time
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ..core import characters, jobs as jobmgr, llm, log, paths, persona, rag, tts_engine

router = APIRouter(prefix="/chat", tags=["chat"])

TRAIN_KINDS = ("train:s2", "train:s1", "rvc:train")


def _training_running() -> bool:
    return any(jobmgr.running_of_kind(k) for k in TRAIN_KINDS)


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = Field(default_factory=list)
    character: str = "typhoea"
    top_k: int = 5


class ChatTtsRequest(BaseModel):
    text: str
    character: str = "typhoea"


_HISTORY_DIR = os.path.join(paths.OUTPUTS_DIR, "chat_history")


def _sess_dir(character: str) -> str:
    d = os.path.join(_HISTORY_DIR, character)
    os.makedirs(d, exist_ok=True)
    return d


def _sess_path(character: str, sid: str) -> str:
    if not sid.isalnum():
        raise HTTPException(400, "bad session id")
    return os.path.join(_sess_dir(character), f"{sid}.json")


def _clean_messages(messages: list[dict]) -> list[dict]:
    # 只保留 role/content/sources，剔除 audioUrl(blob)/streaming 等瞬态字段
    out = []
    for m in messages:
        clean = {"role": m.get("role"), "content": m.get("content", "")}
        if m.get("sources"):
            clean["sources"] = m["sources"]
        out.append(clean)
    return out


def _auto_title(messages: list[dict]) -> str:
    first = next((m["content"] for m in messages if m.get("role") == "user" and m.get("content")), "")
    return " ".join(first.split())[:24] or "新对话"


def _write_session(character: str, sess: dict) -> None:
    with open(_sess_path(character, sess["id"]), "w", encoding="utf-8") as f:
        json.dump(sess, f, ensure_ascii=False)


def _read_session(character: str, sid: str) -> dict | None:
    p = _sess_path(character, sid)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _migrate_legacy(character: str) -> None:
    """旧版单文件 chat_history/<character>.json → 一个会话。"""
    legacy = os.path.join(_HISTORY_DIR, f"{character}.json")
    if not os.path.isfile(legacy):
        return
    try:
        with open(legacy, encoding="utf-8") as f:
            msgs = json.load(f)
    except (OSError, ValueError):
        msgs = []
    if msgs:
        now = time.time()
        _write_session(character, {"id": uuid.uuid4().hex[:12], "title": _auto_title(msgs), "created": now, "updated": now, "messages": msgs})
    os.remove(legacy)


class SessionCreate(BaseModel):
    character: str = "typhoea"
    title: str = ""


class SessionSave(BaseModel):
    character: str = "typhoea"
    messages: list[dict] = Field(default_factory=list)
    title: str | None = None


@router.get("/sessions")
def list_sessions(character: str = "typhoea"):
    _migrate_legacy(character)
    rows = []
    for fn in os.listdir(_sess_dir(character)):
        if not fn.endswith(".json"):
            continue
        sess = _read_session(character, fn[:-5])
        if sess:
            rows.append({"id": sess["id"], "title": sess.get("title") or "新对话", "updated": sess.get("updated", 0), "count": len(sess.get("messages", []))})
    rows.sort(key=lambda r: r["updated"], reverse=True)
    return {"sessions": rows}


@router.post("/sessions")
def create_session(body: SessionCreate):
    now = time.time()
    sess = {"id": uuid.uuid4().hex[:12], "title": body.title.strip() or "新对话", "created": now, "updated": now, "messages": []}
    _write_session(body.character, sess)
    return sess


@router.get("/sessions/{sid}")
def get_session(sid: str, character: str = "typhoea"):
    sess = _read_session(character, sid)
    if not sess:
        raise HTTPException(404, "session not found")
    return sess


@router.put("/sessions/{sid}")
def save_session(sid: str, body: SessionSave):
    sess = _read_session(body.character, sid)
    if not sess:
        raise HTTPException(404, "session not found")
    sess["messages"] = _clean_messages(body.messages)
    if body.title is not None:
        sess["title"] = body.title.strip() or "新对话"
    elif sess.get("title") in ("", "新对话"):
        sess["title"] = _auto_title(sess["messages"])
    sess["updated"] = time.time()
    _write_session(body.character, sess)
    return {"ok": True, "title": sess["title"], "count": len(sess["messages"])}


@router.delete("/sessions/{sid}")
def delete_session(sid: str, character: str = "typhoea"):
    p = _sess_path(character, sid)
    if os.path.isfile(p):
        os.remove(p)
    return {"ok": True}


@router.get("/status")
def chat_status():
    return {
        "llm": llm.llm_enabled(),
        "embed": llm.embed_enabled(),
        "llm_model": paths.LLM_MODEL,
        "embed_model": paths.EMBED_MODEL,
        "rag_chunks": rag.count(),
        "rag_ready": rag.ready(),
    }


@router.post("/reload")
def reload_rag():
    """重新加载资料库（ingest_lore.py 之后无需重启 server 即可生效）。"""
    rag.reload()
    return {"rag_chunks": rag.count(), "rag_ready": rag.ready()}


@router.post("")
async def chat(body: ChatRequest):
    char = characters.get(body.character) or characters.get("typhoea")
    if not char:
        raise HTTPException(404, f"character {body.character} not found")
    if not body.message.strip():
        raise HTTPException(400, "message is empty")
    t0 = time.time()

    # 1) RAG：向量化问题 -> 检索相关资料
    context: list[dict] = []
    if rag.ready() and llm.embed_enabled():
        try:
            qvec = await run_in_threadpool(llm.embed_query, body.message)
            context = await run_in_threadpool(rag.search, qvec, body.top_k)
        except llm.LlmError as e:
            log.warn("RAG 检索失败（降级为无上下文）", error=str(e))
            context = []

    # 2) 生成回复
    if llm.llm_enabled():
        messages = [{"role": "system", "content": persona.build_system_prompt(context)}]
        messages.extend({"role": m.get("role", "user"), "content": m.get("content", "")} for m in body.history)
        messages.append({"role": "user", "content": body.message})
        try:
            reply = await run_in_threadpool(llm.chat, messages)
        except llm.LlmError as e:
            log.error("LLM 调用失败", model=paths.LLM_MODEL, base_url=paths.LLM_BASE_URL, error=str(e))
            raise HTTPException(502, f"LLM 调用失败: {e}") from e
        mode = "llm"
    else:
        # 检索模式：未配置 LLM 时，直接回最相关的资料片段，方便先验证 RAG 效果
        if context:
            reply = "（未配置云端 LLM，以下为检索到的最相关资料）\n" + "\n".join(f"· {c['text'][:240]}" for c in context[:3])
        else:
            reply = "尚未配置云端 LLM，也没有可检索的资料。请设置 ENDFIELD_LLM_API_KEY 后重启 server，并运行 scripts/ingest_lore.py 入库。"
        mode = "retrieval"

    log.info("对话完成", model=paths.LLM_MODEL, mode=mode, sources=len(context), chars=len(reply), elapsed_ms=int((time.time() - t0) * 1000))
    return {"reply": reply, "sources": context, "mode": mode}


@router.post("/stream")
def chat_stream(body: ChatRequest):
    """流式对话：SSE 逐段返回。事件：{type:'meta',sources} → {type:'delta',text}... → [DONE]。"""
    char = characters.get(body.character) or characters.get("typhoea")
    if not char:
        raise HTTPException(404, f"character {body.character} not found")
    if not body.message.strip():
        raise HTTPException(400, "message is empty")
    t0 = time.time()

    def gen():
        # 1) RAG 检索
        context: list[dict] = []
        if rag.ready() and llm.embed_enabled():
            try:
                qvec = llm.embed_query(body.message)
                context = rag.search(qvec, body.top_k)
            except llm.LlmError as e:
                log.warn("RAG 检索失败（降级为无上下文）", error=str(e))
                context = []
        yield f"data: {json.dumps({'type': 'meta', 'sources': context, 'mode': 'llm' if llm.llm_enabled() else 'retrieval'}, ensure_ascii=False)}\n\n"

        # 2) 生成回复（流式）
        if llm.llm_enabled():
            messages = [{"role": "system", "content": persona.build_system_prompt(context)}]
            messages.extend({"role": m.get("role", "user"), "content": m.get("content", "")} for m in body.history)
            messages.append({"role": "user", "content": body.message})
            try:
                for delta in llm.chat_stream(messages):
                    yield f"data: {json.dumps({'type': 'delta', 'text': delta}, ensure_ascii=False)}\n\n"
            except llm.LlmError as e:
                log.error("LLM 流式调用失败", model=paths.LLM_MODEL, error=str(e))
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
        else:
            reply = ("（未配置云端 LLM，以下为检索到的最相关资料）\n" + "\n".join(f"· {c['text'][:240]}" for c in context[:3])) if context else "尚未配置云端 LLM，也没有可检索的资料。"
            yield f"data: {json.dumps({'type': 'delta', 'text': reply}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        log.info("对话完成(流式)", model=paths.LLM_MODEL, sources=len(context), elapsed_ms=int((time.time() - t0) * 1000))

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/tts")
async def chat_tts(body: ChatTtsRequest):
    """把一句话合成提弗洛斯语音（复用角色的 defaultRef）。"""
    char = characters.get(body.character) or characters.get("typhoea")
    if not char:
        raise HTTPException(404, f"character {body.character} not found")
    if not body.text.strip():
        raise HTTPException(400, "text is empty")

    eng = tts_engine.get()
    want = "cpu" if _training_running() else "cuda:0"
    if eng.device != want:
        eng.set_device(want)
    if eng.tts is None:
        await run_in_threadpool(eng.ensure_loaded, char)
    if eng.busy:
        raise HTTPException(409, "engine busy")

    ref = char["defaultRef"]
    params = {
        "text": body.text,
        "text_lang": "zh",
        "ref_audio_path": ref["audio"],
        "prompt_text": ref.get("text", ""),
        "prompt_lang": ref.get("lang", "zh"),
        "aux_ref_audio_paths": [],
        "top_k": 15,
        "top_p": 1.0,
        "temperature": 1.0,
        "text_split_method": "cut5",
        "batch_size": 1,
        "batch_threshold": 0.75,
        "split_bucket": True,
        "speed_factor": 1.0,
        "fragment_interval": 0.3,
        "seed": -1,
        "parallel_infer": True,
        "repetition_penalty": 1.35,
        "sample_steps": 32,
        "super_sampling": False,
    }
    try:
        wav, sr, dur, elapsed = await run_in_threadpool(eng.synthesize, params)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"synthesis failed: {e}") from e

    headers = {"X-Sample-Rate": str(sr), "X-Duration": f"{dur:.3f}", "X-Elapsed": f"{elapsed:.3f}"}
    return Response(content=wav, media_type="audio/wav", headers=headers)
