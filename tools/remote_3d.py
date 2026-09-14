"""Hosted 3D generation backends: Hyper3D/Rodin and Trify3D."""

from __future__ import annotations

import base64
import mimetypes
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Use the Windows certificate store when available while keeping TLS
# verification enabled for hosted providers.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import requests


OUTPUT_ROOT = Path.home() / "Pictures" / "AgentePessoal" / "Hosted3D"


def _api_key(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} n\u00e3o configurada no .env")
    return value


def _json_error(response: requests.Response, service: str) -> RuntimeError:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text[:1000]
    if response.status_code == 402:
        message = "cr\u00e9ditos insuficientes"
    elif response.status_code == 429:
        message = "limite de requisi\u00e7\u00f5es atingido"
    else:
        message = str(payload)
    return RuntimeError(f"{service}: HTTP {response.status_code} - {message}")


def _request(session, method: str, url: str, service: str, **kwargs):
    response = session.request(method, url, timeout=60, **kwargs)
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "5")
        try:
            delay = min(max(int(retry_after), 1), 60)
        except ValueError:
            delay = 5
        time.sleep(delay)
        response = session.request(method, url, timeout=60, **kwargs)
    if not response.ok:
        raise _json_error(response, service)
    return response.json()


def _poll(session, status_url: str, payload: dict, service: str, timeout: int):
    started = time.monotonic()
    delay = 5
    while time.monotonic() - started < timeout:
        time.sleep(delay)
        result = _request(session, "POST", status_url, service, json=payload)
        jobs = result.get("jobs", []) if isinstance(result, dict) else []
        if isinstance(jobs, dict):
            jobs = [jobs]
        states = {str(job.get("status", "")).lower() for job in jobs if isinstance(job, dict)}
        if any(state in {"failed", "error", "cancelled", "canceled"} for state in states):
            raise RuntimeError(f"{service}: geração falhou: {result}")
        if jobs and all(state in {"done", "completed", "success", "succeeded"} for state in states):
            return result
        delay = min(delay + 5, 30)
    raise TimeoutError(f"{service}: geração excedeu {timeout}s")


def _save_url(session, url: str, stem: str, service: str) -> Path:
    response = session.get(url, timeout=120)
    if not response.ok:
        raise _json_error(response, service)
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in {".glb", ".gltf", ".obj", ".stl", ".ply"}:
        suffix = ".glb"
    output = OUTPUT_ROOT / f"{stem}{suffix}"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output.write_bytes(response.content)
    return output


def _viewer(mesh: Path) -> Path | None:
    if mesh.suffix.lower() not in {".glb", ".gltf"}:
        return None
    viewer = mesh.with_suffix(".html")
    viewer.write_text(
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Agente Pessoal - Modelo 3D</title>"
        "<script type='module' src='https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js'></script>"
        "<style>html,body{margin:0;height:100%;background:#101114}model-viewer{width:100%;height:100%}</style>"
        "</head><body><model-viewer src='" + mesh.as_uri() + "' camera-controls auto-rotate shadow-intensity='1' exposure='1' environment-image='neutral'></model-viewer></body></html>",
        encoding="utf-8",
    )
    return viewer


def _finish(mesh: Path, service: str) -> str:
    viewer = _viewer(mesh)
    extra = f" Visualizador: {viewer}" if viewer else ""
    return f"Modelo 3D gerado via {service}. Arquivo: {mesh}.{extra}"


def _stem(service: str) -> str:
    return f"{service.lower().replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


def generate_rodin(prompt: str = "", image_path: str | None = None) -> str:
    """Generate text-to-3D or image-to-3D with Hyper3D/Rodin."""
    prompt = (prompt or "").strip()
    image = Path(image_path).expanduser() if image_path else None
    if not prompt and not image:
        raise ValueError("Informe um prompt ou uma imagem para gerar o modelo 3D.")
    if image and not image.is_file():
        raise ValueError(f"Imagem n\u00e3o encontrada: {image}")

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {_api_key('RODIN_API_KEY')}"
    data = {
        "tier": os.getenv("RODIN_TIER", "Gen-2.5-Medium"),
        "mesh_mode": "Raw",
        "quality": os.getenv("RODIN_QUALITY", "medium"),
        "geometry_file_format": "glb",
    }
    if prompt:
        data["prompt"] = prompt
    files = None
    image_file = None
    try:
        if image:
            image_file = image.open("rb")
            content_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
            files = {"images": (image.name, image_file, content_type)}
        result = _request(session, "POST", "https://api.hyper3d.com/api/v2/rodin", "Rodin", data=data, files=files)
    finally:
        if image_file:
            image_file.close()

    task_uuid = result.get("uuid")
    subscription = result.get("jobs", {}).get("subscription_key")
    if not task_uuid or not subscription:
        raise RuntimeError(f"Rodin retornou uma resposta inv\u00e1lida: {result}")
    _poll(session, "https://api.hyper3d.com/api/v2/status", {"subscription_key": subscription}, "Rodin", int(os.getenv("RODIN_TIMEOUT", "1200")))
    downloads = _request(session, "POST", "https://api.hyper3d.com/api/v2/download", "Rodin", json={"task_uuid": task_uuid})
    entries = downloads.get("list", [])
    url = next((item.get("url") for item in entries if str(item.get("name", "")).lower().endswith(".glb")), None)
    url = url or next((item.get("url") for item in entries if item.get("url")), None)
    if not url:
        raise RuntimeError(f"Rodin n\u00e3o retornou URL de download: {downloads}")
    return _finish(_save_url(session, url, _stem("rodin"), "Rodin"), "Rodin")


def _data_url(image: Path) -> str:
    mime = mimetypes.guess_type(image.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(image.read_bytes()).decode("ascii")


def generate_trify(prompt: str = "", image_path: str | None = None) -> str:
    """Generate text-to-3D or image-to-3D with Trify3D."""
    prompt = (prompt or "").strip()
    image = Path(image_path).expanduser() if image_path else None
    if not prompt and not image:
        raise ValueError("Informe um prompt ou uma imagem para gerar o modelo 3D.")
    if image and not image.is_file():
        raise ValueError(f"Imagem n\u00e3o encontrada: {image}")
    key = _api_key("TRIFY3D_API_KEY")
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if image:
        endpoint = "image-to-3d"
        body = {
            "type": "image_to_3d",
            "fileName": image.name,
            "fileSize": image.stat().st_size,
            "fileType": mimetypes.guess_type(image.name)[0] or "image/png",
            "imageDataUrl": _data_url(image),
            "mode": os.getenv("TRIFY3D_MODE", "quality"),
        }
    else:
        endpoint = "text-to-3d"
        body = {"type": "text_to_3d", "prompt": prompt, "style": os.getenv("TRIFY3D_STYLE", "realistic"), "mode": os.getenv("TRIFY3D_MODE", "quality")}
    # The API recommends an idempotency key so a retry cannot create duplicate
    # paid jobs if the connection drops after the server accepted the request.
    session.headers["Idempotency-Key"] = str(uuid.uuid4())
    result = _request(session, "POST", f"https://trify3d.com/api/v1/generations/{endpoint}", "Trify3D", json=body)
    data = result.get("data", result)
    task_id = data.get("taskId") or data.get("id") or data.get("generationId")
    if not task_id:
        raise RuntimeError(f"Trify3D retornou uma resposta inv\u00e1lida: {result}")
    deadline = int(os.getenv("TRIFY3D_TIMEOUT", "1200"))
    started = time.monotonic()
    while time.monotonic() - started < deadline:
        time.sleep(5)
        status_result = _request(session, "GET", f"https://trify3d.com/api/v1/generations/{task_id}", "Trify3D")
        status = status_result.get("data", status_result)
        state = str(status.get("status", "")).lower()
        if state in {"failed", "error", "cancelled", "canceled"}:
            raise RuntimeError(f"Trify3D: geração falhou: {status_result}")
        if state in {"completed", "success", "succeeded", "done"}:
            url = status.get("outputModelUrl") or status.get("modelUrl") or status.get("model_url")
            if not url:
                raise RuntimeError(f"Trify3D terminou sem URL do modelo: {status_result}")
            return _finish(_save_url(session, url, _stem("trify3d"), "Trify3D"), "Trify3D")
    raise TimeoutError(f"Trify3D: geração excedeu {deadline}s")


__all__ = ["generate_rodin", "generate_trify"]
