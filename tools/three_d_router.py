"""Provider selection for ordinary 3D requests."""

from __future__ import annotations

import os

from .huggingface_multimodal import generate_3d as generate_hf_3d
from .nvidia_trellis import generate_nvidia_trellis
from .threews_3d import generate_threews


def generate_3d_auto(
    prompt: str = "",
    image_path: str | None = None,
    timeout: int | None = None,
) -> str:
    """Prefer configured HF 3D, then NVIDIA TRELLIS, then the free fallback."""
    hf_configured = bool(
        os.getenv("HF_TOKEN", "").strip()
        or os.getenv("HF_API_KEY", "").strip()
    )
    if hf_configured:
        try:
            return generate_hf_3d(prompt, image_path=image_path)
        except Exception as hf_error:
            if image_path:
                raise RuntimeError(
                    f"Hugging Face 3D falhou com imagem e não há fallback de imagem disponível: {hf_error}"
                ) from hf_error
            nvidia_configured = bool(
                os.getenv("NVIDIA_TRELLIS_API_KEY", "").strip()
                or os.getenv("NVIDIA_API_KEY", "").strip()
            )
            if nvidia_configured:
                try:
                    return generate_nvidia_trellis(prompt, image_path, timeout)
                except Exception as nvidia_error:
                    try:
                        return generate_threews(prompt, timeout)
                    except Exception as fallback_error:
                        raise RuntimeError(
                            f"Hugging Face 3D falhou ({hf_error}); NVIDIA TRELLIS falhou ({nvidia_error}); fallback three.ws também falhou ({fallback_error})."
                        ) from fallback_error
            try:
                return generate_threews(prompt, timeout)
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Hugging Face 3D falhou ({hf_error}); fallback three.ws também falhou ({fallback_error})."
                ) from fallback_error

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
            "Nenhum backend 3D de imagem configurado. Configure HF_TOKEN ou NVIDIA_TRELLIS_API_KEY."
        )
    return generate_threews(prompt, timeout)


__all__ = ["generate_3d_auto", "generate_hf_3d"]
