"""训练:格式化 1a/1b/1sv/1c、s1、s2 作为 job;曲线;checkpoint 列表。"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import characters, gsv, jobs as jobmgr, paths, tfevents, tts_engine

router = APIRouter(prefix="/training", tags=["training"])


@router.get("/versions")
def versions():
    return gsv.available_versions()


@router.get("/{exp}/status")
def status(exp: str, version: str = "v2"):
    fmt = gsv.format_status(exp)
    running = {j.kind: j.id for j in jobmgr.all_jobs() if j.status == "running" and j.meta.get("exp") == exp}
    weights = [w for w in tts_engine.list_weights() if w["exp"] == exp]
    return {"exp": exp, "version": version, "format": fmt, "running": running, "weights": weights, "expDir": paths.rel_to_root(gsv.exp_dir(exp))}


class FormatBody(BaseModel):
    character: str
    exp: str
    version: str = "v2"
    stages: list[str] = ["1a", "1b", "1c"]


def _dataset_of(cid: str) -> tuple[str, str]:
    c = characters.get(cid)
    if not c:
        raise HTTPException(404, "character not found")
    inp_text = paths.resolve(c["dataset"]["list"])
    inp_wav = paths.resolve(c["dataset"]["wavDir"])
    if not os.path.isfile(inp_text):
        raise HTTPException(400, f"list not found: {c['dataset']['list']}")
    return inp_text, inp_wav


@router.post("/format")
def run_format(b: FormatBody):
    """逐阶段起 job,前端按顺序触发;格式化也吃显存,先卸载推理引擎。"""
    inp_text, inp_wav = _dataset_of(b.character)
    stage = b.stages[0]
    if stage not in gsv.FORMAT_STAGES:
        raise HTTPException(400, "bad stage")
    kind = f"train:format:{stage}"
    if jobmgr.running_of_kind(kind):
        raise HTTPException(409, "already running")
    tts_engine.get().unload()
    cmd, env, cwd = gsv.format_stage(stage, b.exp, inp_text, inp_wav, b.version)
    job = jobmgr.launch(kind, f"{stage} {gsv.FORMAT_STAGES[stage][1]}", cmd, cwd, env, meta={"exp": b.exp, "stage": stage, "version": b.version, "character": b.character})
    return job.public()


@router.post("/format/{stage}/merge")
def merge(stage: str, exp: str):
    gsv.merge_parts(stage, exp)
    return gsv.format_status(exp)


MIN_FREE_RAM_GB = 4.0


def _guard_training(free_engine: bool):
    if any(jobmgr.running_of_kind(k) for k in ("train:s2", "train:s1", "rvc:train")):
        raise HTTPException(409, "a training job is already running")
    if free_engine:
        tts_engine.get().unload()
    import psutil

    free_gb = psutil.virtual_memory().available / 2**30
    if free_gb < MIN_FREE_RAM_GB:
        raise HTTPException(507, f"主机可用内存仅 {free_gb:.1f} GB,训练需要 ≥{MIN_FREE_RAM_GB:g} GB;请关闭浏览器/其他进程后重试")


class S2Body(BaseModel):
    exp: str
    version: str = "v2"
    batch_size: int = 1
    epochs: int = 8
    save_every: int = 1
    text_low_lr_rate: float = 0.4
    if_save_latest: bool = True
    if_save_every_weights: bool = True
    grad_ckpt: bool = True
    lora_rank: int = 0
    resume: bool = True
    free_engine: bool = True


@router.post("/s2")
def run_s2(b: S2Body):
    _guard_training(b.free_engine)
    cmd, env, cwd = gsv.s2_cmd(b.exp, b.version, b.batch_size, b.epochs, b.save_every, b.text_low_lr_rate, b.if_save_latest, b.if_save_every_weights, b.grad_ckpt, b.lora_rank, b.resume)
    return jobmgr.launch("train:s2", f"SoVITS 训练 {b.exp} ×{b.epochs}", cmd, cwd, env, meta={"exp": b.exp, "version": b.version, "epochs": b.epochs}).public()


class S1Body(BaseModel):
    exp: str
    version: str = "v2"
    batch_size: int = 1
    epochs: int = 15
    save_every: int = 1
    if_save_latest: bool = True
    if_save_every_weights: bool = True
    if_dpo: bool = False
    free_engine: bool = True


@router.post("/s1")
def run_s1(b: S1Body):
    _guard_training(b.free_engine)
    cmd, env, cwd = gsv.s1_cmd(b.exp, b.version, b.batch_size, b.epochs, b.save_every, b.if_save_latest, b.if_save_every_weights, b.if_dpo)
    return jobmgr.launch("train:s1", f"GPT 训练 {b.exp} ×{b.epochs}", cmd, cwd, env, meta={"exp": b.exp, "version": b.version, "epochs": b.epochs}).public()


@router.get("/{exp}/curves")
def curves(exp: str, version: str = "v2"):
    try:
        return tfevents.curves(exp, version)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@router.delete("/weights")
def delete_weight(path: str):
    ap = os.path.join(paths.GSV_DIR, path)
    if not (path.startswith("GPT_weights") or path.startswith("SoVITS_weights")) or not os.path.isfile(ap):
        raise HTTPException(404)
    eng = tts_engine.get()
    if path in (eng.gpt, eng.sovits):
        raise HTTPException(409, "weight is currently loaded")
    os.remove(ap)
    return {"ok": True}
