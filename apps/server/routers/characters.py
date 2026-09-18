from fastapi import APIRouter, HTTPException

from ..core import characters

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("")
def list_characters():
    return list(characters.load_all().values())


@router.get("/{cid}")
def get_character(cid: str):
    c = characters.get(cid)
    if not c:
        raise HTTPException(404, f"character {cid} not found")
    return c


@router.post("/reload")
def reload_characters():
    characters.reload()
    return {"count": len(characters.load_all())}
