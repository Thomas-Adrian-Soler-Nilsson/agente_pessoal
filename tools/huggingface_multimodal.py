"""Ferramentas multimodais exclusivas do provider Hugging Face.

Estas ferramentas ficam fora do executor global para não poluir os demais
providers. O provider HF injeta as ferramentas apenas quando ele está ativo.
"""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

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


def _stamp(prefix: str, suffix: str) -> Path:
    return _output_dir(prefix) / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{suffix}"


def generate_hf_image(prompt: str, model: str | None = None) -> str:
    """Gera uma imagem e devolve o caminho local do arquivo."""
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
    """Gera áudio TTS usando um modelo Hugging Face."""
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


def generate_3d(prompt: str, model: str | None = None, image_path: str | None = None) -> str:
    """Gera um asset 3D via um Space Gradio do Hugging Face.

    O Hunyuan3D-2.1 não possui Inference Provider dedicado atualmente, então
    usamos o Space oficial como endpoint Gradio. Isso é deliberadamente
    separado do avatar Live2D existente.
    """
    try:
        from gradio_client import Client, handle_file
    except ImportError as exc:
        raise RuntimeError(
            "A geração 3D precisa do pacote gradio_client. Instale com: pip install gradio_client"
        ) from exc

    model = model or os.getenv("HF_3D_MODEL", "tencent/Hunyuan3D-2.1")
    space = os.getenv("HF_3D_SPACE", "tencent/Hunyuan3D-2.1")
    token = _token()
    client = Client(space, token=token)

    # O endpoint do Space pode evoluir; view_api mantém a integração
    # desacoplada do restante do agente e produz erro legível se mudar.
    api = client.view_api(return_format="dict")
    named = api.get("named_endpoints", {}) if isinstance(api, dict) else {}

    candidates = [
        "/generation_all",
        "/generate",
        "/shape_generation",
        "/predict",
    ]
    endpoint = next((name for name in candidates if name in named), None)
    if endpoint is None:
        available = ", ".join(named.keys()) if named else "nenhum endpoint nomeado"
        raise RuntimeError(
            f"O Space {space} está disponível, mas seu endpoint de geração mudou. "
            f"Endpoints encontrados: {available}"
        )

    # O Space oficial é image-to-3D. Se não houver imagem, o prompt é mantido
    # no resultado para que o agente possa explicar que precisa de uma imagem.
    if not image_path:
        raise ValueError(
            "A geração 3D atual do Hunyuan3D-2.1 precisa de uma imagem de entrada. "
            "Gere uma imagem primeiro ou forneça image_path."
        )

    result = client.predict(handle_file(image_path), api_name=endpoint)
    path = _stamp("3d", ".glb")

    # Gradio normalmente devolve um caminho/arquivo local para outputs de modelo.
    output = result
    if isinstance(result, (list, tuple)):
        output = next((item for item in result if isinstance(item, (str, Path))), result[0] if result else None)

    if not output:
        raise RuntimeError("O Space concluiu a chamada, mas não retornou um arquivo 3D.")

    source = Path(str(output))
    if not source.exists():
        raise RuntimeError(f"O Space retornou uma saída que não existe localmente: {source}")

    suffix = source.suffix or ".glb"
    path = path.with_suffix(suffix)
    path.write_bytes(source.read_bytes())
    return f"Modelo 3D gerado com {model}. Arquivo: {path}"


def hf_tool_executor(name: str, arguments: dict, fallback):
    """Executa ferramentas HF e delega o restante ao executor original."""
    arguments = arguments or {}
    if name == "generate_hf_image":
        return generate_hf_image(arguments.get("prompt", ""), arguments.get("model"))
    if name == "generate_3d":
        return generate_3d(
            arguments.get("prompt", ""),
            arguments.get("model"),
            arguments.get("image_path"),
        )
    if name == "hf_text_to_speech":
        return text_to_speech_hf(arguments.get("text", ""), arguments.get("model"))
    return fallback(name, arguments)
