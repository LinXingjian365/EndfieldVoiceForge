"""提弗洛斯资料库：分块检索（RAG）。

存储文件 lore/typhoea_chunks.json，结构：
{
  "embed_model": "text-embedding-3-small",
  "chunks": [
    {"id": "...", "text": "...", "source": "sns|archive|sim|meta", "speaker": "...", "embedding": [...]},
    ...
  ]
}

检索用 numpy 余弦相似度（numpy 已在 server 依赖里），不引入向量数据库。
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

import numpy as np

from . import paths


def exists() -> bool:
    return os.path.isfile(paths.LORE_STORE)


@lru_cache(maxsize=1)
def _load() -> dict:
    if not exists():
        return {"embed_model": None, "chunks": []}
    with open(paths.LORE_STORE, encoding="utf-8") as f:
        return json.load(f)


def reload():
    _load.cache_clear()


def count() -> int:
    return len(_load().get("chunks", []))


def ready() -> bool:
    d = _load()
    return bool(d.get("chunks"))


def _norm(v: list[float]) -> np.ndarray:
    a = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(a))
    return a / n if n > 0 else a


def search(query_vec: list[float], top_k: int = 5, min_score: float = 0.0) -> list[dict]:
    """返回 [{text, source, speaker, score}, ...]，按相似度降序。"""
    chunks = _load().get("chunks", [])
    if not chunks:
        return []
    q = _norm(query_vec)
    scored = []
    for c in chunks:
        e = c.get("embedding")
        if not e:
            continue
        score = float(q @ _norm(e))
        if score >= min_score:
            scored.append({"text": c["text"], "source": c.get("source", ""), "speaker": c.get("speaker", ""), "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
