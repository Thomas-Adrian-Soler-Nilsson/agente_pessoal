"""NVIDIA hosted TRELLIS 3D generation backend."""

from __future__ import annotations

import base64
import binascii
import mimetypes
import os
from pathlib import Path

# On Windows, requests/certifi may not include the certificate authority used
# by the system/network. truststore keeps TLS verification enabled while using
# the native Windows certificate store.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import requests

from .remote_3d import OUTPUT_ROOT, _finish, _stem, _viewer


DEFAULT_URL = "https://ai.api.nvidia.com/v1/genai/microsoft/trellis"


def _key() -> str:
    value = (
        os.getenv("NVIDIA_TRELLIS_API_KEY", "").strip()
        or os.getenv("NVIDIA_API_KEY", "").strip()
    )
    if not value and "localhost" not in os.getenv("NVIDIA_TRELLIS_URL", ""):
        raise ValueError("NVIDIA_TRELLIS_API_KEY ou NVIDIA_API_KEY não configurada no .env")
    return value


def _error(response: requests.Response) -> RuntimeError:
    try:
        detail = response.json()
    except ValueError:
        detail = response.text[:1000]
    if response.status_code == 401:
        message = "chave inválida ou sem acesso ao endpoint TRELLIS"
    elif response.status_code == 402:
        message = "créditos ou cota insuficientes"
    elif response.status_code == 429:
        message = "limite de requisições atingido"
    elif response.status_code == 422:
        message = f"payload inválido: {detail}"
    elif response.status_code >= 500:
        nvcf_status = response.headers.get("nvcf-status", "")
        suffix = f" (nvcf-status={nvcf_status})" if nvcf_status else ""
        message = f"serviço hospedado NVIDIA indisponível{suffix}; tente novamente mais tarde"
    else:
        message = str(detail)
    return RuntimeError(f"NVIDIA TRELLIS: HTTP {response.status_code} - {message}")


def _image_data_url(image: Path) -> str:
    mime = mimetypes.guess_type(image.name)[0] or "image/png"
    encoded = base64.b64encode(image.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _decode_artifact(payload: dict) -> bytes:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError(f"NVIDIA TRELLIS não retornou artefato GLB: {payload}")
    artifact = artifacts[0]
    encoded = artifact.get("base64") if isinstance(artifact, dict) else None
    if not encoded:
        raise RuntimeError(f"NVIDIA TRELLIS retornou um artefato sem base64: {payload}")
    if "," in encoded and encoded.startswith("data:"):
        encoded = encoded.split(",", 1)[1]
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("NVIDIA TRELLIS retornou base64 inválido.") from exc


def generate_nvidia_trellis(
    prompt: str = "",
    image_path: str | None = None,
    timeout: int | None = None,
) -> str:
    """Generate a GLB synchronously with NVIDIA's hosted TRELLIS endpoint."""
    prompt = (prompt or "").strip()
    image = Path(image_path).expanduser() if image_path else None
    if not prompt and not image:
        raise ValueError("Informe um prompt ou uma imagem para gerar o modelo 3D.")
    if prompt and len(prompt) > 77:
        raise ValueError("O NVIDIA TRELLIS aceita prompts de até 77 caracteres.")
    if image and not image.is_file():
        raise ValueError(f"Imagem não encontrada: {image}")

    body = {
        "mode": "image" if image else "text",
        "output_format": "glb",
        "seed": int(os.getenv("NVIDIA_TRELLIS_SEED", "0")),
        "ss_sampling_steps": int(os.getenv("NVIDIA_TRELLIS_SS_STEPS", "25")),
        "slat_sampling_steps": int(os.getenv("NVIDIA_TRELLIS_SLAT_STEPS", "25")),
    }
    if image:
        body["image"] = _image_data_url(image)
    else:
        body["prompt"] = prompt
    if os.getenv("NVIDIA_TRELLIS_NO_TEXTURE", "false").lower() in {"1", "true", "yes"}:
        body["no_texture"] = True

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    key = _key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    response = requests.post(
        os.getenv("NVIDIA_TRELLIS_URL", DEFAULT_URL),
        headers=headers,
        json=body,
        timeout=int(timeout or os.getenv("NVIDIA_TRELLIS_TIMEOUT", "900")),
    )
    if not response.ok:
        raise _error(response)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("NVIDIA TRELLIS retornou uma resposta que não é JSON.") from exc

    mesh = OUTPUT_ROOT / f"{_stem('nvidia_trellis')}.glb"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    mesh.write_bytes(_decode_artifact(payload))
    return _finish(mesh, "NVIDIA TRELLIS")


__all__ = ["generate_nvidia_trellis"]
