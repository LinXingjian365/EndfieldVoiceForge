"""提弗洛斯 AI 对话：/chat（文本，RAG + LLM）与 /chat/tts（提弗洛斯语音回复）。"""
from __future__ import annotations

import json
import os
import time

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


def _history_path(character: str) -> str:
    return os.path.join(_HISTORY_DIR, f"{character}.json")


class HistoryBody(BaseModel):
    character: str = "typhoea"
    messages: list[dict] = Field(default_factory=list)


@router.get("/history")
def get_history(character: str = "typhoea"):
    p = _history_path(character)
    if not os.path.isfile(p):
        return {"messages": []}
    try:
        with open(p, encoding="utf-8") as f:
            return {"messages": json.load(f)}
    except (OSError, ValueError):
        return {"messages": []}


@router.post("/history")
def save_history(body: HistoryBody):
    os.makedirs(_HISTORY_DIR, exist_ok=True)
    # 只保留 role/content/sources，剔除 audioUrl(blob)/streaming 等瞬态字段
    msgs = []
    for m in body.messages:
        clean = {"role": m.get("role"), "content": m.get("content", "")}
        if m.get("sources"):
            clean["sources"] = m["sources"]
        msgs.append(clean)
    with open(_history_path(body.character), "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False)
    return {"ok": True, "count": len(msgs)}


@router.delete("/history")
def clear_history(character: str = "typhoea"):
    p = _history_path(character)
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
