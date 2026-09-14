"""Free, keyless text-to-3D generation through three.ws."""

from __future__ import annotations

import os
import time
from urllib.parse import urljoin

import requests

from .remote_3d import _finish, _save_url, _stem


BASE_URL = os.getenv("THREE_WS_URL", "https://three.ws").rstrip("/")


def _json_response(response: requests.Response, action: str) -> dict:
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "30")
        raise RuntimeError(
            f"three.ws: limite gratuito atingido ao {action}. "
            f"Tente novamente em {retry_after}s."
        )
    if response.status_code == 503:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        raise RuntimeError(
            f"three.ws: serviço temporariamente indisponível ao {action}: {detail}"
        )
    if not response.ok:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        raise RuntimeError(f"three.ws: HTTP {response.status_code} - {detail}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"three.ws retornou JSON inválido ao {action}.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"three.ws retornou uma resposta inválida ao {action}: {payload}")
    return payload


def generate_threews(prompt: str, timeout: int | None = None) -> str:
    """Generate a free draft GLB from one text prompt, without an API key."""
    prompt = (prompt or "").strip()
    if not 3 <= len(prompt) <= 1000:
        raise ValueError("O prompt 3D precisa ter entre 3 e 1000 caracteres.")

    session = requests.Session()
    session.headers["Content-Type"] = "application/json"
    response = session.post(
        f"{BASE_URL}/api/3d/generate",
        json={"prompt": prompt, "format": "glb"},
        timeout=120,
    )
    result = _json_response(response, "iniciar a geração")
    deadline = int(timeout or os.getenv("THREE_WS_TIMEOUT", "600"))
    started = time.monotonic()

    while True:
        state = str(result.get("status", "")).lower()
        if state == "done":
            url = result.get("glbUrl") or result.get("glb_url")
            if not url:
                raise RuntimeError(f"three.ws terminou sem URL do GLB: {result}")
            mesh = _save_url(session, url, _stem("threews"), "three.ws")
            return _finish(mesh, "three.ws (free draft)")
        if state in {"error", "failed", "cancelled", "canceled"}:
            raise RuntimeError(f"three.ws: geração falhou: {result.get('error', result)}")
        if state != "pending":
            raise RuntimeError(f"three.ws retornou um status desconhecido: {result}")
        if time.monotonic() - started >= deadline:
            raise TimeoutError(f"three.ws: geração excedeu {deadline}s")

        wait_seconds = max(1, min(int(result.get("retryAfter", 5)), 60))
        time.sleep(wait_seconds)
        poll_url = result.get("poll")
        if not poll_url:
            job = result.get("job")
            if not job:
                raise RuntimeError(f"three.ws retornou uma fila sem job/poll: {result}")
            poll_url = f"/api/3d/generate?job={job}"
        poll_response = session.get(urljoin(f"{BASE_URL}/", poll_url), timeout=120)
        result = _json_response(poll_response, "consultar a geração")


__all__ = ["generate_threews"]
