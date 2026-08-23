from .groq_provider import GroqAgent
from .nvidia_provider import NvidiaAgent, available_models as nvidia_models
from .openrouter_provider import OpenRouterAgent, available_models as openrouter_models


class ProviderRouter:
    def __init__(self, tool_executor):
        self.tool_executor = tool_executor

    def groq(self, model=None):
        return GroqAgent(self.tool_executor, model=model)

    def openrouter(self, model=None):
        return OpenRouterAgent(self.tool_executor, model=model)

    def nvidia(self, model=None):
        return NvidiaAgent(self.tool_executor, model=model)

    def automatic(self, groq_model=None, openrouter_model=None, nvidia_model=None):
        return AutomaticAgent(self.tool_executor, groq_model, openrouter_model, nvidia_model)


class AutomaticAgent:
    def __init__(self, tool_executor, groq_model=None, openrouter_model=None, nvidia_model=None):
        self.tool_executor = tool_executor
        self.groq_model = groq_model
        self.openrouter_model = openrouter_model
        self.nvidia_model = nvidia_model
        self.current = None
        self.messages = None

    def ask_stream(self, text: str):
        try:
            self.current = GroqAgent(self.tool_executor, self.groq_model, self.messages)
            self.messages = self.current.agent.messages
            yield from self.current.ask_stream(text)
            return
        except Exception as error:
            print(f"\n⚠️ Groq falhou: {error}")
        candidates = [self.openrouter_model] if self.openrouter_model else []
        candidates.extend(model for model in openrouter_models() if model not in candidates)
        for model in candidates:
            try:
                self.current = OpenRouterAgent(self.tool_executor, model, self.messages)
                self.messages = self.current.agent.messages
                yield from self.current.ask_stream(text)
                return
            except Exception as error:
                print(f"\n⚠️ OpenRouter ({model}) falhou: {error}")

        candidates = [self.nvidia_model] if self.nvidia_model else []
        candidates.extend(model for model in nvidia_models() if model not in candidates)
        for model in candidates:
            try:
                self.current = NvidiaAgent(self.tool_executor, model, self.messages)
                self.messages = self.current.agent.messages
                yield from self.current.ask_stream(text)
                return
            except Exception as error:
                print(f"\n⚠️ NVIDIA ({model}) falhou: {error}")

        yield "Os provedores de IA estão indisponíveis agora."
