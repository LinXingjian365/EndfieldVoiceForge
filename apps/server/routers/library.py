from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import library

router = APIRouter(prefix="/library", tags=["library"])


class Patch(BaseModel):
    favorite: bool | None = None
    tags: list[str] | None = None


@router.get("")
def list_generations(character: str | None = None, favorite: bool | None = None, limit: int = 100, offset: int = 0):
    return library.list_(character, favorite, limit, offset)


@router.get("/{gid}")
def get_generation(gid: int):
    g = library.get(gid)
    if not g:
        raise HTTPException(404)
    return g


@router.patch("/{gid}")
def patch_generation(gid: int, body: Patch):
    kw = {k: v for k, v in body.model_dump().items() if v is not None}
    g = library.update(gid, **kw)
    if not g:
        raise HTTPException(404)
    return g


@router.delete("/{gid}")
def delete_generation(gid: int):
    if not library.delete(gid):
        raise HTTPException(404)
    return {"ok": True}
