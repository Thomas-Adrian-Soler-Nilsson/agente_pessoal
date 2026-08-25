import os

from dotenv import load_dotenv
from openai import OpenAI

from .compatible_agent import CompatibleAgent

load_dotenv()

# Modelos acessíveis no tier gratuito ("Experiment") da Mistral La Plateforme.
# O tier gratuito dá acesso limitado (rate-limited) a praticamente todos os
# modelos da Mistral, incluindo o Large — sem cartão de crédito.
DEFAULT_MISTRAL_MODELS = [
    "mistral-small-latest",
    "mistral-large-latest",
    "mistral-medium-latest",
    "open-mistral-nemo",
    "ministral-8b-latest",
    "ministral-3b-latest",
    "codestral-latest",
    "open-mixtral-8x7b",
]


def available_models():
    configured = os.getenv("MISTRAL_MODELS", "")
    return [model.strip() for model in configured.split(",") if model.strip()] or DEFAULT_MISTRAL_MODELS


class MistralAgent:
    def __init__(self, tool_executor, model=None, messages=None):
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY não encontrada no .env")
        self.model = model or os.getenv("MISTRAL_MODEL", available_models()[0])
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.mistral.ai/v1",
        )
        self.agent = CompatibleAgent(client, self.model, tool_executor, messages)

    def ask_stream(self, text: str):
        return self.agent.ask_stream(text)

    def set_personality(self, personality: str):
        self.agent.set_personality(personality)