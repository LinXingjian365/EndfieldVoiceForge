"""子进程任务管理:启动、行缓冲日志、SSE 订阅、取消。

训练/数据处理类工作全部走这里(GPT-SoVITS 脚本靠环境变量传参且各自吃满显存,不能进程内跑)。

训练类任务用 detached 模式:进程独立于 server 存活(关掉/重启 server 不会打断训练),
日志写文件,server 通过 tail 文件提供实时进度;任务信息持久化到 outputs/jobs/*.json,
server 重启后 recover() 可重新挂载仍在运行的训练进程。
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from . import paths

DETACH_FLAGS = (
    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    | getattr(subprocess, "DETACHED_PROCESS", 0)
    | getattr(subprocess, "CREATE_NO_WINDOW", 0)
)

# 训练类任务(长任务)走 detached 模式,重启 server 不打断
DETACHED_KINDS = ("train:s2", "train:s1", "rvc:train", "rvc:index", "rvc:preprocess")


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
    pid: int | None = None
    detached: bool = False
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
            "pid": self.pid,
            "detached": self.detached,
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
        detached=kind in DETACHED_KINDS,
    )
    job.log_path = os.path.join(paths.JOBS_LOG_DIR, f"{job.id}.log")
    try:
        job._loop = asyncio.get_running_loop()
    except RuntimeError:
        job._loop = None
    with _lock:
        _jobs[job.id] = job
    _persist(job)
    if job.detached:
        threading.Thread(target=_run_detached, args=(job,), daemon=True).start()
    else:
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
    _finalize(job)


def _run_detached(job: Job):
    job.status = "running"
    job.started_at = time.time()
    job._emit({"type": "status", "status": job.status})
    try:
        with open(job.log_path, "w", encoding="utf-8") as logf:
            logf.write("$ " + " ".join(job.cmd) + "\n")
        # 子进程 stdout 直接落到日志文件(不依赖 server 的 pipe),server 挂掉也不影响训练
        log_file = open(job.log_path, "ab")
        job._proc = subprocess.Popen(
            job.cmd,
            cwd=job.cwd,
            env=job.env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=DETACH_FLAGS,
        )
        job.pid = job._proc.pid
        _persist(job)
        _tail_log(job)
        job.exit_code = job._proc.wait()
        log_file.close()
    except Exception as e:  # noqa: BLE001
        job.lines.append(f"[jobs] launch error: {e}")
        job.exit_code = -1
    _finalize(job)


def _tail_log(job: Job):
    """轮询日志文件,把新行喂给内存缓冲 + SSE(实时进度)。"""
    last = 0
    if os.path.isfile(job.log_path):
        last = os.path.getsize(job.log_path)
    while job._proc is not None and job._proc.poll() is None:
        try:
            size = os.path.getsize(job.log_path)
            if size > last:
                with open(job.log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(last)
                    new = f.read()
                last = size
                for line in new.splitlines():
                    if line:
                        job.lines.append(line)
                        job._emit({"type": "line", "line": line})
        except OSError:
            pass
        time.sleep(0.4)
    # 最后一次 drain
    try:
        with open(job.log_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(last)
            new = f.read()
        for line in new.splitlines():
            if line:
                job.lines.append(line)
                job._emit({"type": "line", "line": line})
    except OSError:
        pass


def _finalize(job: Job):
    job.ended_at = time.time()
    if job.status != "cancelled":
        job.status = "done" if job.exit_code == 0 else "failed"
    job._emit({"type": "status", "status": job.status, "exit_code": job.exit_code})
    job._emit({"type": "end"})
    _clear_persist(job)


def cancel(job_id: str) -> bool:
    job = _jobs.get(job_id)
    if not job or job.status != "running":
        return False
    job.status = "cancelled"
    if job._proc and job._proc.pid:
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(job._proc.pid)], capture_output=True)
        except Exception:  # noqa: BLE001
            try:
                job._proc.kill()
            except Exception:  # noqa: BLE001
                pass
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


# ---- 持久化 + 恢复 ----

def _persist_path(job_id: str) -> str:
    return os.path.join(paths.JOBS_LOG_DIR, f"{job_id}.json")


def _persist(job: Job):
    if job.detached and job.pid:
        data = {
            "id": job.id,
            "kind": job.kind,
            "title": job.title,
            "cmd": job.cmd,
            "cwd": job.cwd,
            "pid": job.pid,
            "started_at": job.started_at,
            "meta": job.meta,
        }
        try:
            with open(_persist_path(job.id), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass


def _clear_persist(job: Job):
    try:
        p = _persist_path(job.id)
        if os.path.isfile(p):
            os.remove(p)
    except OSError:
        pass


def recover() -> int:
    """server 启动时调用:重新挂载仍在运行的 detached 训练进程。返回恢复的进程数。"""
    recovered = 0
    if not os.path.isdir(paths.JOBS_LOG_DIR):
        return 0
    try:
        import psutil
    except Exception:  # noqa: BLE001
        psutil = None

    for fn in os.listdir(paths.JOBS_LOG_DIR):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(paths.JOBS_LOG_DIR, fn)
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        pid = data.get("pid")
        alive = False
        if pid:
            if psutil is not None:
                alive = psutil.pid_exists(pid)
            else:
                try:
                    subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
                    alive = True  # 保守起见,无法精确判断就当作还在
                except Exception:  # noqa: BLE001
                    alive = False
        if not alive:
            os.remove(p)
            continue
        # 重建 Job 并挂载
        job = Job(
            id=data["id"],
            kind=data["kind"],
            title=data["title"],
            cmd=data["cmd"],
            cwd=data.get("cwd", paths.ROOT),
            env={},
            meta=data.get("meta", {}),
            status="running",
            started_at=data.get("started_at"),
            pid=pid,
            detached=True,
        )
        job.log_path = os.path.join(paths.JOBS_LOG_DIR, f"{job.id}.log")
        with _lock:
            _jobs[job.id] = job
        threading.Thread(target=_recover_tail, args=(job,), daemon=True).start()
        recovered += 1
    return recovered


def _recover_tail(job: Job):
    """恢复的 detached 进程:先读已有日志,再 tail 新日志直到进程退出。"""
    try:
        import psutil
    except Exception:  # noqa: BLE001
        psutil = None

    def alive() -> bool:
        if psutil is not None:
            try:
                return psutil.pid_exists(job.pid)
            except Exception:  # noqa: BLE001
                return False
        return False

    last = 0
    if os.path.isfile(job.log_path):
        last = os.path.getsize(job.log_path)
        try:
            with open(job.log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f.read().splitlines():
                    if line:
                        job.lines.append(line)
        except OSError:
            pass

    while alive():
        try:
            size = os.path.getsize(job.log_path)
            if size > last:
                with open(job.log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(last)
                    new = f.read()
                last = size
                for line in new.splitlines():
                    if line:
                        job.lines.append(line)
                        job._emit({"type": "line", "line": line})
        except OSError:
            pass
        time.sleep(2)
    job.exit_code = 0
    _finalize(job)
