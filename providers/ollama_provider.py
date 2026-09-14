import os
import json
from urllib.request import Request, urlopen
from openai import OpenAI

from .compatible_agent import CompatibleAgent


OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434/v1",
)


FALLBACK_MODELS = [
        "llama3.1",
        "minimax-m3:cloud",
        "qwen2.5-coder:latest",
]


def available_models():
    """Lista os modelos instalados no Ollama para o menu de seleção."""
    api_url = OLLAMA_BASE_URL.rstrip("/")
    if api_url.endswith("/v1"):
        api_url = api_url[:-3]
    try:
        request = Request(api_url + "/api/tags", headers={"Accept": "application/json"})
        with urlopen(request, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        names = [item.get("name") or item.get("model") for item in payload.get("models", [])]
        names = [name for name in names if name]
        if names:
            return list(dict.fromkeys(names))
    except Exception:
        pass
    return list(FALLBACK_MODELS)


def active_model(base_url=OLLAMA_BASE_URL):
    """Retorna um modelo instalado no Ollama usando o endpoint /api/tags."""
    api_url = base_url.rstrip("/")
    if api_url.endswith("/v1"):
        api_url = api_url[:-3]
    try:
        request = Request(api_url + "/api/tags", headers={"Accept": "application/json"})
        with urlopen(request, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = payload.get("models") or []
        if models:
            names = [item.get("name") or item.get("model") for item in models]
            names = [name for name in names if name]
            configured = os.getenv("OLLAMA_MODEL", "").strip()
            if configured:
                for name in names:
                    if name == configured:
                        return name
            return names[0] if names else None
    except Exception:
        pass
    return None


class OllamaAgent:
    def __init__(
        self,
        tool_executor,
        model=None,
        messages=None,
    ):
        configured_model = os.getenv("OLLAMA_MODEL", "").strip()
        requested_model = model or configured_model
        # O modelo vindo do menu pode ser apenas o valor padrão do .env;
        # nesse caso ainda permitimos descobrir o modelo realmente ativo.
        forced_model = bool(model and model != configured_model)
        detected_model = active_model() if not forced_model else None
        self.model = requested_model or detected_model or "llama3:latest"
        self.detected_model = detected_model

        self.client = OpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
        )

        self.agent = CompatibleAgent(
            client=self.client,
            model=self.model,
            tool_executor=tool_executor,
            messages=messages,
        )

    @property
    def messages(self):
        return self.agent.messages

    def set_personality(self, personality):
        self.agent.set_personality(personality)

    def ask_stream(self, text, cancel_event=None):
        yield from self.agent.ask_stream(text, cancel_event=cancel_event)

    @property
    def display_model(self):
        return self.detected_model or self.model
