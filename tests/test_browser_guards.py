"""Testes do freio de falhas, do limite de abas e do error_code no resumo final.

Cobrem a Tarefa 4 em providers/compatible_agent.py: sem essas travas o modelo
contornava o bloqueio abrindo outra aba (novo tab_id) e repetia o erro
indefinidamente, terminando com um resumo vago que escondia o error_code real.
"""
import unittest
from types import SimpleNamespace

from providers.compatible_agent import CompatibleAgent


class StubClient:
    """Cliente mínimo: devolve sempre texto puro."""

    def __init__(self, content="resumo"):
        class Chat:
            pass

        self.chat = Chat()
        self.chat.completions = self
        self.content = content

    def create(self, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content, tool_calls=None)
                )
            ]
        )


class FailingToolClient(StubClient):
    """Primeira rodada pede browser_fill; depois devolve um resumo vago."""

    def __init__(self):
        super().__init__(content="A tarefa ficou meio confusa.")
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            call = SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(
                    name="browser_fill",
                    arguments='{"tab_id":7,"element_ref":"ref-1","value":"oi"}',
                ),
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="", tool_calls=[call])
                    )
                ]
            )
        return super().create(**kwargs)


def make_agent(execute):
    return CompatibleAgent(StubClient(), "test-model", execute)


class BrowserFailureBudgetTests(unittest.TestCase):
    def test_three_browser_failures_block_further_browser_actions(self):
        calls = []

        def execute(name, arguments):
            calls.append(name)
            return {"status": "failure", "error_code": "stale_element_reference"}

        agent = make_agent(execute)

        for index in range(3):
            result = agent._run_tool(
                "browser_fill",
                {"tab_id": 7, "element_ref": f"ref-{index}", "value": "x"},
            )
            self.assertEqual(result["error_code"], "stale_element_reference")

        blocked = agent._run_tool(
            "browser_fill",
            {"tab_id": 7, "element_ref": "ref-4", "value": "x"},
        )

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["error_code"], "browser_failure_budget_exhausted")
        self.assertEqual(len(calls), 3, "a quarta ação não pode chegar ao executor")

    def test_budget_is_not_reset_by_opening_another_tab(self):
        """O furo original: novo tab_id zerava o bloqueio por aba."""

        calls = []

        def execute(name, arguments):
            calls.append(name)
            if name == "browser_open_tab":
                return {"status": "success", "tab": {"id": 99}}
            return {"status": "failure", "error_code": "stale_element_reference"}

        agent = make_agent(execute)

        for index in range(3):
            agent._run_tool(
                "browser_fill",
                {"tab_id": 7, "element_ref": f"ref-{index}", "value": "x"},
            )

        escaped = agent._run_tool("browser_open_tab", {"url": "https://example.com"})

        self.assertEqual(escaped["status"], "blocked")
        self.assertEqual(escaped["error_code"], "browser_failure_budget_exhausted")
        self.assertEqual(calls, ["browser_fill"] * 3)
        self.assertEqual(agent._tabs_opened, 0)

    def test_retry_suppression_does_not_consume_the_failure_budget(self):
        def execute(name, arguments):
            if name == "browser_click":
                return {"status": "failure", "error_code": "page_changed_since_screenshot"}
            return {"status": "success"}

        agent = make_agent(execute)

        agent._run_tool("browser_click", {"tab_id": 5, "element_ref": "r"})
        self.assertEqual(agent._browser_failures, 1)

        for _ in range(5):
            suppressed = agent._run_tool("browser_click", {"tab_id": 5, "element_ref": "r"})
            self.assertEqual(suppressed["error_code"], "retry_suppressed_after_browser_failure")

        self.assertEqual(agent._browser_failures, 1, "bloqueios não contam como falha nova")


class BrowserTabLimitTests(unittest.TestCase):
    def test_second_tab_of_the_same_request_is_blocked(self):
        calls = []

        def execute(name, arguments):
            calls.append(name)
            return {"status": "success", "tab": {"id": 1}}

        agent = make_agent(execute)

        first = agent._run_tool("browser_open_tab", {"url": "https://example.com"})
        second = agent._run_tool("browser_open_tab", {"url": "https://example.com/outra"})

        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "blocked")
        self.assertEqual(second["error_code"], "too_many_tabs_opened")
        self.assertEqual(calls, ["browser_open_tab"])
        self.assertEqual(agent._tabs_opened, 1)

    def test_navigate_without_tab_id_counts_as_a_new_tab(self):
        def execute(name, arguments):
            return {"status": "success", "tab": {"id": 1}}

        agent = make_agent(execute)

        agent._run_tool("browser_open_tab", {"url": "https://example.com"})
        opened_by_navigate = agent._run_tool("browser_navigate", {"url": "https://example.com/2"})

        self.assertEqual(opened_by_navigate["error_code"], "too_many_tabs_opened")

    def test_navigate_with_explicit_tab_id_is_allowed(self):
        def execute(name, arguments):
            return {"status": "success"}

        agent = make_agent(execute)

        agent._run_tool("browser_open_tab", {"url": "https://example.com"})
        in_place = agent._run_tool(
            "browser_navigate",
            {"url": "https://example.com/2", "tab_id": 1},
        )

        self.assertNotEqual(in_place.get("error_code"), "too_many_tabs_opened")
        self.assertEqual(agent._tabs_opened, 1)

    def test_new_request_resets_both_counters(self):
        def execute(name, arguments):
            return {"status": "failure", "error_code": "stale_element_reference"}

        agent = make_agent(execute)
        agent._run_tool("browser_fill", {"tab_id": 7, "element_ref": "r", "value": "x"})
        self.assertEqual(agent._browser_failures, 1)

        list(agent.ask_stream("nova solicitação"))

        self.assertEqual(agent._browser_failures, 0)
        self.assertEqual(agent._tabs_opened, 0)
        self.assertEqual(agent._last_browser_error_code, "")


class FinalSummaryErrorCodeTests(unittest.TestCase):
    def test_final_answer_cites_the_last_browser_error_code(self):
        def execute(name, arguments):
            return {"status": "failure", "error_code": "stale_element_reference"}

        agent = CompatibleAgent(FailingToolClient(), "test-model", execute)
        chunks = list(agent.ask_stream("converse com o seu amigo deepseek"))

        self.assertTrue(chunks)
        final = chunks[-1]
        self.assertIn("stale_element_reference", final)
        self.assertIn("A tarefa ficou meio confusa.", final)

    def test_vague_summary_is_not_left_unexplained(self):
        def execute(name, arguments):
            return {"status": "failure", "error_code": "unsupported_page"}

        agent = CompatibleAgent(FailingToolClient(), "test-model", execute)
        final = list(agent.ask_stream("abra o chrome://extensions"))[-1]

        self.assertIn("error_code=unsupported_page", final)

    def test_successful_browser_action_clears_the_pending_error_code(self):
        def execute(name, arguments):
            if arguments.get("value") == "erro":
                return {"status": "failure", "error_code": "stale_element_reference"}
            return {"status": "success"}

        agent = make_agent(execute)

        agent._run_tool("browser_fill", {"tab_id": 7, "element_ref": "r", "value": "erro"})
        self.assertEqual(agent._last_browser_error_code, "stale_element_reference")

        agent._run_tool("browser_fill", {"tab_id": 7, "element_ref": "r", "value": "ok"})
        self.assertEqual(agent._last_browser_error_code, "")

        self.assertEqual(agent._cite_browser_error("tudo certo"), "tudo certo")


if __name__ == "__main__":
    unittest.main()
