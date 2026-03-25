"""Route for backend version."""

from fastapi import APIRouter

VERSION = "0.0.2"

router = APIRouter()


@router.get("/version")
def get_version() -> dict[str, str]:
    return {"version": VERSION}
