"""Authenticated loopback broker between the Python agent and Chrome native host."""
from __future__ import annotations

import json
import os
import queue
import secrets
import socket
import socketserver
import threading
from pathlib import Path

from tools.browser_protocol import MAX_MESSAGE_BYTES, normalize_response, request, result


def _config_path() -> Path:
    base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    return base / "AgentePessoal" / "browser-bridge.json"


_shared_bridge_lock = threading.RLock()
_shared_bridge = None
_shared_bridge_users = 0


class _BrokerHandler(socketserver.StreamRequestHandler):
    def handle(self):
        owner = self.server.owner
        try:
            hello = self.rfile.readline(MAX_MESSAGE_BYTES + 1)
            if len(hello) > MAX_MESSAGE_BYTES:
                return
            payload = json.loads(hello.decode("utf-8"))
            if payload.get("type") != "hello" or not secrets.compare_digest(str(payload.get("token", "")), owner.token):
                return
            owner.attach(self)
            self.wfile.write(b"{\"type\":\"ready\"}\n")
            self.wfile.flush()
            while not owner.stopping.is_set():
                raw = self.rfile.readline(MAX_MESSAGE_BYTES + 1)
                if not raw:
                    break
                if len(raw) > MAX_MESSAGE_BYTES:
                    break
                try:
                    message = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if message.get("type") == "response":
                    owner.resolve(message)
        except (OSError, ValueError, TypeError):
            pass
        finally:
            owner.detach(self)


class _BrokerServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    def __init__(self, address, owner):
        self.owner = owner
        super().__init__(address, _BrokerHandler)


class BrowserBridge:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.stopping = threading.Event()
        self._lock = threading.RLock()
        self._send_lock = threading.Lock()
        self._host = None
        self._pending = {}
        self._server = _BrokerServer(("127.0.0.1", 0), self)
        self._thread = threading.Thread(target=self._server.serve_forever, name="browser-broker", daemon=True)
        self._thread.start()
        self.config_path = _config_path()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"host": "127.0.0.1", "port": self._server.server_address[1], "token": self.token}), encoding="utf-8")
        os.replace(temporary, self.config_path)

    def attach(self, handler):
        with self._lock:
            self._host = handler
            self._host_ready = threading.Event()
            self._host_ready.set()
            for pending in self._pending.values():
                pending["event"].set()

    def detach(self, handler):
        with self._lock:
            if self._host is handler:
                self._host = None
                for pending in self._pending.values():
                    pending["event"].set()

    def resolve(self, message):
        request_id = message.get("request_id")
        with self._lock:
            pending = self._pending.get(request_id)
            if pending:
                pending["message"] = message
                pending["event"].set()

    def execute(self, operation: str, arguments: dict | None = None, timeout: float = 30) -> dict:
        try:
            outbound = request(operation, arguments)
        except ValueError as exc:
            return result(operation, "failure", error_code=str(exc))
        pending = {"event": threading.Event(), "message": None}
        with self._lock:
            self._pending[outbound["request_id"]] = pending
            host = self._host
        if host is None:
            with self._lock:
                self._pending.pop(outbound["request_id"], None)
            return result(operation, "setup_needed", request_id=outbound["request_id"], error_code="extension_disconnected", retry_hint="Open the Agente Pessoal extension popup in Chrome and reconnect.")
        try:
            encoded = (json.dumps(outbound, ensure_ascii=False) + "\n").encode("utf-8")
            if len(encoded) > MAX_MESSAGE_BYTES:
                with self._lock:
                    self._pending.pop(outbound["request_id"], None)
                return result(operation, "failure", request_id=outbound["request_id"], error_code="request_too_large")
            with self._send_lock:
                host.wfile.write(encoded)
                host.wfile.flush()
        except OSError:
            return result(operation, "failure", request_id=outbound["request_id"], error_code="extension_disconnected", retry_hint="Reconnect the extension, then inspect the tab again.")
        try:
            pending["event"].wait(max(1.0, min(timeout, 120.0)))
            if pending["message"] is None:
                with self._lock:
                    connected = self._host is not None
                code = "browser_timeout" if connected else "extension_disconnected"
                hint = "Inspect the selected tab and retry only if it is still the intended page." if connected else "Open the extension popup after the app starts, then reconnect."
                return result(operation, "failure", request_id=outbound["request_id"], error_code=code, retry_hint=hint)
            return normalize_response(pending["message"], outbound)
        finally:
            with self._lock:
                self._pending.pop(outbound["request_id"], None)

    def close(self):
        self.stopping.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        try:
            current = json.loads(self.config_path.read_text(encoding="utf-8"))
            if secrets.compare_digest(str(current.get("token", "")), self.token):
                self.config_path.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


def acquire_shared_browser_bridge():
    global _shared_bridge, _shared_bridge_users
    with _shared_bridge_lock:
        if _shared_bridge is None or _shared_bridge.stopping.is_set():
            _shared_bridge = BrowserBridge()
            _shared_bridge_users = 0
        _shared_bridge_users += 1
        return _shared_bridge


def release_shared_browser_bridge(bridge):
    global _shared_bridge, _shared_bridge_users
    close_bridge = None
    with _shared_bridge_lock:
        if bridge is _shared_bridge:
            _shared_bridge_users = max(0, _shared_bridge_users - 1)
            if _shared_bridge_users == 0:
                close_bridge = _shared_bridge
                _shared_bridge = None
        else:
            close_bridge = bridge
    if close_bridge is not None:
        close_bridge.close()
