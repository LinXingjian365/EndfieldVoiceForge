"""RVC(Retrieval-based Voice Conversion)后处理:导出小模型、建索引、转换。

RVC 有独立的 Py3.12 venv(config.PY_RVC),所以全部走子进程;转换一句约 15–20 s,同步等待即可。
"""
from __future__ import annotations

import os
import re
import subprocess

from . import paths

WEIGHTS = os.path.join(paths.RVC_DIR, "assets", "weights")
INDICES = os.path.join(paths.RVC_DIR, "assets", "indices")
LOGS = os.path.join(paths.RVC_DIR, "logs")
CKPT_RE = re.compile(r"^G_(\d+)\.pth$")


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": paths.RVC_DIR, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}


def _run(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run([paths.PY_RVC, *args], cwd=paths.RVC_DIR, env=_env(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def list_models() -> dict:
    models = []
    if os.path.isdir(WEIGHTS):
        for fn in sorted(os.listdir(WEIGHTS)):
            if fn.endswith(".pth"):
                st = os.stat(os.path.join(WEIGHTS, fn))
                models.append({"file": fn, "name": fn[:-4], "size": st.st_size, "mtime": st.st_mtime})
    indices = sorted(fn for fn in os.listdir(INDICES) if fn.endswith(".index")) if os.path.isdir(INDICES) else []
    exps = []
    if os.path.isdir(LOGS):
        for exp in sorted(os.listdir(LOGS)):
            d = os.path.join(LOGS, exp)
            if not os.path.isdir(d):
                continue
            ckpts = []
            for fn in os.listdir(d):
                m = CKPT_RE.match(fn)
                if m:
                    ckpts.append({"file": fn, "step": int(m.group(1)), "size": os.path.getsize(os.path.join(d, fn))})
            if ckpts or os.path.isdir(os.path.join(d, "3_feature768")):
                exps.append({"exp": exp, "checkpoints": sorted(ckpts, key=lambda c: c["step"]), "has_features": os.path.isdir(os.path.join(d, "3_feature768")), "has_index": any(exp in i for i in indices)})
    return {"models": models, "indices": indices, "experiments": exps}


def export_small(exp: str, ckpt: str, name: str, info: str = "") -> str:
    """logs/<exp>/G_*.pth -> assets/weights/<name>.pth(半精度、去 enc_q)。"""
    src = os.path.join(LOGS, exp, ckpt)
    if not os.path.isfile(src) or not CKPT_RE.match(ckpt):
        raise FileNotFoundError(ckpt)
    code = (
        "from train.process_ckpt import extract_small_model as f;"
        f"print(f({src!r},{name!r},'40k',True,{info or exp!r},'v2'))"
    )
    r = _run(["-c", code], timeout=300)
    out = os.path.join(WEIGHTS, f"{name}.pth")
    if r.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError((r.stdout + r.stderr)[-2000:])
    return f"{name}.pth"


def index_cmd(exp: str):
    return [paths.PY_RVC, "-m", "train.train_index", exp, "v2", "assets/indices", "4", "single"], {"PYTHONPATH": paths.RVC_DIR}, paths.RVC_DIR


def convert(model: str, src: str, dst: str, pitch: int = 0, f0_method: str = "rmvpe", index_rate: float = 0.5, protect: float = 0.33, rms_mix_rate: float = 1.0) -> float:
    """返回耗时秒。index_rate=0 时不需要索引。"""
    args = ["infer/cli.py", "--model", model, "--input", src, "--output", dst, "--pitch", str(pitch), "--f0-method", f0_method,
            "--index-rate", str(index_rate), "--protect", str(protect), "--rms-mix-rate", str(rms_mix_rate), "--overwrite"]
    import time

    t0 = time.time()
    r = _run(args, timeout=900)
    if r.returncode != 0 or not os.path.isfile(dst):
        raise RuntimeError((r.stdout + r.stderr)[-2000:])
    return time.time() - t0
