"""EndfieldVoiceForge API server.

跑在 third_party/index-tts/.venv(Python 3.11 + torch cu128),因为要进程内 import GPT-SoVITS 的 TTS 类。
启动:third_party/index-tts/.venv/Scripts/python.exe -m uvicorn apps.server.main:app --host 127.0.0.1 --port 9890
"""
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core import paths
from .routers import characters, datasets, files, inference, jobs, library, rvc, status, tools, training

app = FastAPI(title="EndfieldVoiceForge", version=paths.VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(paths.ASSETS_DIR, exist_ok=True)
app.mount("/assets", StaticFiles(directory=paths.ASSETS_DIR), name="assets")

for r in (status, characters, files, inference, library, jobs, datasets, tools, training, rvc):
    app.include_router(r.router)


@app.get("/")
def root():
    return {"name": "EndfieldVoiceForge", "version": paths.VERSION, "python": sys.version.split()[0]}
