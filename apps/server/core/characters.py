import json
import os
from functools import lru_cache

from . import paths


@lru_cache(maxsize=1)
def load_all() -> dict[str, dict]:
    out = {}
    for fn in sorted(os.listdir(paths.CHARACTERS_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(paths.CHARACTERS_DIR, fn), encoding="utf-8") as f:
                c = json.load(f)
            out[c["id"]] = c
    return out


def get(cid: str) -> dict | None:
    return load_all().get(cid)


def reload():
    load_all.cache_clear()
