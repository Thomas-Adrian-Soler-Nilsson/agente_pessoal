"""Token Harbor provider using its OpenAI-compatible API."""

import os

from dotenv import load_dotenv
from openai import OpenAI

from .compatible_agent import CompatibleAgent

load_dotenv()

TOKENHARBOR_BASE_URL = "https://tokenharbor.ai/v1"

# Current explicit free routes. The catalog can change; users can override it
# with TOKENHARBOR_MODELS without changing the code.
DEFAULT_TOKENHARBOR_MODELS = [
    "deepseek-v4.1-flash:free",
    "deepseek-v4-flash:free",
    "mimo-v2.5:free",
]


def available_models():
    configured = os.getenv("TOKENHARBOR_MODELS", "")
    return [model.strip() for model in configured.split(",") if model.strip()] or DEFAULT_TOKENHARBOR_MODELS


def _api_key():
    return (
        os.getenv("TOKENHARBOR_API_KEY", "").strip()
        or os.getenv("TOKENHARBOR_KEY", "").strip()
    )


class TokenHarborAgent:
    def __init__(self, tool_executor, model=None, messages=None):
        api_key = _api_key()
        if not api_key:
            raise ValueError("TOKENHARBOR_API_KEY ou TOKENHARBOR_KEY nao encontrada no .env")
        self.model = model or os.getenv("TOKENHARBOR_MODEL", available_models()[0])
        base_url = os.getenv("TOKENHARBOR_BASE_URL", TOKENHARBOR_BASE_URL).strip() or TOKENHARBOR_BASE_URL
        client = OpenAI(api_key=api_key, base_url=base_url)
        self.agent = CompatibleAgent(client, self.model, tool_executor, messages)

    def ask_stream(self, text: str, cancel_event=None):
        yield from self.agent.ask_stream(text, cancel_event=cancel_event)

    def set_personality(self, personality: str):
        self.agent.set_personality(personality)


__all__ = ["TokenHarborAgent", "available_models"]
