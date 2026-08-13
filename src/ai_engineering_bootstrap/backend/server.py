"""Dependency-free HTTP server for the stable backend and GUI."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from ai_engineering_bootstrap.backend import ApplicationBackend


class BackendRequestHandler(BaseHTTPRequestHandler):
    """Serve versioned backend APIs and the local GUI."""

    backend = ApplicationBackend()
    gui_root = Path(__file__).resolve().parents[1] / "gui" / "static"
    server_instance: ThreadingHTTPServer | None = None

    def _write(self, status: int, payload: dict, content_type: str = "application/json") -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _result(self, result: object) -> None:
        status_name = getattr(result, "status", "ok")
        status_code = {"ok": 200, "rejected": 403, "bad_request": 400, "not_found": 404, "conflict": 409, "failed": 500}.get(status_name, 500)
        self._write(status_code, {
            "status": status_name,
            "request_id": getattr(result, "request_id", ""),
            "api_version": self.backend.VERSION,
            "data": getattr(result, "data", {}),
        })

    def do_OPTIONS(self) -> None:
        self._write(204, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        routes = {
            "/api/v1/health": self.backend.health,
            "/api/v1/audit": self.backend.audit,
            "/api/v1/plan": self.backend.plan,
            "/api/v1/engineering": self.backend.engineering,
        }
        if path in routes:
            try:
                self._result(routes[path]())
            except Exception as exc:  # noqa: BLE001
                self._write(500, {"status": "error", "error": str(exc)})
            return
        if path.startswith("/api/v1/bootstrap-sessions/"):
            session_id = path.rsplit("/", 1)[-1]
            self._result(self.backend.session(session_id))
            return
        if path in {"/", "/index.html"}:
            index = self.gui_root / "index.html"
            if not index.is_file():
                self._write(404, {"status": "error", "error": "GUI asset not found"})
                return
            body = index.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._write(404, {"status": "error", "error": "Endpoint not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/v1/run-safe":
                self._result(self.backend.run_safe())
                return
            if path == "/api/v1/bootstrap-safe":
                self._result(self.backend.bootstrap_safe())
                return
            if path == "/api/v1/run-real":
                self._result(self.backend.run_real_requires_cli())
                return
            if path == "/api/v1/bootstrap-sessions":
                self._result(self.backend.start_bootstrap_session())
                return
            if path == "/api/v1/shutdown":
                self._result(self.backend.stop_server(self.server))
                return
            marker = "/api/v1/bootstrap-sessions/"
            if path.startswith(marker):
                suffix = path[len(marker):]
                parts = suffix.split("/")
                if len(parts) == 4 and parts[1] == "actions" and parts[3] in {"approve", "reject"}:
                    try:
                        action_index = int(parts[2])
                    except ValueError:
                        self._write(400, {"status": "bad_request", "error": "Action index must be an integer."})
                        return
                    result = self.backend.resolve_action(
                        parts[0],
                        action_index,
                        parts[3] == "approve",
                    )
                    self._result(result)
                    return
        except Exception as exc:  # noqa: BLE001
            self._write(500, {"status": "error", "error": str(exc)})
            return
        self._write(404, {"status": "error", "error": "Endpoint not found"})

    def log_message(self, format: str, *args: object) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    """Run the stable backend and local GUI."""
    server = ThreadingHTTPServer((host, port), BackendRequestHandler)
    BackendRequestHandler.server_instance = server
    print(f"AI Engineering Bootstrap: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
