from ui import ui

from .groq_provider import GroqAgent
from .nvidia_provider import (
    NvidiaAgent,
    available_models as nvidia_models,
)
from .openrouter_provider import (
    OpenRouterAgent,
    available_models as openrouter_models,
)
from .ollama_provider import OllamaAgent, available_models as ollama_models


class ProviderRouter:
    def __init__(self, tool_executor):
        self.tool_executor = tool_executor

    def groq(self, model=None):
        return GroqAgent(
            self.tool_executor,
            model=model,
        )

    def openrouter(self, model=None):
        return OpenRouterAgent(
            self.tool_executor,
            model=model,
        )

    def nvidia(self, model=None):
        return NvidiaAgent(
            self.tool_executor,
            model=model,
        )


    def ollama(self, model=None):
        return OllamaAgent(
            self.tool_executor,
            model=model
        )

    def automatic(
        self,
        groq_model=None,
        openrouter_model=None,
        nvidia_model=None,
        ollama_model=None,
    ):
        return AutomaticAgent(
            self.tool_executor,
            groq_model,
            openrouter_model,
            nvidia_model,
            ollama_model,
        )


class AutomaticAgent:
    def __init__(
        self,
        tool_executor,
        groq_model=None,
        openrouter_model=None,
        nvidia_model=None,
        ollama_model=None,
    ):
        self.tool_executor = tool_executor

        self.groq_model = groq_model
        self.openrouter_model = openrouter_model
        self.nvidia_model = nvidia_model
        self.ollama_model = ollama_model

        self.current = None
        self.messages = None
        self.personality = ""

    def set_personality(self, personality: str):
        self.personality = personality

        if self.current is not None:
            self.current.set_personality(
                personality
            )

    def ask_stream(self, text: str):

        # ========================================================
        # GROQ
        # ========================================================

        try:
            self.current = GroqAgent(
                self.tool_executor,
                self.groq_model,
                self.messages,
            )

            self.current.set_personality(
                self.personality
            )

            self.messages = (
                self.current.agent.messages
            )

            yield from self.current.ask_stream(
                text
            )

            return

        except Exception as error:
            ui.warn(
                f"Groq falhou: {error}"
            )

        # ========================================================
        # OPENROUTER
        # ========================================================

        candidates = []

        if self.openrouter_model:
            candidates.append(
                self.openrouter_model
            )

        candidates.extend(
            model
            for model in openrouter_models()
            if model not in candidates
        )

        for model in candidates:
            try:
                self.current = OpenRouterAgent(
                    self.tool_executor,
                    model,
                    self.messages,
                )

                self.current.set_personality(
                    self.personality
                )

                self.messages = (
                    self.current.agent.messages
                )

                yield from self.current.ask_stream(
                    text
                )

                return

            except Exception as error:
                ui.warn(
                    f"OpenRouter ({model}) falhou: "
                    f"{error}"
                )

        # ========================================================
        # NVIDIA
        # ========================================================

        candidates = []

        if self.nvidia_model:
            candidates.append(
                self.nvidia_model
            )

        candidates.extend(
            model
            for model in nvidia_models()
            if model not in candidates
        )

        for model in candidates:
            try:
                self.current = NvidiaAgent(
                    self.tool_executor,
                    model,
                    self.messages,
                )

                self.current.set_personality(
                    self.personality
                )

                self.messages = (
                    self.current.agent.messages
                )

                yield from self.current.ask_stream(
                    text
                )

                return

            except Exception as error:
                ui.warn(
                    f"NVIDIA ({model}) falhou: "
                    f"{error}"
                )

        # ========================================================
        # OLLAMA
        # ========================================================

        candidates = []

        if self.ollama_model:
            candidates.append(
                self.ollama_model
            )

        candidates.extend(
            model
            for model in ollama_models()
            if model not in candidates
        )

        for model in candidates:
            try:
                self.current = OllamaAgent(
                    self.tool_executor,
                    model,
                    self.messages,
                )

                self.current.set_personality(
                    self.personality
                )

                self.messages = (
                    self.current.agent.messages
                )

                yield from self.current.ask_stream(
                    text
                )

                return

            except Exception as error:
                ui.warn(
                    f"Ollama ({model}) falhou: "
                    f"{error}"
                )

        yield (
            "Os provedores de IA estão "
            "indisponíveis agora."
        )