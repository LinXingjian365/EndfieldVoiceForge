# -*- coding: utf-8 -*-
"""清洗刚提取的台词 wav 并扩入 RVC 训练集。

对 datasets/typhoea_speech_externals/ 里的 323 条台词:
    1. 去重: 与 datasets/typhoea_train/manifest.json 已有 path(basename) 对比, 跳过已存在的
    2. 去静音: 按帧能量 trim 首尾静音(留 50ms 缓冲)
    3. 过滤: trim 后 < 0.3s 的丢弃(几乎纯静音/杂音)
    4. 复制到 datasets/typhoea_train/, 命名 typhoea_<fid>.wav (fid=externals 文件ID)
    5. 追加到 manifest.json

采样率保持 48k(RVC 预处理会统一重采样到 40k)。

用法(在 EndfieldVoiceForge 目录):
    third_party\\index-tts\\.venv\\Scripts\\python.exe scripts\\clean_and_extend_dataset.py
"""
from __future__ import annotations

import json
import os
import shutil

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTERNALS = os.path.join(ROOT, "datasets", "typhoea_speech_externals")
MAPPING = os.path.join(EXTERNALS, "mapping.json")
TRAIN_DIR = os.path.join(ROOT, "datasets", "typhoea_train")
MANIFEST = os.path.join(TRAIN_DIR, "manifest.json")

MIN_DUR = 0.3          # trim 后最小时长(秒)
SILENCE_RATIO = 0.02   # 静音阈值 = 峰值 * 这个比例
FRAME_MS = 20          # 帧长
PAD_MS = 50            # trim 后保留的缓冲


def trim_silence(y, sr):
    """按帧能量去掉首尾静音, 返回 trim 后的数组。全静音返回 None。"""
    frame = max(1, int(sr * FRAME_MS / 1000))
    n = len(y) // frame
    if n < 1:
        return None
    # 每帧 RMS
    y_frames = y[: n * frame].reshape(n, frame)
    rms = np.sqrt(np.mean(y_frames ** 2, axis=1))
    peak = float(rms.max()) if rms.size else 0.0
    if peak <= 0:
        return None
    thresh = peak * SILENCE_RATIO
    voiced = np.where(rms > thresh)[0]
    if voiced.size == 0:
        return None
    start = max(0, voiced[0] * frame - int(sr * PAD_MS / 1000))
    end = min(len(y), (voiced[-1] + 1) * frame + int(sr * PAD_MS / 1000))
    if end - start < sr * MIN_DUR:
        return None
    return y[start:end]


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    existing_paths = {os.path.basename(m.get("path", "")) for m in manifest}
    existing_wavs = {m.get("wav", "") for m in manifest}
    print(f"训练集现有条目: {len(manifest)} (去重 path: {len(existing_paths)})")

    mapping = json.load(open(MAPPING, encoding="utf-8"))
    print(f"待清洗台词: {len(mapping)}")

    added = 0
    skipped_dup = 0
    skipped_short = 0
    skipped_missing = 0
    failed = 0
    new_entries = []

    for m in mapping:
        path = m.get("path", "")
        base = os.path.basename(path)
        fid = m.get("fid")
        wav_name = f"typhoea_{fid}.wav"
        src = os.path.join(EXTERNALS, m.get("wav", ""))

        if base in existing_paths or wav_name in existing_wavs:
            skipped_dup += 1
            continue
        if not os.path.isfile(src):
            skipped_missing += 1
            continue

        try:
            y, sr = sf.read(src, dtype="float32")
            if y.ndim > 1:
                y = y.mean(axis=1)  # 转单声道
            trimmed = trim_silence(y, sr)
            if trimmed is None:
                skipped_short += 1
                continue
            dst = os.path.join(TRAIN_DIR, wav_name)
            sf.write(dst, trimmed, sr)
            added += 1
            dur = len(trimmed) / sr
            new_entries.append({
                "idx": fid,
                "wav": wav_name,
                "dur": round(dur, 2),
                "f0": 0.0,
                "voiced": 0.0,
                "path": base,
                "vt": m.get("voType", 0),
            })
        except Exception as e:
            failed += 1
            print(f"  !! {base}: {e}")

    # 追加 manifest
    manifest.extend(new_entries)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n=== 结果 ===")
    print(f"新增(去静音后): {added}")
    print(f"跳过-已存在(去重): {skipped_dup}")
    print(f"跳过-过短/纯静音: {skipped_short}")
    print(f"跳过-源文件缺失: {skipped_missing}")
    print(f"失败: {failed}")
    print(f"训练集总数: {len(manifest)}")
    print(f"新 wav 位置: {TRAIN_DIR}")


if __name__ == "__main__":
    main()
