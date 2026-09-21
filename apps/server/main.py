"""EndfieldVoiceForge API server.

跑在 third_party/index-tts/.venv(Python 3.11 + torch cu128),因为要进程内 import GPT-SoVITS 的 TTS 类。
启动:third_party/index-tts/.venv/Scripts/python.exe -m uvicorn apps.server.main:app --host 127.0.0.1 --port 9890
"""
import os
import sys
import mimetypes

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core import jobs as jobmgr, paths
from .routers import characters, chat, config, datasets, files, inference, jobs, library, logs, rvc, status, system, tools, training

app = FastAPI(title="EndfieldVoiceForge", version=paths.VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _recover_training():
    """重启 server 后重新挂载仍在运行的 detached 训练进程(避免训练中断)。"""
    try:
        n = jobmgr.recover()
        if n:
            print(f"[jobs] recovered {n} detached training job(s)")
    except Exception as e:  # noqa: BLE001
        print(f"[jobs] recover failed: {e}")

os.makedirs(paths.ASSETS_DIR, exist_ok=True)
# Windows 上 Python 的 mimetypes 会把 .svg 认成 image/svg(错误),浏览器不认;强制纠正。
mimetypes.add_type("image/svg+xml", ".svg")
app.mount("/assets", StaticFiles(directory=paths.ASSETS_DIR), name="assets")

for r in (status, characters, files, inference, library, jobs, datasets, tools, training, rvc, chat, config, system, logs):
    app.include_router(r.router)


@app.get("/")
def root():
    return {"name": "EndfieldVoiceForge", "version": paths.VERSION, "python": sys.version.split()[0]}
