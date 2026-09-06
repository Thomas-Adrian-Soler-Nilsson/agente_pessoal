import threading
import tempfile
import unittest
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from memory.temporal_memory import TemporalMemory
from providers.compatible_agent import CompatibleAgent, build_tools
from providers.router import AutomaticAgent
from tools.files import FileTools
from tools.tool_call_parser import (
    is_tool_json_error,
    parse_tool_arguments,
    recover_tool_call,
)


class FakeCompletionClient:
    def __init__(self):
        self.calls = 0

        class Chat:
            pass

        self.chat = Chat()
        self.chat.completions = self

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="resposta",
                        tool_calls=None,
                    )
                )
            ]
        )


class FourToolRoundsClient(FakeCompletionClient):
    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            call = SimpleNamespace(
                id=f"call-{self.calls}",
                function=SimpleNamespace(
                    name="read_file",
                    arguments='{"path":"C:\\\\Users\\\\Thomas\\\\site\\\\index.html"}',
                ),
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="",
                            tool_calls=[call],
                        )
                    )
                ]
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Resumo pronto para continuar.",
                        tool_calls=None,
                    )
                )
            ]
        )


class JsonRecoveryClient(FakeCompletionClient):
    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            error = RuntimeError(
                "Failed to parse tool call arguments as JSON"
            )
            error.body = {
                "failed_generation": (
                    '{"name":"write_file","arguments":'
                    '{"path":"C:\\\\Users\\\\Thomas\\\\site\\\\index.html",'
                    '"content":"<html>...'
                )
            }
            raise error
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Vou continuar usando edição incremental.",
                        tool_calls=None,
                    )
                )
            ]
        )


class EmptyThenSummaryClient(FakeCompletionClient):
    def create(self, **kwargs):
        self.calls += 1
        content = "" if self.calls == 1 else "Resumo recuperado."
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=content,
                        tool_calls=None,
                    )
                )
            ]
        )


class InspectThenReadClient(FakeCompletionClient):
    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            name = "inspect_project"
            arguments = '{"path":"C:\\\\Users\\\\Thomas\\\\site"}'
        elif self.calls == 2:
            name = "read_file"
            arguments = '{"path":"C:\\\\Users\\\\Thomas\\\\site\\\\index.html"}'
        else:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="Inspeção concluída; pronto para editar.",
                            tool_calls=None,
                        )
                    )
                ]
            )
        call = SimpleNamespace(
            id=f"call-{self.calls}",
            function=SimpleNamespace(name=name, arguments=arguments),
        )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="", tool_calls=[call])
                )
            ]
        )


class FailingProvider:
    def __init__(self, tool_executor, model=None, messages=None):
        self.agent = SimpleNamespace(
            messages=messages if messages is not None else [
                {"role": "system", "content": "system"}
            ]
        )

    def set_personality(self, personality):
        return None

    def ask_stream(self, text, cancel_event=None):
        self.agent.messages.append({"role": "user", "content": text})
        raise RuntimeError("provider indisponivel")


class WorkingProvider(FailingProvider):
    def ask_stream(self, text, cancel_event=None):
        self.agent.messages.append({"role": "user", "content": text})
        yield "resposta de fallback"


class AgentContractsTests(unittest.TestCase):
    def test_tool_registry_contains_core_tools(self):
        names = {
            item["function"]["name"]
            for item in build_tools()
        }
        self.assertTrue({
            "open_application",
            "list_directory",
            "read_file",
            "capture_screen",
            "capture_webcam",
        }.issubset(names))

    def test_cancelled_agent_does_not_call_provider(self):
        client = FakeCompletionClient()
        agent = CompatibleAgent(client, "test-model", lambda name, args: "ok")
        cancel_event = threading.Event()
        cancel_event.set()

        self.assertEqual(list(agent.ask_stream("olá", cancel_event)), [])
        self.assertEqual(client.calls, 0)

    def test_tool_round_limit_still_returns_final_response(self):
        client = FourToolRoundsClient()
        agent = CompatibleAgent(client, "test-model", lambda name, args: "arquivo lido")
        result = list(agent.ask_stream("melhore o site"))
        self.assertEqual(result, ["Resumo pronto para continuar."])
        self.assertEqual(client.calls, 2)

    def test_fallback_does_not_reuse_failed_attempt_history(self):
        automatic = AutomaticAgent(lambda name, args: "ok")

        with patch("providers.router.GroqAgent", FailingProvider), patch(
            "providers.router.MistralAgent", FailingProvider
        ), patch("providers.router.mistral_models", return_value=[]), patch(
            "providers.router.openrouter_models", return_value=["fallback"]
        ), patch("providers.router.OpenRouterAgent", WorkingProvider):
            result = list(automatic.ask_stream("teste"))

        self.assertEqual(result, ["resposta de fallback"])
        user_messages = [
            message
            for message in automatic.messages
            if message.get("role") == "user"
        ]
        self.assertEqual(user_messages, [{"role": "user", "content": "teste"}])

    def test_memory_persists_and_searches(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory) / "memory.json"
            memory = TemporalMemory(storage)
            memory.add("Thomas prefere respostas curtas", "preference", 0.9)

            reloaded = TemporalMemory(storage)
            results = reloaded.search("preferência respostas curtas")

        self.assertEqual(len(results), 1)
        self.assertIn("respostas curtas", results[0]["content"])

    def test_file_tools_reject_path_outside_allowed_roots(self):
        tools = FileTools()
        outside = Path.home().parent

        with self.assertRaises(PermissionError):
            tools._resolve_path(str(outside))

    def test_windows_path_arguments_are_parsed(self):
        raw = r'{"path":"C:\\Users\\Thomas Adrian\\Desktop\\site","content":"ok"}'
        arguments = parse_tool_arguments(raw)
        self.assertEqual(arguments["path"], r"C:\Users\Thomas Adrian\Desktop\site")

    def test_project_inspection_returns_structure_and_relevant_files(self):
        tools = FileTools()
        root = Path.home() / "Desktop" / "agent-inspection-test"
        root.mkdir(parents=True, exist_ok=True)
        try:
            (root / "index.html").write_text("<main>ok</main>", encoding="utf-8")
            (root / "notes.txt").write_text("ignore", encoding="utf-8")
            result = tools.inspect_project(str(root))
            self.assertIn("index.html", result)
            self.assertIn("<main>ok</main>", result)
        finally:
            import shutil
            shutil.rmtree(root, ignore_errors=True)

    def test_failed_generation_tool_call_can_be_recovered(self):
        error = RuntimeError("tool_use_failed")
        error.body = {
            "failed_generation": (
                '{"name":"list_directory",'
                '"arguments":{"path":"C:\\\\Users\\\\Thomas"}}'
            )
        }
        call = recover_tool_call(error)
        self.assertIsNotNone(call)
        self.assertEqual(call.function.name, "list_directory")
        self.assertEqual(
            parse_tool_arguments(call.function.arguments)["path"],
            r"C:\Users\Thomas",
        )

    def test_invalid_json_requests_safe_retry(self):
        client = JsonRecoveryClient()
        agent = CompatibleAgent(client, "test-model", lambda name, args: "ok")
        result = list(agent.ask_stream("melhore o site"))
        self.assertEqual(result, ["Vou continuar usando edição incremental."])
        self.assertEqual(client.calls, 2)
        self.assertTrue(is_tool_json_error(RuntimeError("tool_use_failed")))

    def test_empty_provider_response_uses_recovery_summary(self):
        client = EmptyThenSummaryClient()
        agent = CompatibleAgent(client, "test-model", lambda name, args: "ok")
        self.assertEqual(list(agent.ask_stream("melhore o site")), ["Resumo recuperado."])

    def test_inspection_preserves_rounds_after_redundant_read(self):
        client = InspectThenReadClient()
        agent = CompatibleAgent(client, "test-model", lambda name, args: "conteúdo")
        result = list(agent.ask_stream("melhore o site"))
        self.assertEqual(result, ["Inspeção concluída; pronto para editar."])
        self.assertEqual(client.calls, 3)

    def test_incremental_edit_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path.home() / "Desktop" / "agent-test-contracts"
            root.mkdir(parents=True, exist_ok=True)
            path = root / "sample.py"
            tools = FileTools()
            try:
                self.assertIn("sucesso", tools.write_file(str(path), "value = 1\n"))
                self.assertIn("sucesso", tools.edit_file(str(path), "value = 1", "value = 2"))
                self.assertIn("sucesso", tools.validate_file(str(path)))
                self.assertIn("value = 2", path.read_text(encoding="utf-8"))
            finally:
                shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()