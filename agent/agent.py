import os

from dotenv import load_dotenv
from groq import Groq

from providers.compatible_agent import CompatibleAgent, build_tools

load_dotenv()


class Agent(CompatibleAgent):
    """Adaptador legado para o agente compatível da aplicação."""

    def __init__(self, tool_executor, tools=None):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY não encontrada no .env")

        super().__init__(
            client=Groq(api_key=api_key),
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            tool_executor=tool_executor,
        )

        if tools is not None:
            self.tools = tools


__all__ = ["Agent", "CompatibleAgent", "build_tools"]
