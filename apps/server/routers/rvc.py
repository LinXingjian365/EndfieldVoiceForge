"""RVC 后处理:模型列表、从训练 checkpoint 导出、建索引(job)、对生成结果做音色转换。"""
from __future__ import annotations

import os
import time
import uuid

import soundfile as sf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..core import jobs as jobmgr, library, paths, rvc, tfevents, tts_engine
from .training import RVC_MIN_FREE_RAM_GB, _guard_training

router = APIRouter(prefix="/rvc", tags=["rvc"])


@router.get("/models")
def models():
    return rvc.list_models()


@router.get("/{exp}/status")
def status(exp: str):
    running = {j.kind: j.id for j in jobmgr.all_jobs() if j.status == "running" and j.kind.startswith("rvc:") and j.meta.get("exp") == exp}
    return {"exp": exp, "epoch": rvc.latest_epoch(exp), "running": running}


@router.get("/{exp}/curves")
def curves(exp: str):
    return tfevents.rvc_curves(exp)


class TrainBody(BaseModel):
    exp: str
    total_epoch: int = 100
    save_every: int = 10
    batch_size: int = 1
    keep_all: bool = False


@router.post("/train")
def train(b: TrainBody):
    if jobmgr.running_of_kind("rvc:train"):
        raise HTTPException(409, "rvc training already running")
    _guard_training(True, RVC_MIN_FREE_RAM_GB)
    cmd, env, cwd = rvc.train_cmd(b.exp, b.total_epoch, b.save_every, b.batch_size, b.keep_all)
    return jobmgr.launch("rvc:train", f"RVC 训练 {b.exp} → e{b.total_epoch}", cmd, cwd, env, meta={"exp": b.exp, "epochs": b.total_epoch}).public()


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


class RepreprocessBody(BaseModel):
    exp: str = "typhoea"
    n_p: int = 4


@router.post("/repreprocess")
def repreprocess(b: RepreprocessBody):
    kind = "rvc:preprocess"
    if jobmgr.running_of_kind(kind):
        raise HTTPException(409, "already running")
    if jobmgr.running_of_kind("rvc:train"):
        raise HTTPException(409, "rvc training is running")
    trainset = os.path.join(paths.DATASETS_DIR, "typhoea_train")
    cmd, env, cwd = rvc.repreprocess_cmd(b.exp, trainset, b.n_p)
    return jobmgr.launch(kind, f"RVC 重新预处理 {b.exp}", cmd, cwd, env, meta={"exp": b.exp}).public()


class ConvertBody(BaseModel):
    generation_id: int | None = None
    path: str | None = None
    model: str
    pitch: int = 0
    f0_method: str = "rmvpe"
    index_rate: float = 0.75
    protect: float = 0.33
    rms_mix_rate: float = 1.0


@router.post("/convert")
def convert(b: ConvertBody):
    if jobmgr.running_of_kind("rvc:convert"):
        raise HTTPException(409, "rvc convert already running")
    src_item = library.get(b.generation_id) if b.generation_id is not None else None
    if b.generation_id is not None and not src_item:
        raise HTTPException(404, "generation not found")
    src = paths.resolve(src_item["wav"] if src_item else (b.path or ""))
    if not os.path.isfile(src):
        raise HTTPException(404, "source audio not found")
    if not os.path.isfile(os.path.join(rvc.WEIGHTS, b.model)):
        raise HTTPException(404, f"rvc model not found: {b.model}")
    if jobmgr.running_of_kind("train:s2") or jobmgr.running_of_kind("train:s1") or jobmgr.running_of_kind("rvc:train"):
        raise HTTPException(409, "training is running; RVC would OOM")
    base = os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(paths.GENERATED_DIR, f"{base}_rvc_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.wav")
    cmd, env, cwd = rvc.convert_cmd(b.model, src, dst, b.pitch, b.f0_method, b.index_rate, b.protect, b.rms_mix_rate)
    meta = {
        "dst": paths.rel_to_root(dst),
        "model": b.model,
        "character": src_item["character"] if src_item else "unknown",
        "text": src_item["text"] if src_item else base,
        "ref_audio": src_item["ref_audio"] if src_item else None,
        "prompt_text": src_item["prompt_text"] if src_item else None,
        "gpt": src_item["gpt"] if src_item else None,
        "sovits": src_item["sovits"] if src_item else None,
        "params": {**(src_item["params"] if src_item else {}), "rvc": b.model_dump(exclude={"generation_id", "path"}), "source_id": b.generation_id},
        "seed": src_item["seed"] if src_item else -1,
    }
    return jobmgr.launch("rvc:convert", f"RVC 音色转换 {base}", cmd, cwd, env, meta=meta, on_done=_add_to_library).public()


def _add_to_library(j: jobmgr.Job) -> dict:
    """转换 job 结束时在服务端入库(幂等):不依赖前端还停在原页面。"""
    if "library_id" in j.meta:
        return library.get(j.meta["library_id"])
    dst = paths.resolve(j.meta["dst"])
    if not os.path.isfile(dst):
        raise RuntimeError("output file missing")
    m = j.meta
    item = library.add(
        character=m["character"],
        text=m["text"],
        ref_audio=m["ref_audio"],
        prompt_text=m["prompt_text"],
        gpt=m["gpt"],
        sovits=m["sovits"],
        params=m["params"],
        wav=m["dst"],
        duration=sf.info(dst).duration,
        seed=m["seed"],
        elapsed=round((j.ended_at or time.time()) - (j.started_at or 0), 2),
        tags=["rvc"],
    )
    j.meta["library_id"] = item["id"]
    return item


class FinalizeBody(BaseModel):
    job_id: str


@router.post("/finalize")
def finalize(b: FinalizeBody):
    j = jobmgr.get(b.job_id)
    if not j or j.kind != "rvc:convert":
        raise HTTPException(404, "job not found")
    if j.status != "done":
        raise HTTPException(409, f"job not done ({j.status})")
    try:
        return _add_to_library(j)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
