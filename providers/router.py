import copy

from ui import ui
from .groq_provider import GroqAgent
from .mistral_provider import MistralAgent, available_models as mistral_models
from .nvidia_provider import NvidiaAgent, available_models as nvidia_models
from .ollama_provider import OllamaAgent
from .openrouter_provider import OpenRouterAgent, available_models as openrouter_models
from .huggingface_provider import HuggingFaceAgent, available_models as huggingface_models


class ProviderRouter:
    def __init__(self, tool_executor):
        self.tool_executor = tool_executor

    def groq(self, model=None):
        return GroqAgent(self.tool_executor, model=model)

    def openrouter(self, model=None):
        return OpenRouterAgent(self.tool_executor, model=model)

    def nvidia(self, model=None):
        return NvidiaAgent(self.tool_executor, model=model)

    def ollama(self, model=None):
        return OllamaAgent(self.tool_executor, model=model)

    def mistral(self, model=None):
        return MistralAgent(self.tool_executor, model=model)

    def huggingface(self, model=None):
        return HuggingFaceAgent(self.tool_executor, model=model)

    def automatic(
        self,
        groq_model=None,
        openrouter_model=None,
        nvidia_model=None,
        mistral_model=None,
        huggingface_model=None,
    ):
        return AutomaticAgent(
            self.tool_executor,
            groq_model,
            openrouter_model,
            nvidia_model,
            mistral_model,
            huggingface_model,
        )


class AutomaticAgent:
    def __init__(
        self,
        tool_executor,
        groq_model=None,
        openrouter_model=None,
        nvidia_model=None,
        mistral_model=None,
        huggingface_model=None,
    ):
        self.tool_executor = tool_executor
        self.groq_model = groq_model
        self.openrouter_model = openrouter_model
        self.nvidia_model = nvidia_model
        self.mistral_model = mistral_model
        self.huggingface_model = huggingface_model
        self.current = None
        self.messages = None
        self.personality = ""

    def set_personality(self, personality: str):
        self.personality = personality
        if self.current is not None:
            self.current.set_personality(personality)

    def _try_provider(self, provider_class, model, label, base_messages, text, cancel_event):
        self.current = provider_class(
            self.tool_executor,
            model,
            base_messages,
        )
        self.current.set_personality(self.personality)
        yield from self.current.ask_stream(text, cancel_event=cancel_event)
        if cancel_event is None or not cancel_event.is_set():
            self.messages = self.current.agent.messages

    def ask_stream(self, text: str, cancel_event=None):
        base_messages = copy.deepcopy(self.messages)

        if cancel_event is not None and cancel_event.is_set():
            return

        providers = [
            (GroqAgent, self.groq_model, "Groq"),
            (MistralAgent, self.mistral_model, "Mistral"),
            (OpenRouterAgent, self.openrouter_model, "OpenRouter"),
            (NvidiaAgent, self.nvidia_model, "NVIDIA"),
            (HuggingFaceAgent, self.huggingface_model, "Hugging Face"),
        ]

        # Cada provider recebe primeiro o modelo configurado; depois,
        # quando aplicável, o catálogo alternativo daquele provider.
        model_lists = {
            "Mistral": mistral_models,
            "OpenRouter": openrouter_models,
            "NVIDIA": nvidia_models,
            "Hugging Face": huggingface_models,
        }

        for provider_class, selected_model, label in providers:
            candidates = [selected_model] if selected_model else []
            list_fn = model_lists.get(label)
            if list_fn is not None:
                candidates.extend(model for model in list_fn() if model not in candidates)

            if not candidates:
                candidates = [None]

            for model in candidates:
                if cancel_event is not None and cancel_event.is_set():
                    return
                try:
                    yield from self._try_provider(
                        provider_class,
                        model,
                        label,
                        base_messages,
                        text,
                        cancel_event,
                    )
                    return
                except Exception as error:
                    suffix = f" ({model})" if model else ""
                    ui.warn(f"{label}{suffix} falhou: {error}")

        yield "Os provedores de IA estão indisponíveis agora."
