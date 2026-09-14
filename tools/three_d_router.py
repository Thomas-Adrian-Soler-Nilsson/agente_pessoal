"""Provider selection for ordinary 3D requests."""

from __future__ import annotations

import os

from .nvidia_trellis import generate_nvidia_trellis
from .threews_3d import generate_threews


def generate_3d_auto(
    prompt: str = "",
    image_path: str | None = None,
    timeout: int | None = None,
) -> str:
    """Prefer NVIDIA TRELLIS and then three.ws for text generation."""
    nvidia_configured = bool(
        os.getenv("NVIDIA_TRELLIS_API_KEY", "").strip()
        or os.getenv("NVIDIA_API_KEY", "").strip()
    )
    if nvidia_configured:
        try:
            return generate_nvidia_trellis(prompt, image_path, timeout)
        except Exception as nvidia_error:
            if image_path:
                raise RuntimeError(
                    f"NVIDIA TRELLIS falhou e o fallback gratuito não aceita imagem: {nvidia_error}"
                ) from nvidia_error
            try:
                return generate_threews(prompt, timeout)
            except Exception as fallback_error:
                raise RuntimeError(
                    f"NVIDIA TRELLIS falhou ({nvidia_error}); fallback three.ws também falhou ({fallback_error})."
                ) from fallback_error
    if image_path:
        raise RuntimeError(
            "Nenhum backend 3D de imagem configurado. Configure NVIDIA_TRELLIS_API_KEY."
        )
    return generate_threews(prompt, timeout)


__all__ = ["generate_3d_auto"]
