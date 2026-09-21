# -*- coding: utf-8 -*-
"""从 Chinese stream PCK 的 externals 扇区提取提弗洛斯台词（外部语音）。

之前的 extract_typhoea_voice.py 是从 Main 流 PCK（Audio_wem_all）做的时长匹配，
那批只含战斗音效，不含台词。台词走 Wwise 外部源(externals)，存在
`Chinese/default_chinese_stream.pck` 的 externals 扇区里。

流程:
    1. 解析 externals 扇区(28277 条, 64-bit id = hi<<32|lo, 48kHz)
    2. 解密每个 wem 头 -> (采样率, 总样本数)
    3. 按 wavDuration 时长匹配 typhoea 台词
    4. 唯一匹配(单 fid)直接提取 wem -> vgmstream 转 wav -> datasets/typhoea_speech_externals/
       多候选写 ambiguous,未匹配写 unmatched,供后续人工核对

用法(在 EndfieldVoiceForge 目录):
    third_party\\index-tts\\.venv\\Scripts\\python.exe scripts\\extract_typhoea_externals.py
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config  # noqa: E402

config.import_unpacker()
from extract_akpk import read_u32, decrypt_vfs, decrypt_wem  # noqa: E402

PCK = config.PCK_CHINESE_STREAM
AD = config.AUDIO_DIALOG_JSON
VGSTREAM = config.VGMSTREAM
OUT_WAV = os.path.join(ROOT, "datasets", "typhoea_speech_externals")
AMBIGUOUS = os.path.join(ROOT, "datasets", "typhoea_externals_ambiguous.json")
UNMATCHED = os.path.join(ROOT, "datasets", "typhoea_externals_unmatched.json")
MAPPING = os.path.join(OUT_WAV, "mapping.json")


def parse_externals():
    """返回 externals 扇区条目列表 [(lo, hi, sz, off, lang)]。"""
    fp = open(PCK, "rb")
    magic = fp.read(4)
    hs = struct.unpack("<I", fp.read(4))[0]
    fp.seek(0)
    d = bytearray(fp.read(hs + 16))
    fp.close()
    decrypt_vfs(d, 12, hs - 4, hs, 0)
    d[0:4] = b"AKPK"
    struct.pack_into("<I", d, 8, 1)
    langs = read_u32(d, 12)
    banks = read_u32(d, 16)
    sounds = read_u32(d, 20)
    spos = 28 + langs + banks + sounds
    ecnt = read_u32(d, spos)
    ep = spos + 4
    entries = []
    for i in range(ecnt):
        b = ep + i * 24
        lo = read_u32(d, b)
        blk = read_u32(d, b + 8)
        sz = read_u32(d, b + 12)
        off = read_u32(d, b + 16)
        lang = read_u32(d, b + 20)
        entries.append((lo, sz, off * blk if blk else off, lang))
    return entries


def read_wem_head(off, lo):
    """读 wem 头并解密，返回 (采样率, 总样本数)，失败返回 None。"""
    f = open(PCK, "rb")
    f.seek(off)
    wem = bytearray(f.read(48))
    f.close()
    decrypt_vfs(wem, 0, 48, lo, 0)
    if bytes(wem[:4]) not in (b"RIFF", b"RIFX"):
        return None
    return read_u32(wem, 24), read_u32(wem, 44)


def extract_wem(off, sz, lo):
    """读完整 wem 并解密，返回 bytes。"""
    f = open(PCK, "rb")
    f.seek(off)
    wem = bytearray(f.read(sz))
    f.close()
    decrypt_wem(wem, lo)
    return bytes(wem)


def load_typhoea():
    data = json.load(open(AD, encoding="utf-8"))
    return [(k, v) for k, v in data.items() if "typhoea" in str(v.get("speakerChannel", "")).lower()]


def main():
    print("[1] 解析 externals 扇区...")
    entries = parse_externals()
    print(f"    externals 条目: {len(entries)}")

    print("[2] 读取 wem 头...")
    smap = defaultdict(list)  # (sr, total) -> [lo]
    for lo, sz, off, lang in entries:
        r = read_wem_head(off, lo)
        if r is not None:
            smap[r].append(lo)
    print(f"    可读头: {sum(len(v) for v in smap.values())}")

    print("[3] 匹配 typhoea 台词...")
    typhoea = load_typhoea()
    matched = {}
    unmatched = []
    for k, v in typhoea:
        dur = v.get("wavDuration", 0)
        found = None
        for sr in (48000, 24000, 44100):
            exp = round(dur * sr)
            cands = smap.get((sr, exp))
            if not cands:
                for delta in (-2, -1, 1, 2):
                    if smap.get((sr, exp + delta)):
                        cands = smap.get((sr, exp + delta))
                        break
            if cands:
                found = (sr, cands)
                break
        if found:
            matched[k] = (v, found[0], found[1])
        else:
            unmatched.append((k, v))

    unique = {k: v for k, v in matched.items() if len(v[2]) == 1}
    ambiguous = {k: v for k, v in matched.items() if len(v[2]) > 1}
    print(f"    匹配 {len(matched)}/{len(typhoea)}  唯一 {len(unique)}  歧义 {len(ambiguous)}  未匹配 {len(unmatched)}")

    print("[4] 提取唯一匹配 -> wav...")
    os.makedirs(OUT_WAV, exist_ok=True)
    ok = 0
    mapping = []
    for k, (v, sr, fids) in unique.items():
        lo = fids[0]
        base = os.path.splitext(os.path.basename(v.get("path", "")))[0] or str(k)
        wav_name = f"{base}__{k}.wav"
        wav_path = os.path.join(OUT_WAV, wav_name)
        if not os.path.isfile(wav_path):
            # 找到该 lo 对应的 off/sz
            off = sz = None
            for e_lo, e_sz, e_off, e_lang in entries:
                if e_lo == lo:
                    off, sz = e_off, e_sz
                    break
            if off is None:
                continue
            wem = extract_wem(off, sz, lo)
            wem_tmp = os.path.join(OUT_WAV, f"_tmp_{lo}.wem")
            with open(wem_tmp, "wb") as f:
                f.write(wem)
            subprocess.run([VGSTREAM, "-o", wav_path, wem_tmp], capture_output=True, timeout=120)
            try:
                os.remove(wem_tmp)
            except OSError:
                pass
        if os.path.isfile(wav_path):
            ok += 1
        mapping.append({"key": k, "path": v.get("path"), "wavDuration": v.get("wavDuration"), "voType": v.get("voType"), "fid": lo, "wav": wav_name})

    print(f"    转 wav 完成: {ok} 个 -> {OUT_WAV}")

    with open(MAPPING, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    with open(AMBIGUOUS, "w", encoding="utf-8") as f:
        json.dump([{"key": k, "path": v[0].get("path"), "wavDuration": v[0].get("wavDuration"), "fids": v[2]} for k, v in ambiguous.items()], f, ensure_ascii=False, indent=2)
    with open(UNMATCHED, "w", encoding="utf-8") as f:
        json.dump([{"key": k, "path": v.get("path"), "wavDuration": v.get("wavDuration"), "voType": v.get("voType"), "isPlaceholder": v.get("isPlaceholder")} for k, v in unmatched], f, ensure_ascii=False, indent=2)

    print(f"    完成。映射 -> {MAPPING}，歧义 -> {AMBIGUOUS}，未匹配 -> {UNMATCHED}")


if __name__ == "__main__":
    main()
