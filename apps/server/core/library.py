"""生成历史(sqlite)。"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager

from . import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character TEXT NOT NULL,
  text TEXT NOT NULL,
  ref_audio TEXT,
  prompt_text TEXT,
  gpt TEXT,
  sovits TEXT,
  params TEXT,
  wav TEXT NOT NULL,
  duration REAL,
  seed INTEGER,
  elapsed REAL,
  favorite INTEGER DEFAULT 0,
  tags TEXT DEFAULT '[]',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gen_char ON generations(character, id DESC);
"""


@contextmanager
def conn():
    c = sqlite3.connect(paths.LIBRARY_DB)
    c.row_factory = sqlite3.Row
    try:
        c.executescript(SCHEMA)
        yield c
        c.commit()
    finally:
        c.close()


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["params"] = json.loads(d["params"] or "{}")
    d["tags"] = json.loads(d["tags"] or "[]")
    d["favorite"] = bool(d["favorite"])
    return d


def add(**kw) -> dict:
    kw.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
    kw["params"] = json.dumps(kw.get("params") or {}, ensure_ascii=False)
    kw["tags"] = json.dumps(kw.get("tags") or [], ensure_ascii=False)
    cols = ", ".join(kw)
    qs = ", ".join("?" for _ in kw)
    with conn() as c:
        cur = c.execute(f"INSERT INTO generations ({cols}) VALUES ({qs})", list(kw.values()))
        return _row(c.execute("SELECT * FROM generations WHERE id=?", (cur.lastrowid,)).fetchone())


def list_(character: str | None = None, favorite: bool | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    where, args = [], []
    if character:
        where.append("character=?")
        args.append(character)
    if favorite is not None:
        where.append("favorite=?")
        args.append(int(favorite))
    sql = "SELECT * FROM generations" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT ? OFFSET ?"
    with conn() as c:
        return [_row(r) for r in c.execute(sql, [*args, limit, offset]).fetchall()]


def get(gid: int) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM generations WHERE id=?", (gid,)).fetchone()
        return _row(r) if r else None


def update(gid: int, **kw) -> dict | None:
    if "tags" in kw:
        kw["tags"] = json.dumps(kw["tags"], ensure_ascii=False)
    if "favorite" in kw:
        kw["favorite"] = int(bool(kw["favorite"]))
    sets = ", ".join(f"{k}=?" for k in kw)
    with conn() as c:
        c.execute(f"UPDATE generations SET {sets} WHERE id=?", [*kw.values(), gid])
    return get(gid)


def delete(gid: int, remove_file: bool = True) -> bool:
    g = get(gid)
    if not g:
        return False
    with conn() as c:
        c.execute("DELETE FROM generations WHERE id=?", (gid,))
    if remove_file:
        p = paths.resolve(g["wav"])
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass
    return True
