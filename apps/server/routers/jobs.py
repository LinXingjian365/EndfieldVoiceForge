import asyncio
import json

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..core import jobs as jobmgr

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs():
    return [j.public() for j in jobmgr.all_jobs()]


@router.get("/{job_id}")
def get_job(job_id: str, tail: int = 200):
    j = jobmgr.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    return j.public(tail=tail)


@router.delete("/{job_id}")
def cancel_job(job_id: str):
    if not jobmgr.cancel(job_id):
        raise HTTPException(409, "job not running")
    return {"ok": True}


@router.get("/{job_id}/events")
async def job_events(job_id: str):
    j = jobmgr.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    q = jobmgr.subscribe(j)

    async def gen():
        try:
            # 先补发已有日志与状态
            yield {"data": json.dumps({"type": "snapshot", "job": j.public(tail=400)}, ensure_ascii=False)}
            if j.status in ("done", "failed", "cancelled"):
                yield {"data": json.dumps({"type": "end"})}
                return
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield {"comment": "keepalive"}
                    continue
                yield {"data": json.dumps(ev, ensure_ascii=False)}
                if ev.get("type") == "end":
                    return
        finally:
            jobmgr.unsubscribe(j, q)

    return EventSourceResponse(gen())
