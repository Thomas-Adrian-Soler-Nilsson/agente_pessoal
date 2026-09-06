"""Capacidades generativas do provider Hugging Face.

O módulo é carregado somente pelo provider HF, então os demais providers
não ganham ferramentas duplicadas.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from huggingface_hub import InferenceClient

OUTPUT_ROOT = Path.home() / "Pictures" / "AgentePessoal" / "HuggingFace"


def _token() -> str:
    token = os.getenv("HF_TOKEN", "").strip() or os.getenv("HF_API_KEY", "").strip()
    if not token:
        raise ValueError("HF_TOKEN ou HF_API_KEY não encontrada no .env")
    return token


def _output_dir(kind: str) -> Path:
    path = OUTPUT_ROOT / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stamp(kind: str, suffix: str) -> Path:
    return _output_dir(kind) / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{suffix}"


def generate_hf_image(prompt: str, model: str | None = None) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "Não foi possível gerar a imagem: prompt vazio."

    model = model or os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
    provider = os.getenv("HF_IMAGE_PROVIDER", "auto").strip() or "auto"
    client = InferenceClient(api_key=_token(), provider=provider)
    image = client.text_to_image(prompt=prompt, model=model)
    path = _stamp("images", ".png")
    image.save(path)
    return f"Imagem gerada com {model}. Arquivo: {path}"


def text_to_speech_hf(text: str, model: str | None = None) -> str:
    text = (text or "").strip()
    if not text:
        return "Não foi possível gerar a fala: texto vazio."

    model = model or os.getenv("HF_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
    provider = os.getenv("HF_TTS_PROVIDER", "auto").strip() or "auto"
    client = InferenceClient(api_key=_token(), provider=provider)
    audio = client.text_to_speech(text=text, model=model)
    path = _stamp("audio", ".wav")
    path.write_bytes(audio)
    return f"Áudio gerado com {model}. Arquivo: {path}"


def _find_3d_file(value) -> Path | None:
    """Extrai recursivamente um arquivo GLB/GLTF/OBJ/STL/PLY do retorno Gradio."""
    if isinstance(value, Path):
        return value if value.exists() and value.suffix.lower() in {".glb", ".gltf", ".obj", ".stl", ".ply"} else None
    if isinstance(value, str):
        path = Path(value)
        return path if path.exists() and path.suffix.lower() in {".glb", ".gltf", ".obj", ".stl", ".ply"} else None
    if isinstance(value, dict):
        for item in value.values():
            found = _find_3d_file(item)
            if found:
                return found
    if isinstance(value, (list, tuple)):
        for item in value:
            found = _find_3d_file(item)
            if found:
                return found
    return None


def generate_3d(prompt: str, model: str | None = None, image_path: str | None = None) -> str:
    """Gera um asset 3D e cria um pequeno viewer HTML local.

    O modelo continua separado do avatar Live2D. Hunyuan3D-2.0 é usado como
    backend padrão porque o Space oficial está atualmente em execução e expõe
    text-to-3D/image-to-3D; Hunyuan3D-2.1 continua disponível no catálogo para
    execução local/futura infraestrutura própria.
    """
    try:
        from gradio_client import Client, handle_file
    except ImportError as exc:
        raise RuntimeError("A geração 3D precisa do pacote gradio_client. Instale com: pip install gradio_client") from exc

    model = model or os.getenv("HF_3D_MODEL", "tencent/Hunyuan3D-2")
    space = os.getenv("HF_3D_SPACE", "tencent/Hunyuan3D-2")
    token = _token()

    if not image_path and "Hunyuan3D-2" in model:
        # O Space 2.0 suporta text-to-3D, mas a API pública pode mudar. O
        # endpoint textual é tentado primeiro; se falhar, a mensagem orienta
        # o agente a gerar uma imagem de referência e repetir.
        client = Client(space, token=token)
        try:
            result = client.predict(prompt or "um objeto 3D detalhado", api_name="/generation_all")
        except Exception:
            raise RuntimeError("O backend 3D não aceitou texto diretamente. Gere uma imagem de referência e tente novamente com image_path.")
    else:
        if not image_path:
            raise ValueError("A geração 3D desse modelo precisa de uma imagem de referência.")
        client = Client(space, token=token)
        result = client.predict(
            image=handle_file(image_path),
            steps=30,
            guidance_scale=5.0,
            seed=1234,
            octree_resolution=256,
            check_box_rembg=True,
            randomize_seed=True,
            api_name="/shape_generation",
        )

    source = _find_3d_file(result)
    if not source:
        raise RuntimeError("O backend 3D respondeu, mas não retornou um arquivo de malha reconhecível.")

    target = _stamp("3d", source.suffix.lower() or ".glb")
    target.write_bytes(source.read_bytes())

    # Viewer independente do avatar: abre no navegador e usa <model-viewer>.
    viewer = target.with_suffix(".html")
    viewer.write_text(
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Agente Pessoal — Modelo 3D</title>"
        "<script type='module' src='https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js'></script>"
        "<style>html,body{margin:0;height:100%;background:#101114}model-viewer{width:100%;height:100%}</style>"
        "</head><body><model-viewer src='" + target.as_uri() + "' camera-controls auto-rotate shadow-intensity='1'"
        " exposure='1' environment-image='neutral'></model-viewer></body></html>",
        encoding="utf-8",
    )

    return f"Modelo 3D gerado com {model}. Arquivo: {target}. Visualizador: {viewer}"


def hf_tool_executor(name: str, arguments: dict, fallback):
    arguments = arguments or {}
    if name == "generate_hf_image":
        return generate_hf_image(arguments.get("prompt", ""), arguments.get("model"))
    if name == "generate_3d":
        return generate_3d(arguments.get("prompt", ""), arguments.get("model"), arguments.get("image_path"))
    if name == "hf_text_to_speech":
        return text_to_speech_hf(arguments.get("text", ""), arguments.get("model"))
    return fallback(name, arguments)
