import os

from dotenv import load_dotenv
from openai import OpenAI

from .compatible_agent import CompatibleAgent

load_dotenv()

GEMINI_MODELS = {
    "text": [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3-flash-preview",
        "gemini-3.1-pro-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
    ],
    "image": [
        "gemini-3.1-flash-image",
        "gemini-3.1-flash-lite-image",
        "gemini-3-pro-image",
        "gemini-2.5-flash-image",
    ],
    "tts": [
        "gemini-3.1-flash-tts-preview",
        "gemini-2.5-flash-preview-tts",
        "gemini-2.5-pro-preview-tts",
    ],
    "live": [
        "gemini-3.1-flash-live-preview",
        "gemini-3.5-live-translate-preview",
        "gemini-3.5-transcribe-live",
        "gemini-2.5-flash-native-audio-preview-12-2025",
    ],
    "audio": ["gemini-3.5-transcribe"],
    "embedding": ["gemini-embedding-2-preview", "gemini-embedding-001"],
    "video": ["veo-3-fast-generate", "veo-3-generate", "veo-3-lite-generate", "gemini-omni-1.1-flash"],
    "agents": ["deep-research-preview-04-2026", "deep-research-max-preview-04-2026", "antigravity-preview-05-2026"],
    "robotics": ["gemini-robotics-er-2-preview"],
}

DEFAULT_GEMINI_MODELS = GEMINI_MODELS["text"]


def available_models():
    configured = os.getenv("GEMINI_MODELS", "")
    return [m.strip() for m in configured.split(",") if m.strip()] or DEFAULT_GEMINI_MODELS


def models_by_category(category: str) -> list[str]:
    return list(GEMINI_MODELS.get(category.strip().lower(), []))


def all_models() -> dict[str, list[str]]:
    return {category: list(models) for category, models in GEMINI_MODELS.items()}


class GeminiAgent:
    def __init__(self, tool_executor, model=None, messages=None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY não encontrada no .env")
        self.model = model or os.getenv("GEMINI_MODEL", available_models()[0])
        client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        self.agent = CompatibleAgent(client, self.model, tool_executor, messages)

    def ask_stream(self, text: str, cancel_event=None):
        return self.agent.ask_stream(text, cancel_event=cancel_event)

    def set_personality(self, personality: str):
        self.agent.set_personality(personality)
