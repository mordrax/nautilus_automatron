"""Tests for the viewer-state sidecar routes.

GET /api/runs/{run_id}/viewer-state
PUT /api/runs/{run_id}/viewer-state
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.main import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def run_id() -> str:
    return "test-run-00000000-0000-0000-0000-000000000001"


@pytest.fixture
def backtest_dir(tmp_path: Path, run_id: str) -> Path:
    """Create a minimal run dir with config.json inside a backtest subdir."""
    run_dir = tmp_path / "backtest" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "config.json").write_text('{"strategy": "test"}')
    return tmp_path


def _client(store_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a test client with NAUTILUS_STORE_PATH pointing at store_path."""
    monkeypatch.setenv("NAUTILUS_STORE_PATH", str(store_path))
    app = create_app()
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET — happy path
# ---------------------------------------------------------------------------


def test_get_viewer_state_returns_empty_default_when_file_missing(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    client = _client(backtest_dir, monkeypatch)
    resp = client.get(f"/api/runs/{run_id}/viewer-state")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"indicators": []}


def test_get_viewer_state_returns_saved_content(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    state = {
        "indicators": [
            {"id": "uuid-1", "type": "SMA", "params": {"period": 20}},
        ]
    }
    state_file = backtest_dir / "backtest" / run_id / "viewer_state.json"
    state_file.write_text(json.dumps(state))

    client = _client(backtest_dir, monkeypatch)
    resp = client.get(f"/api/runs/{run_id}/viewer-state")
    assert resp.status_code == 200, resp.text
    assert resp.json() == state


# ---------------------------------------------------------------------------
# PUT — happy path
# ---------------------------------------------------------------------------


def test_put_viewer_state_returns_204(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    client = _client(backtest_dir, monkeypatch)
    resp = client.put(
        f"/api/runs/{run_id}/viewer-state",
        json={"indicators": []},
    )
    assert resp.status_code == 204


def test_put_then_get_round_trips(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    payload = {
        "indicators": [
            {"id": "uuid-abc", "type": "EMA", "params": {"period": 12}},
            {"id": "uuid-def", "type": "ZigZag", "params": {"threshold": 0.05}},
        ]
    }
    client = _client(backtest_dir, monkeypatch)

    put_resp = client.put(f"/api/runs/{run_id}/viewer-state", json=payload)
    assert put_resp.status_code == 204

    get_resp = client.get(f"/api/runs/{run_id}/viewer-state")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert len(data["indicators"]) == 2
    assert data["indicators"][0]["id"] == "uuid-abc"
    assert data["indicators"][1]["type"] == "ZigZag"


def test_put_no_tmp_file_remains(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    client = _client(backtest_dir, monkeypatch)
    client.put(
        f"/api/runs/{run_id}/viewer-state",
        json={"indicators": []},
    )

    tmp_file = backtest_dir / "backtest" / run_id / "viewer_state.json.tmp"
    assert not tmp_file.exists(), ".tmp file should not remain after successful write"


def test_put_overwrites_existing_state(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    client = _client(backtest_dir, monkeypatch)

    # First write
    client.put(
        f"/api/runs/{run_id}/viewer-state",
        json={"indicators": [{"id": "old", "type": "SMA", "params": {"period": 10}}]},
    )

    # Second write with different content
    new_payload = {"indicators": [{"id": "new", "type": "EMA", "params": {"period": 5}}]}
    client.put(f"/api/runs/{run_id}/viewer-state", json=new_payload)

    resp = client.get(f"/api/runs/{run_id}/viewer-state")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["indicators"]) == 1
    assert data["indicators"][0]["id"] == "new"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_get_unknown_run_returns_404(
    backtest_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    client = _client(backtest_dir, monkeypatch)
    resp = client.get("/api/runs/does-not-exist/viewer-state")
    assert resp.status_code == 404


def test_put_unknown_run_returns_404(
    backtest_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    client = _client(backtest_dir, monkeypatch)
    resp = client.put(
        "/api/runs/does-not-exist/viewer-state",
        json={"indicators": []},
    )
    assert resp.status_code == 404


def test_put_malformed_body_returns_422(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """Pydantic validation — body missing 'indicators' field should return 422."""
    client = _client(backtest_dir, monkeypatch)
    resp = client.put(
        f"/api/runs/{run_id}/viewer-state",
        json={"not_indicators": "wrong_shape"},
    )
    # FastAPI returns 422 for Pydantic validation errors
    assert resp.status_code == 422


def test_put_indicators_wrong_type_returns_422(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """Pydantic validation — indicators must be a list, not a string."""
    client = _client(backtest_dir, monkeypatch)
    resp = client.put(
        f"/api/runs/{run_id}/viewer-state",
        json={"indicators": "not-a-list"},
    )
    assert resp.status_code == 422
