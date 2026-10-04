"""Chrome Native Messaging host: relay framed messages to the app broker."""
from __future__ import annotations

import json
import os
import socket
import struct
import sys
import threading
from pathlib import Path

EXTENSION_ORIGIN = "chrome-extension://kkpfdbnghmplegmilfkkahempcckmefe/"
MAX_MESSAGE = 1_000_000


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_native(stream):
    header = _read_exact(stream, 4)
    if header is None:
        return None
    size = struct.unpack("<I", header)[0]
    if size > MAX_MESSAGE:
        raise ValueError("native_message_too_large")
    body = _read_exact(stream, size)
    if body is None:
        return None
    return body


def _write_native(stream, payload, lock):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_MESSAGE:
        body = json.dumps({"type": "error", "error_code": "response_too_large"}).encode("utf-8")
    with lock:
        stream.write(struct.pack("<I", len(body)))
        stream.write(body)
        stream.flush()


def _main():
    if len(sys.argv) < 2 or sys.argv[1] != EXTENSION_ORIGIN:
        return 2
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    config_path = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "AgentePessoal" / "browser-bridge.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        connection = socket.create_connection((config["host"], int(config["port"])), timeout=5)
        connection.settimeout(None)
        reader = connection.makefile("rb")
        writer = connection.makefile("wb")
        writer.write((json.dumps({"type": "hello", "token": config["token"]}) + "\n").encode("utf-8"))
        writer.flush()
        hello = reader.readline(MAX_MESSAGE + 1)
        if json.loads(hello.decode("utf-8")).get("type") != "ready":
            return 3
        _write_native(sys.stdout.buffer, {"type": "ready"}, threading.Lock())
    except Exception as exc:
        sys.stderr.write("browser native host: " + type(exc).__name__ + "\n")
        return 4
    write_lock = threading.Lock()
    stop = threading.Event()

    def from_broker():
        try:
            while not stop.is_set():
                raw = reader.readline(MAX_MESSAGE + 1)
                if not raw or len(raw) > MAX_MESSAGE:
                    break
                _write_native(sys.stdout.buffer, json.loads(raw.decode("utf-8")), write_lock)
        except Exception:
            pass
        finally:
            stop.set()

    thread = threading.Thread(target=from_broker, daemon=True)
    thread.start()
    try:
        while not stop.is_set():
            body = _read_native(sys.stdin.buffer)
            if body is None:
                break
            message = json.loads(body.decode("utf-8"))
            writer.write((json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
            writer.flush()
    except Exception as exc:
        sys.stderr.write("browser native host: " + type(exc).__name__ + "\n")
    finally:
        stop.set()
        connection.close()
        thread.join(timeout=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
