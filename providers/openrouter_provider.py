import os

from dotenv import load_dotenv
from openai import OpenAI

from .compatible_agent import CompatibleAgent

load_dotenv()

DEFAULT_OPENROUTER_MODELS = [
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-4-26b-a4b-it:free",
    "openrouter/free",
]


def available_models():
    configured = os.getenv("OPENROUTER_MODELS", "")
    return [model.strip() for model in configured.split(",") if model.strip()] or DEFAULT_OPENROUTER_MODELS


class OpenRouterAgent:
    def __init__(self, tool_executor, model=None, messages=None):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY não encontrada no .env")
        self.model = model or os.getenv("OPENROUTER_MODEL", available_models()[0])
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1", default_headers={"HTTP-Referer": "http://localhost", "X-Title": "Agente Pessoal Thomas"})
        self.agent = CompatibleAgent(client, self.model, tool_executor, messages)

    def ask_stream(self, text: str):
        return self.agent.ask_stream(text)
