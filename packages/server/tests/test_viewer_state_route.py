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
    data = resp.json()
    assert data == {"indicators": [], "detectors": []}


def test_get_viewer_state_returns_saved_content(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    # Write a legacy file without the 'detectors' key to verify Pydantic normalisation adds it
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
    # Pydantic normalisation adds detectors: [] for legacy files
    expected = {**state, "detectors": []}
    assert resp.json() == expected


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


# ---------------------------------------------------------------------------
# Path traversal protection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("malicious_id", [
    "../../../etc/passwd",
    "..%2F..%2Fetc%2Fpasswd",
    "../../some-other-run",
])
def test_get_path_traversal_returns_400_or_404(
    backtest_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    malicious_id: str,
):
    """run_id values that escape the backtest directory must not return 200."""
    client = _client(backtest_dir, monkeypatch)
    resp = client.get(f"/api/runs/{malicious_id}/viewer-state")
    assert resp.status_code in (400, 404), (
        f"Expected 400 or 404 for path traversal attempt, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.parametrize("malicious_id", [
    "../../../etc/passwd",
    "../../some-other-run",
])
def test_put_path_traversal_returns_400_or_404(
    backtest_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    malicious_id: str,
):
    """PUT with a path-traversal run_id must not write outside the backtest directory."""
    client = _client(backtest_dir, monkeypatch)
    resp = client.put(
        f"/api/runs/{malicious_id}/viewer-state",
        json={"indicators": []},
    )
    assert resp.status_code in (400, 404), (
        f"Expected 400 or 404 for path traversal attempt, got {resp.status_code}: {resp.text}"
    )


def test_put_empty_body_uses_defaults(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """Both fields have defaults, so a body with no recognised keys succeeds with empty state."""
    client = _client(backtest_dir, monkeypatch)
    resp = client.put(
        f"/api/runs/{run_id}/viewer-state",
        json={"not_indicators": "wrong_shape"},
    )
    # Both fields have defaults — Pydantic accepts the body and returns 204
    assert resp.status_code == 204


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


# ---------------------------------------------------------------------------
# Detectors support
# ---------------------------------------------------------------------------


def test_put_with_detectors_round_trips(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """PUT with both indicators and detectors persists and returns both."""
    payload = {
        "indicators": [{"id": "uuid-1", "type": "SMA", "params": {"period": 20}}],
        "detectors": ["equal_highs_lows", "wick_rejection"],
    }
    client = _client(backtest_dir, monkeypatch)
    put_resp = client.put(f"/api/runs/{run_id}/viewer-state", json=payload)
    assert put_resp.status_code == 204

    get_resp = client.get(f"/api/runs/{run_id}/viewer-state")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["indicators"][0]["id"] == "uuid-1"
    assert data["detectors"] == ["equal_highs_lows", "wick_rejection"]


def test_put_legacy_indicators_only_returns_detectors_empty(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """PUT with only 'indicators' (legacy shape) returns detectors: [] on GET."""
    payload = {"indicators": [{"id": "uuid-2", "type": "EMA", "params": {"period": 12}}]}
    client = _client(backtest_dir, monkeypatch)
    client.put(f"/api/runs/{run_id}/viewer-state", json=payload)

    get_resp = client.get(f"/api/runs/{run_id}/viewer-state")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["detectors"] == []


def test_put_detector_ids_not_validated_against_registry(
    backtest_dir: Path,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """Route accepts arbitrary detector ids — client is responsible for filtering stale ones."""
    payload = {
        "indicators": [],
        "detectors": ["nonexistent_detector_xyz"],
    }
    client = _client(backtest_dir, monkeypatch)
    resp = client.put(f"/api/runs/{run_id}/viewer-state", json=payload)
    assert resp.status_code == 204
