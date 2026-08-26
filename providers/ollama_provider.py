import os
from openai import OpenAI

from .compatible_agent import CompatibleAgent


OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434/v1",
)


def available_models():
    return [
        "llama3.1",
        "minimax-m3:cloud",
        "qwen2.5-coder:latest",
    ]


class OllamaAgent:
    def __init__(
        self,
        tool_executor,
        model=None,
        messages=None,
    ):
        self.model = model or os.getenv(
            "OLLAMA_MODEL",
            "llama3:latest",
        )

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

    def ask_stream(self, text):
        yield from self.agent.ask_stream(text)