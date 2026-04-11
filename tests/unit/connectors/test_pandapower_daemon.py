"""Tests for the pandapower connector REST daemon.

Spec mirror of ``test_opendss_daemon.py``: same REST contract from
``docs/detailed_design/03b_usecase_classes.md`` §3.5.6.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest

pp = pytest.importorskip("pandapower")

from gridflow.connectors.pandapower import build_daemon  # noqa: E402
from gridflow.domain.error import PackNotFoundError  # noqa: E402
from gridflow.domain.scenario import PackMetadata, PackStatus, ScenarioPack  # noqa: E402


def _make_pack(pack_id: str = "ieee30_pp@1.0.0", pp_network: str = "case_ieee30") -> ScenarioPack:
    from gridflow.domain.util.params import as_params

    name, version = pack_id.split("@")
    meta = PackMetadata(
        name=name,
        version=version,
        description="t",
        author="t",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="pandapower",
        parameters=as_params({"pp_network": pp_network}),
    )
    return ScenarioPack(
        pack_id=pack_id,
        name=name,
        version=version,
        metadata=meta,
        network_dir=Path("/tmp"),
        timeseries_dir=Path("/tmp"),
        config_dir=Path("/tmp"),
    )


class _FakeRegistry:
    def __init__(self, packs: dict[str, ScenarioPack] | None = None) -> None:
        self._packs = dict(packs or {})

    def register(self, pack: ScenarioPack) -> ScenarioPack:
        self._packs[pack.pack_id] = pack
        return pack

    def get(self, pack_id: str) -> ScenarioPack:
        if pack_id not in self._packs:
            raise PackNotFoundError(
                f"pack_id '{pack_id}' not found",
                context={"pack_id": pack_id},
            )
        return self._packs[pack_id]

    def list_all(self) -> tuple[ScenarioPack, ...]:
        return tuple(self._packs.values())

    def update_status(self, pack_id: str, new_status: PackStatus) -> ScenarioPack:
        return self._packs[pack_id]

    def delete(self, pack_id: str) -> None:
        del self._packs[pack_id]


def _start_daemon(
    *,
    registry: Any = None,
) -> tuple[Any, threading.Thread, tuple[str, int]]:
    daemon = build_daemon(
        host="127.0.0.1",
        port=0,
        registry=registry or _FakeRegistry(),
    )
    thread = threading.Thread(target=daemon.serve_forever, daemon=True)
    thread.start()
    host, port = daemon.server_address[0], daemon.server_address[1]
    return daemon, thread, (host, port)


def _stop_daemon(daemon: Any, thread: threading.Thread) -> None:
    daemon.shutdown()
    daemon.server_close()
    thread.join(timeout=2)


@pytest.fixture
def running_daemon() -> Iterator[tuple[str, int]]:
    daemon, thread, addr = _start_daemon()
    try:
        yield addr
    finally:
        _stop_daemon(daemon, thread)


def _http_post(
    host: str,
    port: int,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"http://{host}:{port}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        payload: dict[str, Any] = {}
        raw = exc.read().decode("utf-8")
        if raw:
            payload = json.loads(raw)
        return exc.code, payload


class TestPandaPowerDaemonHealth:
    def test_health(self, running_daemon: tuple[str, int]) -> None:
        host, port = running_daemon
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as resp:
            assert resp.status == HTTPStatus.OK
            payload = json.loads(resp.read().decode())
        assert payload["healthy"] is True
        assert "pandapower" in payload["message"]


class TestPandaPowerDaemonLifecycle:
    def test_full_round_trip(self) -> None:
        pack = _make_pack(pp_network="case_ieee30")
        registry = _FakeRegistry({pack.pack_id: pack})
        daemon, thread, (host, port) = _start_daemon(registry=registry)
        try:
            status, _ = _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            assert status == HTTPStatus.OK

            status, body = _http_post(host, port, "/execute", {"step": 0, "context": []})
            assert status == HTTPStatus.OK
            assert body["status"] == "success"
            assert body["node_result"]["voltages"]
            assert all(0.9 < v < 1.1 for v in body["node_result"]["voltages"])

            status, _ = _http_post(host, port, "/teardown", {})
            assert status == HTTPStatus.OK
        finally:
            _stop_daemon(daemon, thread)

    def test_initialize_unknown_pack_returns_422(self) -> None:
        daemon, thread, (host, port) = _start_daemon(registry=_FakeRegistry())
        try:
            status, body = _http_post(host, port, "/initialize", {"pack_id": "missing@1.0.0"})
            assert status == HTTPStatus.UNPROCESSABLE_ENTITY
            assert body["error_code"] == "E-10002"
        finally:
            _stop_daemon(daemon, thread)

    def test_execute_before_initialize_returns_409(self) -> None:
        daemon, thread, (host, port) = _start_daemon()
        try:
            status, body = _http_post(host, port, "/execute", {"step": 0, "context": []})
            assert status == HTTPStatus.CONFLICT
            assert body["error_code"] == "E-30006"
        finally:
            _stop_daemon(daemon, thread)
