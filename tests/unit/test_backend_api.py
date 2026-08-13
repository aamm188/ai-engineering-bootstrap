"""Tests for the stable backend service and HTTP boundary."""

import json
from threading import Thread
from urllib.request import urlopen

from ai_engineering_bootstrap.backend.server import BackendRequestHandler, ThreadingHTTPServer
from ai_engineering_bootstrap.backend.service import ApplicationBackend


def test_backend_health_is_versioned_and_identified() -> None:
    result = ApplicationBackend().health()
    assert result.status == "ok"
    assert result.request_id.startswith("req-")
    assert result.data["status"] == "ok"
    assert result.data["version"] == "v1"


def test_backend_exposes_versioned_read_models() -> None:
    backend = ApplicationBackend()
    audit = backend.audit().data
    plan = backend.plan().data
    engineering = backend.engineering().data
    assert "readiness" in audit
    assert "actions" in plan
    assert "tools" in engineering


def test_backend_safe_run_preserves_pipeline_contract() -> None:
    result = ApplicationBackend().run_safe().data
    assert "audit" in result
    assert "plan" in result
    assert "validation" in result
    assert "execution" in result
    assert "verification" in result
    assert "evidence" in result


def test_real_api_is_explicitly_blocked_at_backend_boundary() -> None:
    result = ApplicationBackend().run_real_requires_cli()
    assert result.status == "rejected"
    assert result.data["allowed"] is False
    assert "approve each real action" in result.data["message"]


def test_gui_asset_exists() -> None:
    assert (BackendRequestHandler.gui_root / "index.html").is_file()


def test_http_health_endpoint() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BackendRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["api_version"] == "v1"
        assert payload["data"]["status"] == "ok"
        assert payload["request_id"].startswith("req-")
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def test_http_rejects_unknown_endpoint() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BackendRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        try:
            urlopen(f"http://127.0.0.1:{port}/api/v1/unknown", timeout=3)
        except Exception as exc:
            assert getattr(exc, "code", None) == 404
        else:
            raise AssertionError("Unknown endpoint unexpectedly succeeded")
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def test_gui_unwraps_backend_envelope_and_bootstrap_endpoint_is_present() -> None:
    html = (BackendRequestHandler.gui_root / "index.html").read_text(encoding="utf-8")
    assert "x.data??x" in html
    assert "/api/v1/bootstrap-sessions" in html


def test_gui_handles_backend_errors() -> None:
    html = (BackendRequestHandler.gui_root / "index.html").read_text(encoding="utf-8")
    assert "Backend error:" in html

def test_bootstrap_session_exposes_individual_actions() -> None:
    result = ApplicationBackend().start_bootstrap_session()
    assert result.status == "ok"
    assert result.data["session_id"].startswith("session-")
    assert isinstance(result.data["actions"], list)
    for action in result.data["actions"]:
        assert "action_id" in action
        assert "status" in action
        assert "action_index" in action
        if action["status"] == "pending":
            assert action["approval_id"] is not None


def test_bootstrap_session_rejects_unknown_session() -> None:
    result = ApplicationBackend().session("session-does-not-exist")
    assert result.status == "not_found"


def test_gui_contains_real_bootstrap_controls() -> None:
    html = BackendRequestHandler.gui_root.joinpath("index.html").read_text(encoding="utf-8")
    assert "Start REAL Bootstrap" in html
    assert "Approve & Execute" in html
    assert "Reject" in html
    assert "/api/v1/bootstrap-sessions" in html


def test_bootstrap_session_keeps_duplicate_action_ids_distinct() -> None:
    backend = ApplicationBackend()
    result = backend.start_bootstrap_session()
    data = result.data
    assert result.status == "ok"
    actions = data["actions"]
    indexes = [action["action_index"] for action in actions]
    assert len(indexes) == len(set(indexes))
    for action in actions:
        assert action["status"] in {"pending", "ready", "success", "completed", "rejected", "failed", "executing"}


def test_backend_shutdown_requests_server_shutdown() -> None:
    class FakeServer:
        def __init__(self) -> None:
            self.called = False

        def shutdown(self) -> None:
            self.called = True

    server = FakeServer()
    result = ApplicationBackend.stop_server(server)
    assert result.status == "ok"
    assert result.data["stopped"] is True
