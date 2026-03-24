"""Routes for account state and equity curve."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from server.config import get_settings
from server.store import reader, transforms

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


@router.get("/runs/{run_id}/account")
def get_account(run_id: str, store_path: Path = Depends(_store_path)):
    table = reader.read_account_states(store_path, run_id)
    if table is None:
        raise HTTPException(status_code=404, detail="No account data found")
    return transforms.account_states_to_dicts(table)


@router.get("/runs/{run_id}/equity")
def get_equity(run_id: str, store_path: Path = Depends(_store_path)):
    table = reader.read_account_states(store_path, run_id)
    if table is None:
        raise HTTPException(status_code=404, detail="No account data found")
    states = transforms.account_states_to_dicts(table)
    return transforms.account_states_to_equity(states)
