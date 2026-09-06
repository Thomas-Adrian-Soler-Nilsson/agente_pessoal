import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from .compatible_agent import CompatibleAgent
from .huggingface_catalog import available_models as catalog_models

load_dotenv()


def available_models():
    """Modelos de chat Hugging Face selecionáveis pelo menu."""
    return catalog_models("chat")


class HuggingFaceAgent:
    """Provider Hugging Face usando o InferenceClient oficial."""

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
            tool_executor=tool_executor,
            messages=messages,
        )

    @property
    def messages(self):
        return self.agent.messages

    def ask_stream(self, text: str, cancel_event=None):
        yield from self.agent.ask_stream(text, cancel_event=cancel_event)

    def set_personality(self, personality: str):
        self.agent.set_personality(personality)
