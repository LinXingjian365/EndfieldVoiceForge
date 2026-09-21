# -*- coding: utf-8 -*-
"""生成「自包含」音频预览页(音频 base64 内嵌, 单文件, 可传到手机离线试听)。

只收短音频(<1.5s, 重点是 <1s 的 33 条), 降采样到 24k 单声道以控制体积。
用法:
    third_party\\index-tts\\.venv\\Scripts\\python.exe scripts\\preview_new_audio_standalone.py
输出: outputs/preview_new_audio_standalone.html
"""
from __future__ import annotations

import base64
import io
import json
import os

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "datasets", "typhoea_train", "manifest.json")
TRAIN_DIR = os.path.join(ROOT, "datasets", "typhoea_train")
OUT = os.path.join(ROOT, "outputs", "preview_new_audio_standalone.html")

MAX_DUR = 1.5
TARGET_SR = 24000


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    new = [x for x in manifest if x.get("f0") == 0.0 and x.get("voiced") == 0.0]
    short = sorted([x for x in new if x.get("dur", 0) < MAX_DUR], key=lambda x: x.get("dur", 0))
    print(f"短音频(<{MAX_DUR}s): {len(short)} 条")

    items = []
    total_bytes = 0
    for x in short:
        wav = os.path.join(TRAIN_DIR, x.get("wav", ""))
        if not os.path.isfile(wav):
            continue
        y, sr = sf.read(wav, dtype="float32")
        if y.ndim > 1:
            y = y.mean(axis=1)
        # 降采样到 24k
        if sr != TARGET_SR:
            n = int(len(y) * TARGET_SR / sr)
            idx = np.linspace(0, len(y) - 1, n).astype(int)
            y = y[idx]
        buf = io.BytesIO()
        sf.write(buf, y, TARGET_SR, format="WAV", subtype="PCM_16")
        b64 = base64.b64encode(buf.getvalue()).decode()
        total_bytes += len(buf.getvalue())
        dur = x.get("dur", 0)
        path = x.get("path", "")
        cls = "short" if dur < 1.0 else ""
        items.append(
            f'<div class="item {cls}">'
            f'<audio controls preload="none" src="data:audio/wav;base64,{b64}"></audio>'
            f'<div class="meta"><b>{dur:.2f}s</b> &nbsp;{path}</div>'
            f"</div>"
        )

    short_n = sum(1 for x in short if x.get("dur", 0) < 1.0)
    html = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>短音频预览</title>
<style>
body{font-family:system-ui,sans-serif;max-width:100%%;margin:0;padding:12px;background:#111;color:#ddd}
h2{color:#eee;font-size:17px}.hint{color:#888;font-size:12px;margin-bottom:12px}
.item{display:flex;flex-direction:column;gap:4px;padding:8px 6px;border-bottom:1px solid #2a2a2a}
.item audio{width:100%%}
.item .meta{font-size:12px;color:#aaa}
.item.short{background:#2a1414}.item.short .meta b{color:#ff8888}
</style></head><body>
<h2>短音频预览（%d 条，短→长）</h2>
<div class="hint">红底 = &lt;1s（%d 条）。全部离线内嵌，无需联网。逐个点 ▶ 听是否人声而非噪音。</div>
%s
</body></html>""" % (len(short), short_n, "\n".join(items))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f"已生成: {OUT}")
    print(f"文件大小: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
