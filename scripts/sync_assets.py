"""按 assets.manifest.json 把解包出的 PNG 从 EndfieldUnpacker/_fullmap 拷到 assets/。

assets/ 不入库。用法:python scripts/sync_assets.py
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config

FULLMAP = os.path.join(config.UNPACKER_DIR, "_fullmap")
SOURCES = [os.path.join(FULLMAP, "Sprite"), os.path.join(FULLMAP, "Texture2D")]
DEST = os.path.join(ROOT, "assets")


def find(name):
    for d in SOURCES:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def main():
    manifest = json.load(open(os.path.join(ROOT, "assets.manifest.json"), encoding="utf-8"))
    copied = missing = 0
    for group, names in manifest.items():
        if group.startswith("_"):
            continue
        out = os.path.join(DEST, group)
        os.makedirs(out, exist_ok=True)
        for n in names:
            src = find(n)
            if not src:
                print("MISSING", group, n)
                missing += 1
                continue
            shutil.copy2(src, os.path.join(out, n))
            copied += 1
    print(f"copied {copied}, missing {missing} -> {DEST}")


if __name__ == "__main__":
    main()
