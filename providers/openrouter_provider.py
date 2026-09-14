import os

from dotenv import load_dotenv
from openai import OpenAI

from .compatible_agent import CompatibleAgent

load_dotenv()

DEFAULT_OPENROUTER_MODELS = [
    # Visao, imagem e video (VLM)
    "inclusionai/ling-3.0-flash-vl:free",
    "thinkingmachines/inkling-small:free",
    "google/gemma-4-31b-it:free",
    "nex-agi/nex-n2.5-pro:free",
    "nex-agi/nex-n2.5-mini:free",
    "dots-studio/dots-3-note-preview:free",
    # Agentes, raciocinio, contexto longo e programacao
    "nvidia/nemotron-3-super-120b-a12b:free",
    "cohere/north-mini-code:free",
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "liquid/lfm-2.5-2.6b:free",
    # Modelos especializados que ainda respondem via chat
    "inclusionai/ling-3.0-flash-fin:free",
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-4-26b-a4b-it:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "openrouter/free",
]


def available_models():
    configured = os.getenv("OPENROUTER_MODELS", "")
    models = [model.strip() for model in configured.split(",") if model.strip()]
    if not models:
        return list(DEFAULT_OPENROUTER_MODELS)

    # Mantem a ordem definida pelo usuario, mas evita chamadas duplicadas
    # quando a lista do .env possui repeticoes.
    return list(dict.fromkeys(models))


class OpenRouterAgent:
    def __init__(self, tool_executor, model=None, messages=None):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY não encontrada no .env")
        self.model = model or os.getenv("OPENROUTER_MODEL", available_models()[0])
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1", default_headers={"HTTP-Referer": "http://localhost", "X-Title": "Agente Pessoal Thomas"})
        self.agent = CompatibleAgent(client, self.model, tool_executor, messages)

    def ask_stream(self, text: str, cancel_event=None):
        return self.agent.ask_stream(text, cancel_event=cancel_event)

    def set_personality(self, personality: str):
        self.agent.set_personality(personality)
