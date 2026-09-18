"""RVC 后处理:模型列表、从训练 checkpoint 导出、建索引(job)、对生成结果做音色转换。"""
from __future__ import annotations

import os

import soundfile as sf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..core import jobs as jobmgr, library, paths, rvc

router = APIRouter(prefix="/rvc", tags=["rvc"])


@router.get("/models")
def models():
    return rvc.list_models()


class ExportBody(BaseModel):
    exp: str
    ckpt: str
    name: str
    info: str = ""


@router.post("/export")
async def export(b: ExportBody):
    if not b.name or "/" in b.name or "\\" in b.name:
        raise HTTPException(400, "bad name")
    try:
        file = await run_in_threadpool(rvc.export_small, b.exp, b.ckpt, b.name, b.info)
    except FileNotFoundError as e:
        raise HTTPException(404, f"checkpoint not found: {e}") from e
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e
    return {"file": file}


@router.post("/index")
def build_index(exp: str):
    kind = "rvc:index"
    if jobmgr.running_of_kind(kind):
        raise HTTPException(409, "already running")
    cmd, env, cwd = rvc.index_cmd(exp)
    return jobmgr.launch(kind, f"RVC 索引 {exp}", cmd, cwd, env, meta={"exp": exp}).public()


class ConvertBody(BaseModel):
    generation_id: int | None = None
    path: str | None = None
    model: str
    pitch: int = 0
    f0_method: str = "rmvpe"
    index_rate: float = 0.5
    protect: float = 0.33
    rms_mix_rate: float = 1.0


@router.post("/convert")
async def convert(b: ConvertBody):
    src_item = library.get(b.generation_id) if b.generation_id is not None else None
    if b.generation_id is not None and not src_item:
        raise HTTPException(404, "generation not found")
    src = paths.resolve(src_item["wav"] if src_item else (b.path or ""))
    if not os.path.isfile(src):
        raise HTTPException(404, "source audio not found")
    if not os.path.isfile(os.path.join(rvc.WEIGHTS, b.model)):
        raise HTTPException(404, f"rvc model not found: {b.model}")
    if jobmgr.running_of_kind("train:s2") or jobmgr.running_of_kind("train:s1"):
        raise HTTPException(409, "training is running; RVC would OOM")
    base = os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(paths.GENERATED_DIR, f"{base}_rvc.wav")
    try:
        elapsed = await run_in_threadpool(rvc.convert, b.model, src, dst, b.pitch, b.f0_method, b.index_rate, b.protect, b.rms_mix_rate)
    except RuntimeError as e:
        raise HTTPException(500, f"rvc failed: {e}") from e
    info = sf.info(dst)
    item = library.add(
        character=src_item["character"] if src_item else "unknown",
        text=src_item["text"] if src_item else base,
        ref_audio=src_item["ref_audio"] if src_item else None,
        prompt_text=src_item["prompt_text"] if src_item else None,
        gpt=src_item["gpt"] if src_item else None,
        sovits=src_item["sovits"] if src_item else None,
        params={**(src_item["params"] if src_item else {}), "rvc": b.model_dump(exclude={"generation_id", "path"}), "source_id": b.generation_id},
        wav=paths.rel_to_root(dst),
        duration=info.duration,
        seed=src_item["seed"] if src_item else -1,
        elapsed=elapsed,
        tags=["rvc"],
    )
    return item
