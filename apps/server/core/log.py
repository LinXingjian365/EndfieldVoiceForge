"""统一日志：写文件 + 内存环形缓冲，供「日志」页查询定位问题。

日志同时落在 outputs/evf.log（供人工排查/随反馈提交），
内存缓冲供 /logs 接口实时读取。
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque

from . import paths

_LOCK = threading.Lock()
_BUF: deque[dict] = deque(maxlen=800)
_LOG_FILE = os.path.join(paths.OUTPUTS_DIR, "evf.log")


def log(level: str, message: str, **fields) -> None:
    entry = {
        "ts": int(time.time() * 1000),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "level": level,
        "message": message,
    }
    entry.update(fields)
    with _LOCK:
        _BUF.append(entry)
        try:
            os.makedirs(os.path.dirname(_LOG_FILE), exist_ok=True)
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass


def recent(n: int = 200) -> list[dict]:
    n = max(1, min(n, 800))
    with _LOCK:
        return list(_BUF)[-n:][::-1]


def info(message: str, **fields) -> None:
    log("info", message, **fields)


def warn(message: str, **fields) -> None:
    log("warn", message, **fields)


def error(message: str, **fields) -> None:
    log("error", message, **fields)
