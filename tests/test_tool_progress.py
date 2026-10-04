"""O aviso de ferramenta precisa sair ANTES da execucao, nao no fim do lote.

Antes, os cartoes so apareciam depois que todas as ferramentas do lote
terminavam: numa captura com analise visual (segundos) o terminal ficava parado
e parecia travado.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from providers.compatible_agent import CompatibleAgent


class ToolCallClient:
    """Primeira rodada pede browser_inspect; depois devolve texto final."""

    def __init__(self):
        class Chat:
            pass

        self.chat = Chat()
        self.chat.completions = self
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            call = SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(name="browser_inspect", arguments='{"tab_id":12}'),
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[call]))
                ]
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Pronto.", tool_calls=None))]
        )


class ToolProgressOrderTests(unittest.TestCase):
    def test_pending_notice_comes_before_the_tool_executes(self):
        events = []

        def execute(name, arguments):
            events.append(("executou", name))
            return {"status": "success", "operation": "inspect", "data": {"elements": []}}

        agent = CompatibleAgent(ToolCallClient(), "test-model", execute)

        with patch(
            "providers.compatible_agent.ui.chat_tool_pending",
            side_effect=lambda name, arguments=None: events.append(("avisou", name)),
        ), patch(
            "providers.compatible_agent.ui.chat_tool",
            side_effect=lambda name, *args, **kwargs: events.append(("cartao", name)),
        ), patch("providers.compatible_agent.ui.chat_operation_header"):
            list(agent.ask_stream("inspecione a aba"))

        self.assertIn(("avisou", "browser_inspect"), events, "faltou o aviso imediato")
        self.assertIn(("executou", "browser_inspect"), events)
        self.assertIn(("cartao", "browser_inspect"), events, "o cartao completo sumiu")
        self.assertLess(
            events.index(("avisou", "browser_inspect")),
            events.index(("executou", "browser_inspect")),
            "o aviso precisa vir antes da execucao: " + str(events),
        )
        self.assertLess(
            events.index(("executou", "browser_inspect")),
            events.index(("cartao", "browser_inspect")),
            "o cartao completo continua vindo depois: " + str(events),
        )


if __name__ == "__main__":
    unittest.main()
