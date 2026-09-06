"""Catálogo de modelos Hugging Face para o agente pessoal.

A lista separa modelos por capacidade. Os pesos são open-weight/licenciados
para uso conforme a licença do repositório, mas inferência hospedada pelo
Hugging Face/Inference Providers não é ilimitada: a conta Free recebe apenas
os créditos mensais definidos pelo Hugging Face.
"""

from __future__ import annotations

import os


HF_CHAT_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "Qwen/Qwen3-30B-A3B-Instruct-2507",
    "Qwen/Qwen3-30B-A3B-Instruct",
    "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8",
    "Qwen/Qwen3-Omni-30B-A3B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
    "deepseek-ai/DeepSeek-R1-0528",
    "deepseek-ai/DeepSeek-V3-0324",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "google/gemma-3-27b-it",
]


HF_VISION_MODELS = [
    "Qwen/Qwen3-VL-30B-A3B-Instruct",
    "Qwen/Qwen2.5-VL-32B-Instruct",
    "Qwen/Qwen2.5-VL-72B-Instruct",
    "tencent/HunyuanOCR",
]


HF_TTS_MODELS = [
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "hexgrad/Kokoro-82M",
    "openbmb/VoxCPM2",
    "ResembleAI/chatterbox",
    "nvidia/magpie_tts_multilingual_357m",
    "mistralai/Voxtral-4B-TTS-2603",
    "coqui/XTTS-v2",
]


HF_IMAGE_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "black-forest-labs/FLUX.1-dev",
    "stabilityai/stable-diffusion-xl-base-1.0",
    "tencent/HunyuanImage-3.0",
]


HF_3D_MODELS = [
    "tencent/Hunyuan3D-2.1",
    "tencent/Hunyuan3D-2",
    "tencent/Hunyuan3D-2mini",
    "tencent/Hunyuan3D-2mv",
    "tencent/Hunyuan3D-Omni",
    "tencent/HunyuanWorld-1",
]


HF_AUDIO_MODELS = [
    "Qwen/Qwen3-Omni-30B-A3B-Instruct",
    "openai/whisper-large-v3",
    "openai/whisper-large-v3-turbo",
]


HF_DEFAULTS = {
    "chat": "openai/gpt-oss-20b",
    "vision": "Qwen/Qwen3-VL-30B-A3B-Instruct",
    "tts": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "image": "black-forest-labs/FLUX.1-schnell",
    "3d": "tencent/Hunyuan3D-2.1",
    "audio": "openai/whisper-large-v3-turbo",
}


def _configured(name: str, defaults: list[str]) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return list(defaults)
    return [item.strip() for item in raw.split(",") if item.strip()]


def available_models(capability: str) -> list[str]:
    """Return models for a capability, with optional .env overrides."""
    key = capability.strip().lower()
    groups = {
        "chat": ("HF_CHAT_MODELS", HF_CHAT_MODELS),
        "vision": ("HF_VISION_MODELS", HF_VISION_MODELS),
        "tts": ("HF_TTS_MODELS", HF_TTS_MODELS),
        "image": ("HF_IMAGE_MODELS", HF_IMAGE_MODELS),
        "3d": ("HF_3D_MODELS", HF_3D_MODELS),
        "audio": ("HF_AUDIO_MODELS", HF_AUDIO_MODELS),
    }
    if key not in groups:
        raise ValueError(f"Capacidade Hugging Face desconhecida: {capability}")
    env_name, defaults = groups[key]
    return _configured(env_name, defaults)


def default_model(capability: str) -> str:
    return HF_DEFAULTS[capability.strip().lower()]


__all__ = [
    "HF_CHAT_MODELS",
    "HF_VISION_MODELS",
    "HF_TTS_MODELS",
    "HF_IMAGE_MODELS",
    "HF_3D_MODELS",
    "HF_AUDIO_MODELS",
    "HF_DEFAULTS",
    "available_models",
    "default_model",
]
