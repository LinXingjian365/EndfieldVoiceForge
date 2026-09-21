# -*- coding: utf-8 -*-
"""一键提取提弗洛斯全部语音并转 wav 到语音池。

用法（在 EndfieldVoiceForge 目录）:
    third_party\\index-tts\\.venv\\Scripts\\python.exe scripts\\extract_typhoea_voice.py

流程:
    1. 若 Audio_wem_all 为空,从 Main 流 PCK 解密提取 wem(约 4.4GB,较慢)
    2. 按 48kHz 时长匹配 typhoea 台词 -> fid
    3. 与已提取的 81 条 diff,得到新增 fid
    4. vgmstream 转 wav -> datasets/typhoea_speech_new/

说明:
    - 时长匹配存在"同时长多候选"的歧义;唯一匹配(单 fid)直接转,
      多候选写入 _typhoea_ambiguous.json 供人工核对。
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config  # noqa: E402

UNPACKER = config.UNPACKER_DIR
WEM_ALL = os.path.join(UNPACKER, "DecryptOutput", "Audio_wem_all")
VGSTREAM = config.VGMSTREAM
OUT_DIR = os.path.join(ROOT, "datasets", "typhoea_speech_new")
OLD_FIDS = os.path.join(ROOT, "datasets", "cache", "typhoea_unique_fids.json")
ALL_MATCHED = os.path.join(UNPACKER, "_typhoea_all_matched.json")
AMBIGUOUS = os.path.join(UNPACKER, "_typhoea_ambiguous.json")


def step1_extract():
    if glob.glob(os.path.join(WEM_ALL, "*.wem")):
        print(f"[1] wem 已存在({len(glob.glob(os.path.join(WEM_ALL, '*.wem')))} 个),跳过提取")
        return
    print("[1] 从 Main 流 PCK 提取 wem(约 4.4GB,需几分钟)...")
    r = subprocess.run([sys.executable, os.path.join(UNPACKER, "_extract_all_wem.py")], cwd=UNPACKER)
    if r.returncode != 0:
        print("  !! 提取失败,退出")
        sys.exit(1)


def step2_match():
    print("[2] 匹配 typhoea 台词...")
    subprocess.run([sys.executable, os.path.join(UNPACKER, "_match_final.py")], cwd=UNPACKER)


def step3_diff():
    if not os.path.isfile(ALL_MATCHED):
        print("  !! 未找到匹配结果,退出")
        sys.exit(1)
    all_matched = json.load(open(ALL_MATCHED, encoding="utf-8"))
    old = json.load(open(OLD_FIDS, encoding="utf-8")) if os.path.isfile(OLD_FIDS) else []
    old_fids = {int(o["fid"]) for o in old}

    new_unique = []   # 单 fid 且不在旧集合
    ambiguous = []    # 多 fid
    for m in all_matched:
        fids = [int(f) for f in m.get("fids", [])]
        if not fids:
            continue
        fresh = [f for f in fids if f not in old_fids]
        if not fresh:
            continue
        if len(fids) == 1:
            new_unique.append({"key": m["key"], "duration": m["duration"], "fid": fids[0]})
        else:
            ambiguous.append({"key": m["key"], "duration": m["duration"], "fids": fids})

    with open(AMBIGUOUS, "w", encoding="utf-8") as f:
        json.dump(ambiguous, f, ensure_ascii=False, indent=2)
    print(f"[3] 匹配 {len(all_matched)} 条;已提取 {len(old)} 条;新增唯一 {len(new_unique)} 条,歧义 {len(ambiguous)} 条")
    return new_unique


def step4_convert(new_unique):
    os.makedirs(OUT_DIR, exist_ok=True)
    ok = 0
    for m in new_unique:
        fid = m["fid"]
        wem = os.path.join(WEM_ALL, f"{fid}.wem")
        wav = os.path.join(OUT_DIR, f"{fid}.wav")
        if not os.path.isfile(wem):
            continue
        if not os.path.isfile(wav):
            subprocess.run([VGSTREAM, "-o", wav, wem], capture_output=True, timeout=120)
        if os.path.isfile(wav):
            ok += 1
    print(f"[4] 转 wav 完成: {ok} 个 -> {OUT_DIR}")


if __name__ == "__main__":
    step1_extract()
    step2_match()
    new = step3_diff()
    step4_convert(new)
    print("\n完成。歧义项见 _typhoea_ambiguous.json(需人工核对),新语音在 datasets/typhoea_speech_new/")
