"""系统控制：退出 / 重启 / 反馈 / 联系方式。

退出与重启通过 scripts/system_control.ps1 以 detached 方式执行，
独立于当前 server 进程存活，从而能在杀掉 server 后继续完成重启。
"""
from __future__ import annotations

import json
import os
import subprocess
import time

from fastapi import APIRouter
from pydantic import BaseModel

from ..core import paths

router = APIRouter(prefix="/system", tags=["system"])

_CONTROL_PS1 = os.path.join(paths.ROOT, "scripts", "system_control.ps1")


def _spawn(action: str) -> None:
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", _CONTROL_PS1, "-Action", action],
        cwd=paths.ROOT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


@router.post("/quit")
def quit():
    _spawn("quit")
    return {"ok": True, "message": "服务已停止，可关闭本页。"}


@router.post("/restart")
def restart():
    _spawn("restart")
    return {"ok": True, "message": "正在重启，约 5 秒后恢复，请刷新页面。"}


class FeedbackIn(BaseModel):
    contact: str = ""
    content: str


@router.post("/feedback")
def feedback(fb: FeedbackIn):
    content = (fb.content or "").strip()
    if not content:
        return {"ok": False, "message": "反馈内容为空"}
    os.makedirs(os.path.dirname(paths.FEEDBACK_FILE), exist_ok=True)
    line = {"ts": int(time.time()), "contact": (fb.contact or "").strip(), "content": content}
    with open(paths.FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return {"ok": True, "message": "反馈已提交，感谢！"}


@router.get("/contact")
def contact():
    return paths.CONTACT
