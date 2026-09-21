# -*- coding: utf-8 -*-
"""精确 diff：比对 AudioDialog.json 里 typhoea 台词 vs 已提取的语音 fid。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config  # noqa: E402
from apps.server.core import paths  # noqa: E402


def u32(x):
    x = int(x)
    return x & 0xFFFFFFFF


def main():
    dialog = json.load(open(config.AUDIO_DIALOG_JSON, encoding="utf-8"))
    # 所有 typhoea 台词（speakerChannel == typhoea）
    typhoea = {k: v for k, v in dialog.items() if v.get("speakerChannel") == "typhoea"}
    print(f"[1] AudioDialog 里 typhoea 台词总数: {len(typhoea)}")

    # 已提取的 fid 缓存
    fid_path = os.path.join(ROOT, "datasets", "cache", "typhoea_unique_fids.json")
    uniq = json.load(open(fid_path, encoding="utf-8")) if os.path.isfile(fid_path) else []
    print(f"[2] 已提取缓存(unique_fids)条目数: {len(uniq)}")

    # 归一化 key 集合
    extracted_keys = {u32(u["key"]) for u in uniq if "key" in u}
    typhoea_keys = {u32(k) for k in typhoea}
    print(f"[3] 归一化后已提取 key 数: {len(extracted_keys)}")
    print(f"[4] 归一化后 typhoea key 数: {len(typhoea_keys)}")

    missing = typhoea_keys - extracted_keys
    print(f"[5] 未提取的新 typhoea 台词: {len(missing)}")
    extra = extracted_keys - typhoea_keys
    print(f"[6] 已提取但不在当前 AudioDialog 的(可能来自 SNS/sim 等): {len(extra)}")

    # 也统计语音池实际 wav 数量
    pool_dir = config.SPEECH_POOL_DIR
    if os.path.isdir(pool_dir):
        wavs = [f for f in os.listdir(pool_dir) if f.endswith(".wav")]
        print(f"[7] 语音池 typhoea_speech2 wav 数量: {len(wavs)}")

    train_dir = config.TRAIN_WAV_DIR
    if os.path.isdir(train_dir):
        tw = [f for f in os.listdir(train_dir) if f.endswith(".wav")]
        print(f"[8] 训练集 typhoea_train wav 数量: {len(tw)}")

    if missing:
        sample = sorted(missing)[:5]
        print(f"    缺失样例 key: {sample}")
        # 打印这些 key 对应的 path
        for k in sample:
            for dk, dv in typhoea.items():
                if u32(dk) == k:
                    print(f"      key={k} path={dv.get('path')} dur={dv.get('wavDuration')}")


if __name__ == "__main__":
    main()
