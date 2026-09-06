import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from .compatible_agent import CompatibleAgent

load_dotenv()


# Modelos que fazem sentido como ponto de partida para o agente.
# O catálogo pode ser sobrescrito por HF_MODELS no .env.
DEFAULT_HF_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]


def available_models():
    configured = os.getenv("HF_MODELS", "")
    return [model.strip() for model in configured.split(",") if model.strip()] or DEFAULT_HF_MODELS


class HuggingFaceAgent:
    """Provider Hugging Face usando o InferenceClient oficial.

    Mantém o mesmo contrato dos demais providers de chat do projeto:
    CompatibleAgent cuida de contexto, memória, tools, retries e streaming.
    O Hugging Face fica responsável apenas pelo transporte/inference.
    """

    def __init__(self, tool_executor, model=None, messages=None):
        api_key = (
            os.getenv("HF_TOKEN", "").strip()
            or os.getenv("HF_API_KEY", "").strip()
        )

        if not api_key:
            raise ValueError(
                "HF_TOKEN ou HF_API_KEY não encontrada no .env"
            )

        self.model = model or os.getenv(
            "HF_MODEL",
            available_models()[0],
        )
        self.provider = os.getenv(
            "HF_PROVIDER",
            "auto",
        ).strip() or "auto"

        client = InferenceClient(
            api_key=api_key,
            provider=self.provider,
        )

        self.agent = CompatibleAgent(
            client=client,
            model=self.model,
            tool_executor=tool_executor,
            messages=messages,
        )

    @property
    def messages(self):
        return self.agent.messages

    def ask_stream(self, text: str, cancel_event=None):
        yield from self.agent.ask_stream(
            text,
            cancel_event=cancel_event,
        )

    def set_personality(self, personality: str):
        self.agent.set_personality(personality)
