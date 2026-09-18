"""受限文件读取:只允许仓库根与 EndfieldUnpacker 之下,用于试听 wav / 预览。"""
import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..core import paths

router = APIRouter(tags=["files"])


@router.get("/files")
def get_file(path: str = Query(..., description="绝对路径或相对仓库根的路径")):
    ap = paths.resolve(path)
    if not paths.is_safe(ap):
        raise HTTPException(403, "path outside allowed roots")
    if not os.path.isfile(ap):
        raise HTTPException(404, "file not found")
    return FileResponse(ap)
