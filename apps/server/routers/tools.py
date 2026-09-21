"""工具箱:UVR5 / 切片 / 降噪 / ASR(整目录),都作为子进程 job。"""
import os
import shutil
import subprocess
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..core import gsv, jobs as jobmgr, paths

router = APIRouter(prefix="/tools", tags=["tools"])

FFMPEG = shutil.which("ffmpeg")


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


def _audio_out_dir() -> str:
    d = os.path.join(paths.OUTPUTS_DIR, "extracted")
    os.makedirs(d, exist_ok=True)
    return d


class ExtractAudioBody(BaseModel):
    path: str


@router.post("/extract_audio")
def extract_audio(b: ExtractAudioBody):
    """视频 -> 单声道 40kHz wav(供波形选区 + RVC 用)。ffmpeg 秒级同步。"""
    if not FFMPEG:
        raise HTTPException(500, "ffmpeg not found on PATH")
    src = paths.resolve(b.path)
    if not paths.is_safe(src) or not os.path.isfile(src):
        raise HTTPException(404, "video not found")
    base = os.path.splitext(os.path.basename(src))[0]
    out = os.path.join(_audio_out_dir(), f"{base}_{uuid.uuid4().hex[:6]}.wav")
    r = subprocess.run(
        [FFMPEG, "-y", "-i", src, "-vn", "-ac", "1", "-ar", "40000", "-c:a", "pcm_s16le", out],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0 or not os.path.isfile(out):
        raise HTTPException(500, (r.stderr or r.stdout)[-1500:])
    try:
        import soundfile as sf
        dur = sf.info(out).duration
    except Exception:  # noqa: BLE001
        dur = 0.0
    return {"path": paths.rel_to_root(out), "name": os.path.basename(out), "duration": round(dur, 3)}


class CutBody(BaseModel):
    path: str
    start: float
    end: float


@router.post("/cut")
def cut_audio(b: CutBody):
    """按秒级起止点截取音频片段(不重编码,直接流拷贝)。"""
    if not FFMPEG:
        raise HTTPException(500, "ffmpeg not found on PATH")
    src = paths.resolve(b.path)
    if not paths.is_safe(src) or not os.path.isfile(src):
        raise HTTPException(404, "audio not found")
    dur = b.end - b.start
    if dur <= 0 or b.start < 0:
        raise HTTPException(400, "invalid start/end")
    base = os.path.splitext(os.path.basename(src))[0]
    out = os.path.join(_audio_out_dir(), f"{base}_cut{round(b.start,2)}-{round(b.end,2)}_{uuid.uuid4().hex[:6]}.wav")
    r = subprocess.run(
        [FFMPEG, "-y", "-ss", f"{b.start:.3f}", "-i", src, "-t", f"{dur:.3f}", "-ac", "1", "-ar", "40000", "-c:a", "pcm_s16le", out],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0 or not os.path.isfile(out):
        raise HTTPException(500, (r.stderr or r.stdout)[-1500:])
    try:
        import soundfile as sf
        out_dur = sf.info(out).duration
    except Exception:  # noqa: BLE001
        out_dur = dur
    return {"path": paths.rel_to_root(out), "name": os.path.basename(out), "duration": round(out_dur, 3)}


class ConcatBody(BaseModel):
    paths: list[str]


@router.post("/concat")
def concat_audio(b: ConcatBody):
    """按顺序拼接多个音频片段(组合标记用)。要求采样率/声道一致(均为 40kHz 单声道)。"""
    if not FFMPEG:
        raise HTTPException(500, "ffmpeg not found on PATH")
    if len(b.paths) < 2:
        raise HTTPException(400, "need at least 2 files to concat")
    ins = []
    for p in b.paths:
        ap = paths.resolve(p)
        if not paths.is_safe(ap) or not os.path.isfile(ap):
            raise HTTPException(404, f"audio not found: {p}")
        ins.append(ap)
    out = os.path.join(_audio_out_dir(), f"combo_{uuid.uuid4().hex[:6]}.wav")
    cmd = [FFMPEG, "-y"]
    for p in ins:
        cmd += ["-i", p]
    flt = "".join(f"[{i}:a]" for i in range(len(ins))) + f"concat=n={len(ins)}:v=0:a=1[out]"
    cmd += ["-filter_complex", flt, "-map", "[out]", "-ac", "1", "-ar", "40000", "-c:a", "pcm_s16le", out]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.isfile(out):
        raise HTTPException(500, (r.stderr or r.stdout)[-1500:])
    try:
        import soundfile as sf
        out_dur = sf.info(out).duration
    except Exception:  # noqa: BLE001
        out_dur = 0.0
    return {"path": paths.rel_to_root(out), "name": os.path.basename(out), "duration": round(out_dur, 3)}
