"""子进程任务管理:启动、行缓冲日志、SSE 订阅、取消。

训练/数据处理类工作全部走这里(GPT-SoVITS 脚本靠环境变量传参且各自吃满显存,不能进程内跑)。
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from . import paths


@dataclass
class Job:
    id: str
    kind: str
    title: str
    cmd: list[str]
    cwd: str
    env: dict[str, str]
    meta: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"  # queued | running | done | failed | cancelled
    started_at: float | None = None
    ended_at: float | None = None
    exit_code: int | None = None
    lines: deque[str] = field(default_factory=lambda: deque(maxlen=4000))
    _proc: subprocess.Popen | None = field(default=None, repr=False)
    _subs: list[asyncio.Queue] = field(default_factory=list, repr=False)
    _loop: asyncio.AbstractEventLoop | None = field(default=None, repr=False)
    log_path: str = ""

    def public(self, tail: int = 30) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "status": self.status,
            "cmd": self.cmd,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "meta": self.meta,
            "tail": list(self.lines)[-tail:],
        }

    def _emit(self, ev: dict):
        if not self._loop:
            return
        for q in list(self._subs):
            self._loop.call_soon_threadsafe(q.put_nowait, ev)


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def all_jobs() -> list[Job]:
    return sorted(_jobs.values(), key=lambda j: j.started_at or 0, reverse=True)


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def running_of_kind(kind: str) -> Job | None:
    for j in _jobs.values():
        if j.kind == kind and j.status == "running":
            return j
    return None


def launch(kind: str, title: str, cmd: list[str], cwd: str, env: dict[str, str] | None = None, meta: dict | None = None) -> Job:
    job = Job(
        id=uuid.uuid4().hex[:12],
        kind=kind,
        title=title,
        cmd=cmd,
        cwd=cwd,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", **(env or {})},
        meta=meta or {},
    )
    job.log_path = os.path.join(paths.JOBS_LOG_DIR, f"{job.id}.log")
    try:
        job._loop = asyncio.get_running_loop()
    except RuntimeError:
        job._loop = None
    with _lock:
        _jobs[job.id] = job
    threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job


def _run(job: Job):
    job.status = "running"
    job.started_at = time.time()
    job._emit({"type": "status", "status": job.status})
    try:
        with open(job.log_path, "w", encoding="utf-8") as logf:
            logf.write("$ " + " ".join(job.cmd) + "\n")
            job._proc = subprocess.Popen(
                job.cmd,
                cwd=job.cwd,
                env=job.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            assert job._proc.stdout
            for line in job._proc.stdout:
                line = line.rstrip("\r\n")
                if not line:
                    continue
                job.lines.append(line)
                logf.write(line + "\n")
                job._emit({"type": "line", "line": line})
            job.exit_code = job._proc.wait()
    except Exception as e:  # noqa: BLE001
        job.lines.append(f"[jobs] launch error: {e}")
        job.exit_code = -1
    job.ended_at = time.time()
    if job.status != "cancelled":
        job.status = "done" if job.exit_code == 0 else "failed"
    job._emit({"type": "status", "status": job.status, "exit_code": job.exit_code})
    job._emit({"type": "end"})


def cancel(job_id: str) -> bool:
    job = _jobs.get(job_id)
    if not job or job.status != "running" or not job._proc:
        return False
    job.status = "cancelled"
    try:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(job._proc.pid)], capture_output=True)
    except Exception:
        job._proc.kill()
    return True


def subscribe(job: Job) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    if job._loop is None:
        job._loop = asyncio.get_running_loop()
    job._subs.append(q)
    return q


def unsubscribe(job: Job, q: asyncio.Queue):
    if q in job._subs:
        job._subs.remove(q)
