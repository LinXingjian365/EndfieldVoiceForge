"""日志查询：供「日志」页定位问题，可复制后随反馈一起提交。"""
from __future__ import annotations

from fastapi import APIRouter

from ..core import log

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
def get_logs(lines: int = 200):
    return {"logs": log.recent(lines)}
