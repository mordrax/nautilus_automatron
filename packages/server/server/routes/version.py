"""Route for backend version and health ping."""

from fastapi import APIRouter

VERSION = "0.0.2"

router = APIRouter()


@router.get("/version")
def get_version() -> dict[str, str]:
    return {"version": VERSION}


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
