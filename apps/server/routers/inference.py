import os
import shutil
import soundfile as sf
import time
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ..core import characters, library, paths, tts_engine

router = APIRouter(tags=["inference"])


class TtsRequest(BaseModel):
    character: str | None = None
    text: str
    text_lang: str = "zh"
    ref_audio_path: str
    prompt_text: str = ""
    prompt_lang: str = "zh"
    aux_ref_audio_paths: list[str] = Field(default_factory=list)
    top_k: int = 15
    top_p: float = 1.0
    temperature: float = 1.0
    text_split_method: str = "cut5"
    batch_size: int = 1
    batch_threshold: float = 0.75
    split_bucket: bool = True
    speed_factor: float = 1.0
    fragment_interval: float = 0.3
    seed: int = -1
    parallel_infer: bool = True
    repetition_penalty: float = 1.35
    sample_steps: int = 32
    super_sampling: bool = False
    save: bool = True


class LoadRequest(BaseModel):
    gpt: str
    sovits: str
    version: str = "v2"
    character: str | None = None


@router.get("/models")
def list_models():
    return {"weights": tts_engine.list_weights(), "engine": tts_engine.get().describe()}


@router.post("/models/load")
async def load_models(body: LoadRequest):
    eng = tts_engine.get()
    try:
        return await run_in_threadpool(eng.load, body.gpt, body.sovits, body.version, body.character)
    except FileNotFoundError as e:
        raise HTTPException(404, f"weight not found: {e}") from e


@router.post("/models/unload")
def unload_models():
    return tts_engine.get().unload()


@router.post("/tts")
async def tts(body: TtsRequest):
    eng = tts_engine.get()
    char = characters.get(body.character) if body.character else None
    if eng.tts is None:
        if not char:
            raise HTTPException(409, "engine not loaded; pass character or POST /models/load first")
        await run_in_threadpool(eng.ensure_loaded, char)
    if eng.busy:
        raise HTTPException(409, "engine busy")
    if not body.text.strip():
        raise HTTPException(400, "text is empty")
    ref = paths.resolve(body.ref_audio_path)
    if not os.path.isfile(ref):
        raise HTTPException(404, f"ref audio not found: {body.ref_audio_path}")
    ref_dur = sf.info(ref).duration
    if not 3 <= ref_dur <= 10:
        raise HTTPException(400, f"参考音频 {ref_dur:.1f} 秒,GPT-SoVITS 要求 3–10 秒;请换一条(数据集挑选器里置灰的都不能用)或用「长音频切分」")

    params = body.model_dump(exclude={"character", "save"})
    try:
        wav, sr, dur, elapsed = await run_in_threadpool(eng.synthesize, params)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"synthesis failed: {e}") from e

    item = None
    if body.save:
        cid = char["id"] if char else (eng.character_id or "unknown")
        fn = f"{cid}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.wav"
        out = os.path.join(paths.GENERATED_DIR, fn)
        with open(out, "wb") as f:
            f.write(wav)
        item = library.add(
            character=cid,
            text=body.text,
            ref_audio=body.ref_audio_path,
            prompt_text=body.prompt_text,
            gpt=eng.gpt,
            sovits=eng.sovits,
            params={k: v for k, v in params.items() if k not in ("text", "ref_audio_path", "prompt_text")},
            wav=paths.rel_to_root(out),
            duration=dur,
            seed=body.seed,
            elapsed=elapsed,
        )
    headers = {
        "X-Sample-Rate": str(sr),
        "X-Duration": f"{dur:.3f}",
        "X-Elapsed": f"{elapsed:.3f}",
    }
    if item:
        headers["X-Library-Id"] = str(item["id"])
        headers["X-Wav-Path"] = item["wav"]
    return Response(content=wav, media_type="audio/wav", headers=headers)


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower() or ".wav"
    fn = f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
    out = os.path.join(paths.UPLOADS_DIR, fn)
    with open(out, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": paths.rel_to_root(out), "name": file.filename}


class AsrRequest(BaseModel):
    path: str
    lang: str = "zh"


@router.post("/asr")
async def asr(body: AsrRequest):
    p = paths.resolve(body.path)
    if not os.path.isfile(p):
        raise HTTPException(404, "audio not found")
    text = await run_in_threadpool(tts_engine.asr, p, body.lang)
    if not text:
        raise HTTPException(422, "ASR returned empty text")
    return {"text": text}


class SliceRequest(BaseModel):
    path: str
    max_dur: float = 10.0
    min_dur: float = 1.0
    asr: bool = True


@router.post("/ref/slice")
async def ref_slice(body: SliceRequest):
    p = paths.resolve(body.path)
    if not os.path.isfile(p):
        raise HTTPException(404, "audio not found")
    rows = await run_in_threadpool(tts_engine.slice_reference, p, body.max_dur, body.min_dur, body.asr)
    if not rows:
        raise HTTPException(422, "no valid segments")
    return {"segments": rows}


@router.get("/ref/samples/{cid}")
def ref_samples(cid: str, limit: int = 60):
    """从角色训练集里列可作参考的样本(带文本)。"""
    char = characters.get(cid)
    if not char:
        raise HTTPException(404)
    lst = paths.resolve(char["dataset"]["list"])
    out = []
    if os.path.isfile(lst):
        with open(lst, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("|")
                if len(parts) < 4:
                    continue
                wav = parts[0]
                if not os.path.isfile(wav):
                    continue
                out.append({"path": paths.rel_to_root(wav), "file": os.path.basename(wav), "text": "|".join(parts[3:]), "duration": round(sf.info(wav).duration, 2)})
    return out[:limit]
