"""进程内 GPT-SoVITS 推理引擎(单例)。

GPT-SoVITS 的代码大量用相对路径(GPT_SoVITS/pretrained_models/... 等),
所以首次加载时 chdir 到 gpt-sovits 目录并把它加进 sys.path。server 自身只用绝对路径,不受影响。
"""
from __future__ import annotations

import io
import os
import re
import sys
import threading
import time

import numpy as np

from . import paths

_lock = threading.Lock()
_instance: "Engine | None" = None

WEIGHT_RE = re.compile(r"^(?P<exp>.+?)[-_]e(?P<epoch>\d+)(?:_s(?P<step>\d+))?\.(?:ckpt|pth)$")
SOVITS_DIRS = ("SoVITS_weights", "SoVITS_weights_v2", "SoVITS_weights_v2Pro", "SoVITS_weights_v2ProPlus", "SoVITS_weights_v3", "SoVITS_weights_v4")
GPT_DIRS = ("GPT_weights", "GPT_weights_v2", "GPT_weights_v2Pro", "GPT_weights_v2ProPlus", "GPT_weights_v3", "GPT_weights_v4")


def _bootstrap_gsv():
    if paths.GSV_DIR not in sys.path:
        sys.path.insert(0, paths.GSV_DIR)
        sys.path.insert(0, os.path.join(paths.GSV_DIR, "GPT_SoVITS"))
    os.chdir(paths.GSV_DIR)


def version_of_dir(d: str) -> str:
    m = re.search(r"_(v\d\w*)$", d)
    return m.group(1) if m else "v1"


def list_weights() -> list[dict]:
    out = []
    for kind, dirs in (("gpt", GPT_DIRS), ("sovits", SOVITS_DIRS)):
        for d in dirs:
            full = os.path.join(paths.GSV_DIR, d)
            if not os.path.isdir(full):
                continue
            for fn in os.listdir(full):
                if not fn.endswith((".ckpt", ".pth")):
                    continue
                m = WEIGHT_RE.match(fn)
                st = os.stat(os.path.join(full, fn))
                out.append(
                    {
                        "kind": kind,
                        "path": f"{d}/{fn}",
                        "file": fn,
                        "exp": m.group("exp") if m else fn.rsplit(".", 1)[0],
                        "epoch": int(m.group("epoch")) if m else None,
                        "step": int(m.group("step")) if m and m.group("step") else None,
                        "version": version_of_dir(d),
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                    }
                )
    out.sort(key=lambda w: (w["kind"], w["exp"], w["epoch"] or 0, w["step"] or 0))
    return out


class Engine:
    def __init__(self):
        self.tts = None
        self.character_id: str | None = None
        self.gpt: str | None = None
        self.sovits: str | None = None
        self.version: str | None = None
        self.device = "cuda:0"
        self.busy = False

    # ---------- 状态 ----------
    def describe(self) -> dict:
        return {
            "loaded": self.tts is not None,
            "gpt": self.gpt,
            "sovits": self.sovits,
            "version": self.version,
            "device": self.device,
            "busy": self.busy,
        }

    # ---------- 加载 ----------
    def load(self, gpt: str, sovits: str, version: str = "v2", character_id: str | None = None):
        """gpt/sovits 为相对 gpt-sovits 目录的路径,如 GPT_weights_v2/typhoea-e20.ckpt。"""
        with _lock:
            _bootstrap_gsv()
            from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config

            gpt_abs = os.path.join(paths.GSV_DIR, gpt)
            sov_abs = os.path.join(paths.GSV_DIR, sovits)
            for p in (gpt_abs, sov_abs):
                if not os.path.isfile(p):
                    raise FileNotFoundError(p)
            pm = os.path.join(paths.GSV_DIR, "GPT_SoVITS", "pretrained_models")
            if self.tts is None:
                cfg = TTS_Config(
                    {
                        "custom": {
                            "device": self.device,
                            "is_half": self.device != "cpu",
                            "version": version,
                            "t2s_weights_path": gpt_abs,
                            "vits_weights_path": sov_abs,
                            "bert_base_path": os.path.join(pm, "chinese-roberta-wwm-ext-large"),
                            "cnhuhbert_base_path": os.path.join(pm, "chinese-hubert-base"),
                        }
                    }
                )
                self.tts = TTS(cfg)
            else:
                if gpt != self.gpt:
                    self.tts.init_t2s_weights(gpt_abs)
                if sovits != self.sovits:
                    self.tts.init_vits_weights(sov_abs)
            self.gpt, self.sovits, self.version = gpt, sovits, version
            if character_id:
                self.character_id = character_id
        return self.describe()

    def ensure_loaded(self, character: dict | None):
        if self.tts is not None:
            return
        if not character:
            raise RuntimeError("engine not loaded and no character to load defaults from")
        w = character["weights"]
        self.load(w["gpt"], w["sovits"], w.get("version", "v2"), character["id"])

    def _free_locked(self):
        """(调用方须持有 _lock) 释放模型与显存。"""
        if self.tts is not None:
            del self.tts
            self.tts = None
            self.gpt = self.sovits = self.version = None
        import gc

        gc.collect()
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass

    def unload(self) -> dict:
        """释放推理模型与显存(保持当前 device 不变)。"""
        with _lock:
            self._free_locked()
        return self.describe()

    def set_device(self, device: str) -> dict:
        """切换推理设备。训练切 cpu 时释放显存,让训练与合成可同时进行(合成走 CPU,慢但可用)。"""
        with _lock:
            if self.device != device:
                self._free_locked()
                self.device = device
        return self.describe()

    # ---------- 合成 ----------
    def synthesize(self, params: dict) -> tuple[bytes, int, float, float]:
        """返回 (wav_bytes, sr, duration_sec, elapsed_sec)。"""
        if self.tts is None:
            raise RuntimeError("engine not loaded")
        import soundfile as sf

        p = dict(params)
        p["ref_audio_path"] = paths.resolve(p["ref_audio_path"])
        p["aux_ref_audio_paths"] = [paths.resolve(x) for x in (p.get("aux_ref_audio_paths") or [])]
        p["return_fragment"] = False
        with _lock:
            self.busy = True
            t0 = time.time()
            try:
                _bootstrap_gsv()
                chunks = []
                sr = 32000
                for sr, audio in self.tts.run(p):
                    chunks.append(np.asarray(audio))
            finally:
                self.busy = False
        elapsed = time.time() - t0
        data = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
        if data.dtype != np.int16:
            data = (np.clip(data, -1, 1) * 32767).astype(np.int16)
        buf = io.BytesIO()
        sf.write(buf, data, sr, format="wav")
        return buf.getvalue(), sr, len(data) / sr, elapsed


def get() -> Engine:
    global _instance
    if _instance is None:
        _instance = Engine()
    return _instance


# ---------- ASR / 长音频切分(复用 GPT-SoVITS 工具) ----------

def asr(audio_path: str, lang: str = "zh") -> str:
    _bootstrap_gsv()
    from tools.asr.funasr_asr import only_asr

    return only_asr(paths.resolve(audio_path), lang).strip()


def slice_reference(audio_path: str, max_dur: float = 10.0, min_dur: float = 1.0, do_asr: bool = True) -> list[dict]:
    """长参考音频 -> 多个 ≤max_dur 片段(+ASR)。产物在 outputs/ref_slices/<base>/。"""
    _bootstrap_gsv()
    from scipy.io import wavfile
    from tools.my_utils import load_audio
    from tools.slicer2 import Slicer

    src = paths.resolve(audio_path)
    sr = 32000
    audio = load_audio(src, sr)
    slicer = Slicer(sr=sr, threshold=-40, min_length=2000, min_interval=300, hop_size=10, max_sil_kept=500)
    base = os.path.splitext(os.path.basename(src))[0]
    out_dir = os.path.join(paths.REF_SLICES_DIR, base)
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    idx = 0
    for chunk, _s, _e in slicer.slice(audio):
        dur = len(chunk) / sr
        pieces = []
        if dur > max_dur:
            step = int(max_dur * sr)
            for i in range(0, len(chunk), step):
                piece = chunk[i : i + step]
                if len(piece) / sr >= min_dur:
                    pieces.append(piece)
        elif dur >= min_dur:
            pieces.append(chunk)
        for piece in pieces:
            name = f"{base}_seg{idx:03d}.wav"
            fp = os.path.join(out_dir, name)
            m = float(np.abs(piece).max())
            if m > 1e-6:
                piece = piece / m * 0.95
            wavfile.write(fp, sr, (piece * 32767).astype(np.int16))
            text = ""
            if do_asr:
                try:
                    text = asr(fp)
                except Exception:  # noqa: BLE001
                    text = ""
            rows.append({"file": name, "path": paths.rel_to_root(fp), "duration": round(len(piece) / sr, 3), "text": text})
            idx += 1
    return rows
