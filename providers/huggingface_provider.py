import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from .compatible_agent import CompatibleAgent
from .huggingface_catalog import available_models as catalog_models
from tools.huggingface_multimodal import hf_tool_executor

load_dotenv()


def available_models():
    """Modelos de chat Hugging Face selecionáveis pelo menu."""
    return catalog_models("chat")


HF_EXTRA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_hf_image",
            "description": "Gera uma imagem com o modelo de imagem Hugging Face selecionado e salva o resultado no computador.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Descrição detalhada da imagem."},
                    "model": {"type": "string", "description": "Modelo HF de imagem; deixe vazio para usar HF_IMAGE_MODEL."},
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_3d",
            "description": "Gera um modelo 3D visualizável a partir de uma imagem. Não altera nem substitui o avatar Live2D; é uma capacidade generativa independente do agente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Descrição do objeto desejado; usada como contexto da geração."},
                    "image_path": {"type": "string", "description": "Caminho da imagem de referência. Obrigatório para image-to-3D."},
                    "model": {"type": "string", "description": "Modelo HF 3D; deixe vazio para usar HF_3D_MODEL."},
                },
                "required": ["prompt", "image_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hf_text_to_speech",
            "description": "Gera fala com um modelo TTS Hugging Face e salva o áudio localmente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Texto que será falado."},
                    "model": {"type": "string", "description": "Modelo HF de TTS; deixe vazio para usar HF_TTS_MODEL."},
                },
                "required": ["text"],
            },
        },
    },
]


class HuggingFaceAgent:
    """Provider Hugging Face com chat + capacidades generativas específicas."""

    def __init__(self, tool_executor, model=None, messages=None):
        api_key = (
            os.getenv("HF_TOKEN", "").strip()
            or os.getenv("HF_API_KEY", "").strip()
        )

        if not api_key:
            raise ValueError(
                "HF_TOKEN ou HF_API_KEY não encontrada no .env"
            )

        models = available_models()
        self.model = model or os.getenv("HF_MODEL", models[0])
        self.provider = os.getenv("HF_PROVIDER", "auto").strip() or "auto"

        client = InferenceClient(
            api_key=api_key,
            provider=self.provider,
        )

        self.agent = CompatibleAgent(
            client=client,
            model=self.model,
            tool_executor=lambda name, args: hf_tool_executor(
                name,
                args,
                tool_executor,
            ),
            messages=messages,
        )

        self.agent.tools.extend(HF_EXTRA_TOOLS)

    @property
    def messages(self):
        return self.agent.messages

    def ask_stream(self, text: str, cancel_event=None):
        yield from self.agent.ask_stream(text, cancel_event=cancel_event)

    def set_personality(self, personality: str):
        self.agent.set_personality(personality)
