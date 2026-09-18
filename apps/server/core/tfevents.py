"""读取 tensorboard events 得到训练曲线。"""
from __future__ import annotations

import glob
import math
import os

from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

from . import gsv


def _read(path: str, tags_filter: tuple[str, ...] | None = None) -> dict[str, list[tuple[int, float]]]:
    ea = EventAccumulator(path, size_guidance={"scalars": 0})
    ea.Reload()
    out = {}
    for tag in ea.Tags().get("scalars", []):
        if tags_filter and not tag.startswith(tags_filter):
            continue
        pts = [(s.step, float(s.value)) for s in ea.Scalars(tag)]
        out[tag] = [(st, v) for st, v in pts if math.isfinite(v)]
    return out


def curves(exp: str, version: str = "v2") -> dict:
    d = gsv.exp_dir(exp)
    result = {"s2": {}, "s1": {}}
    # s2: 写在 exp_dir 根(SummaryWriter(log_dir=s2_ckpt_dir))
    for f in sorted(glob.glob(os.path.join(d, "events.out.tfevents*"))):
        for k, v in _read(f, ("loss/", "learning_rate", "grad_norm")).items():
            result["s2"].setdefault(k, []).extend(v)
    # s1: lightning logger,取最新 version_*
    s1_root = os.path.join(d, f"logs_s1_{version}", f"logs_s1_{version}")
    if os.path.isdir(s1_root):
        vers = sorted(glob.glob(os.path.join(s1_root, "version_*")), key=os.path.getmtime)
        for vd in vers[-1:]:
            for f in glob.glob(os.path.join(vd, "events.out.tfevents*")):
                for k, v in _read(f).items():
                    if k == "hp_metric":
                        continue
                    result["s1"].setdefault(k, []).extend(v)
    return result


def rvc_curves(exp: str) -> dict:
    """RVC 训练曲线:SummaryWriter(log_dir=logs/<exp>),step 为 global_step。"""
    from . import rvc

    d = os.path.join(rvc.LOGS, exp)
    out: dict[str, list] = {}
    for f in sorted(glob.glob(os.path.join(d, "events.out.tfevents*")), key=os.path.getmtime):
        for k, v in _read(f, ("loss/g/total", "loss/d/total", "loss/g/mel", "loss/g/kl", "loss/g/fm", "learning_rate")).items():
            out.setdefault(k, []).extend(v)
    return out
