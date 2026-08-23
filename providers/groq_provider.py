import os

from dotenv import load_dotenv
from groq import Groq

from .compatible_agent import CompatibleAgent

load_dotenv()

DEFAULT_GROQ_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "groq/compound",
    "groq/compound-mini",
    "openai/gpt-oss-safeguard-20b",
]


def available_models():
    configured = os.getenv("GROQ_MODELS", "")
    return [model.strip() for model in configured.split(",") if model.strip()] or DEFAULT_GROQ_MODELS


class GroqAgent:
    def __init__(self, tool_executor, model=None, messages=None):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY não encontrada no .env")
        self.model = model or os.getenv("GROQ_MODEL", available_models()[0])
        self.agent = CompatibleAgent(Groq(api_key=api_key), self.model, tool_executor, messages)

    def ask_stream(self, text: str):
        return self.agent.ask_stream(text)

    def set_personality(self, personality: str):
        self.agent.set_personality(personality)
