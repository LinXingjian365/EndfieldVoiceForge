from fastapi import APIRouter

from ..core import jobs as jobmgr
from ..core import paths, tts_engine

router = APIRouter(tags=["status"])


def gpu_info():
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        free, total = torch.cuda.mem_get_info(0)
        return {"name": torch.cuda.get_device_name(0), "total": total, "used": total - free, "free": free}
    except Exception:
        return None


@router.get("/status")
def status():
    eng = tts_engine.get()
    running = sum(1 for j in jobmgr.all_jobs() if j.status == "running")
    return {
        "gpu": gpu_info(),
        "engine": eng.describe(),
        "character": eng.character_id,
        "jobs": {"running": running, "total": len(jobmgr.all_jobs())},
        "version": paths.VERSION,
    }
