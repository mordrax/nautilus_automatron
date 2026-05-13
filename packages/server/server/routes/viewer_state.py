"""Routes for per-run viewer state (indicator selections, etc.)."""

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from server.routes.dependencies import _store_path
from server.schemas import IndicatorInstance

router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ViewerState(BaseModel):
    indicators: list[IndicatorInstance] = Field(default_factory=list)
    detectors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_dir(store_path: Path, run_id: str) -> Path:
    base = store_path.resolve() / "backtest"
    run_dir = (base / run_id).resolve()
    if not run_dir.is_relative_to(base):
        raise HTTPException(status_code=400, detail="Invalid run_id")
    return run_dir


def _run_exists(run_dir: Path) -> bool:
    """A run dir is considered valid if it contains config.json."""
    return (run_dir / "config.json").exists()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}/viewer-state")
def get_viewer_state(
    run_id: str,
    store_path: Path = Depends(_store_path),
) -> dict[str, Any]:
    """Read viewer_state.json for the given run.

    Returns {"indicators": []} if the file doesn't exist but the run dir does.
    Returns 404 if the run dir doesn't exist.
    """
    run_dir = _run_dir(store_path, run_id)

    if not _run_exists(run_dir):
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    state_file = run_dir / "viewer_state.json"
    if not state_file.exists():
        return {"indicators": [], "detectors": []}

    with open(state_file) as f:
        raw = json.load(f)
    state = ViewerState(**raw)
    return state.model_dump()


@router.put("/runs/{run_id}/viewer-state", status_code=204)
def put_viewer_state(
    run_id: str,
    body: ViewerState,
    store_path: Path = Depends(_store_path),
) -> Response:
    """Atomically write viewer_state.json for the given run.

    Writes to viewer_state.json.tmp then renames to viewer_state.json.
    Returns 204 on success, 404 if the run dir doesn't exist.
    """
    run_dir = _run_dir(store_path, run_id)

    if not _run_exists(run_dir):
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    state_file = run_dir / "viewer_state.json"
    tmp_file = run_dir / "viewer_state.json.tmp"

    # Atomic write: write to .tmp then replace
    with open(tmp_file, "w") as f:
        json.dump(body.model_dump(), f, indent=2)

    os.replace(tmp_file, state_file)

    return Response(status_code=204)
