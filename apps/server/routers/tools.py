"""工具箱:UVR5 / 切片 / 降噪 / ASR(整目录),都作为子进程 job。"""
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import gsv, jobs as jobmgr, paths

router = APIRouter(prefix="/tools", tags=["tools"])


def _in(p: str) -> str:
    ap = paths.resolve(p)
    if not os.path.exists(ap):
        raise HTTPException(404, f"input not found: {p}")
    return ap


def _out(p: str) -> str:
    ap = paths.resolve(p)
    os.makedirs(ap, exist_ok=True)
    return ap


@router.get("/uvr5/models")
def uvr5_models():
    return gsv.uvr5_models()


class Uvr5Body(BaseModel):
    model: str
    input: str
    out_vocal: str = "outputs/uvr5/vocal"
    out_inst: str = "outputs/uvr5/inst"
    agg: int = 10
    format: str = "wav"


@router.post("/uvr5")
def run_uvr5(b: Uvr5Body):
    cmd, env, cwd = gsv.uvr5_cmd(b.model, _in(b.input), _out(b.out_vocal), _out(b.out_inst), b.agg, b.format)
    return jobmgr.launch("tool:uvr5", f"UVR5 {b.model}", cmd, cwd, env, meta=b.model_dump()).public()


class SliceBody(BaseModel):
    input: str
    output: str = "outputs/slices"
    threshold: int = -34
    min_length: int = 4000
    min_interval: int = 300
    hop_size: int = 10
    max_sil_kept: int = 500
    max_amp: float = 0.9
    alpha: float = 0.25


@router.post("/slice")
def run_slice(b: SliceBody):
    cmd, env, cwd = gsv.slice_cmd(_in(b.input), _out(b.output), b.threshold, b.min_length, b.min_interval, b.hop_size, b.max_sil_kept, b.max_amp, b.alpha)
    return jobmgr.launch("tool:slice", "音频切片", cmd, cwd, env, meta=b.model_dump()).public()


class DenoiseBody(BaseModel):
    input: str
    output: str = "outputs/denoised"
    precision: str = "float16"


@router.post("/denoise")
def run_denoise(b: DenoiseBody):
    cmd, env, cwd = gsv.denoise_cmd(_in(b.input), _out(b.output), b.precision)
    return jobmgr.launch("tool:denoise", "降噪", cmd, cwd, env, meta=b.model_dump()).public()


class AsrBody(BaseModel):
    input: str
    output: str = "outputs/asr"
    lang: str = "zh"
    backend: str = "funasr"
    precision: str = "float32"


@router.post("/asr")
def run_asr(b: AsrBody):
    cmd, env, cwd = gsv.asr_cmd(_in(b.input), _out(b.output), b.lang, b.backend, b.precision)
    return jobmgr.launch("tool:asr", f"ASR {b.backend}", cmd, cwd, env, meta=b.model_dump()).public()


@router.get("/browse")
def browse(path: str = "outputs"):
    """列目录(仅允许根内),给工具页选输入/输出用。"""
    ap = paths.resolve(path)
    if not paths.is_safe(ap) or not os.path.isdir(ap):
        raise HTTPException(404)
    items = []
    for fn in sorted(os.listdir(ap)):
        p = os.path.join(ap, fn)
        items.append({"name": fn, "dir": os.path.isdir(p), "size": os.path.getsize(p) if os.path.isfile(p) else None, "rel": paths.rel_to_root(p)})
    return {"path": paths.rel_to_root(ap), "items": items}
