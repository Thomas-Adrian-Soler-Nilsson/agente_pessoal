import os

from dotenv import load_dotenv
from openai import OpenAI

from .compatible_agent import CompatibleAgent

load_dotenv()

DEFAULT_NVIDIA_MODELS = [
    "deepseek-ai/deepseek-v4-flash-0731",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-nano-30b-a3b",
    "minimax-m3",
    "moonshotai/kimi-k2.6",
    "mistralai/mistral-medium-3.5-128b-instruct",
    "stepfun/step-3.7-flash",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "meta/llama-3.3-70b-instruct",
    "nvidia/nemotron-mini-4b-instruct",
    "nvidia/muse-glimmer-30b",
    "nvidia/inkling",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/llama-3.1-nemotron-nano-vl-8b-v1",
]

RETIRED_NVIDIA_MODELS = {
    "z-ai/glm-5.2",
}


def available_models():
    configured = os.getenv("NVIDIA_MODELS", "")
    models = [model.strip() for model in configured.split(",") if model.strip()] or DEFAULT_NVIDIA_MODELS
    return [model for model in models if model not in RETIRED_NVIDIA_MODELS]


class NvidiaAgent:
    def __init__(self, tool_executor, model=None, messages=None):
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY não encontrada no .env")
        requested_model = model or os.getenv("NVIDIA_MODEL")
        self.model = (
            requested_model
            if requested_model and requested_model not in RETIRED_NVIDIA_MODELS
            else available_models()[0]
        )
        client = OpenAI(
            api_key=api_key,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        self.agent = CompatibleAgent(client, self.model, tool_executor, messages)

    def ask_stream(self, text: str):
        return self.agent.ask_stream(text)
