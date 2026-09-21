# -*- coding: utf-8 -*-
"""生成新增音频的本地 HTML 预览页(连续试听, 短的在前)。

用法(在 EndfieldVoiceForge 目录):
    third_party\\index-tts\\.venv\\Scripts\\python.exe scripts\\preview_new_audio.py
输出: outputs/preview_new_audio.html (双击打开即可逐个播放)
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "datasets", "typhoea_train", "manifest.json")
OUT = os.path.join(ROOT, "outputs", "preview_new_audio.html")


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    new = [x for x in manifest if x.get("f0") == 0.0 and x.get("voiced") == 0.0]
    new.sort(key=lambda x: x.get("dur", 0))
    print(f"新增条目: {len(new)}")

    items = []
    for x in new:
        dur = x.get("dur", 0)
        path = x.get("path", "")
        wav = x.get("wav", "")
        cls = "short" if dur < 1.0 else ""
        # 相对路径: outputs/ -> datasets/typhoea_train/
        rel = "../datasets/typhoea_train/" + wav
        items.append(
            f'<div class="item {cls}">'
            f'<audio controls preload="none" src="{rel}"></audio>'
            f'<div class="meta"><b>{dur:.2f}s</b> &nbsp;{path}</div>'
            f"</div>"
        )

    short_n = sum(1 for x in new if x.get("dur", 0) < 1.0)
    html = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>新增音频预览</title>
<style>
body{font-family:system-ui,sans-serif;max-width:860px;margin:24px auto;padding:0 16px;background:#111;color:#ddd}
h2{color:#eee}.hint{color:#888;font-size:13px;margin-bottom:16px}
.item{display:flex;align-items:center;gap:14px;padding:8px 10px;border-bottom:1px solid #2a2a2a}
.item audio{flex:0 0 260px}
.item .meta{font-size:13px;color:#aaa}
.item.short{background:#2a1414}.item.short .meta b{color:#ff8888}
</style></head><body>
<h2>新增音频预览（%d 条，短→长）</h2>
<div class="hint">红色底 = &lt;1s 短音频（%d 条），重点听是否是人声而非噪音。点击 ▶ 逐个试听。</div>
%s
</body></html>""" % (len(new), short_n, "\n".join(items))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成: {OUT}")


if __name__ == "__main__":
    main()
