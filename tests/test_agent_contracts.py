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
from tools.browser import BrowserTools
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
    def test_browser_tools_share_broker_until_last_instance_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "browser-bridge.json"
            with patch("tools.browser_bridge._config_path", return_value=config_path):
                primary = BrowserTools()
                temporary = BrowserTools()
                self.addCleanup(primary.close)
                self.addCleanup(temporary.close)

                self.assertIs(primary.bridge, temporary.bridge)
                self.assertTrue(config_path.exists())

                temporary.close()
                self.assertTrue(config_path.exists())

                primary.close()
                self.assertFalse(config_path.exists())

    def test_browser_click_at_forwards_expected_target_label(self):
        class Bridge:
            def __init__(self):
                self.request = None

            def execute(self, operation, arguments, timeout=30):
                self.request = (operation, arguments)
                return {"status": "success"}

        bridge = Bridge()
        browser = BrowserTools(bridge=bridge)

        browser.click_at(42, "shot-1", 65, 165, expected_label="Minha Conta")

        self.assertEqual(bridge.request[0], "click_at")
        self.assertEqual(bridge.request[1]["expected_label"], "Minha Conta")

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
            "browser_visual_click",
        }.issubset(names))

    def test_browser_visual_click_captures_clicks_and_verifies_in_order(self):
        events = []
        screenshot = {
            "type": "image",
            "image_kind": "browser_screenshot",
            "screenshot_id": "shot-123",
            "width": 800,
            "height": 600,
            "mime_type": "image/jpeg",
            "data": "image-bytes",
        }

        def execute(name, arguments):
            events.append((name, arguments))
            if name == "browser_screenshot":
                return screenshot
            if name == "browser_click_at":
                return {"status": "success", "data": {"clicked": True}}
            if name == "browser_inspect":
                return {"status": "success", "data": {"title": "Página seguinte"}}
            self.fail(f"tool inesperada: {name}")

        class Vision:
            def analyze(self, image, task):
                events.append(("vision", image, task))
                return {
                    "type": "vision_analysis",
                    "status": "success",
                    "screenshot_id": "shot-123",
                    "analysis": {
                        "status": "targets_found",
                        "targets": [{
                            "label": "Entrar",
                            "x": 123,
                            "y": 84,
                            "confidence": 0.91,
                            "actionable": True,
                        }, {
                            "label": "Ajuda",
                            "x": 600,
                            "y": 500,
                            "confidence": 0.8,
                            "actionable": True,
                        }],
                    },
                }

        agent = CompatibleAgent(FakeCompletionClient(), "test-model", execute, vision_agent=Vision())
        result = agent._run_tool(
            "browser_visual_click",
            {"tab_id": 42, "goal": "Clique no botão Entrar"},
        )

        self.assertEqual([event[0] for event in events], [
            "browser_screenshot", "vision", "browser_click_at", "browser_inspect",
        ])
        self.assertEqual(events[1][1], screenshot)
        self.assertEqual(events[1][2], "Clique no botão Entrar")
        self.assertEqual(events[2][1], {
            "tab_id": 42,
            "screenshot_id": "shot-123",
            "x": 123,
            "y": 84,
            "expected_label": "Entrar",
        })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["verification"]["status"], "success")
        self.assertNotIn("data", result)

    def test_failed_visual_click_blocks_retry_and_keeps_error_visible(self):
        calls = []
        screenshot = {
            "type": "image",
            "image_kind": "browser_screenshot",
            "screenshot_id": "shot-failed",
            "width": 800,
            "height": 600,
            "mime_type": "image/jpeg",
            "data": "image-bytes",
        }

        def execute(name, arguments):
            calls.append(name)
            if name == "browser_screenshot":
                return screenshot
            if name == "browser_click_at":
                return {"status": "failure", "error_code": "page_changed_since_screenshot"}
            if name == "browser_inspect":
                return {"status": "success", "data": {"title": "Erro 998/999"}}
            if name == "browser_click":
                return {"status": "success"}
            self.fail(f"tool inesperada: {name}")

        class Vision:
            def analyze(self, image, task):
                return {
                    "type": "vision_analysis",
                    "status": "success",
                    "screenshot_id": image["screenshot_id"],
                    "analysis": {
                        "status": "targets_found",
                        "targets": [{
                            "label": "Minha Conta",
                            "x": 240,
                            "y": 90,
                            "confidence": 0.95,
                            "actionable": True,
                        }],
                    },
                }

        agent = CompatibleAgent(FakeCompletionClient(), "test-model", execute, vision_agent=Vision())
        result = agent._run_tool(
            "browser_visual_click",
            {"tab_id": 42, "goal": "Clique em Minha Conta"},
        )
        agent._run_tool("browser_inspect", {"tab_id": 42})
        retry = agent._run_tool(
            "browser_click",
            {"tab_id": 42, "element_ref": "ref-after-failure"},
        )

        self.assertEqual(result["error_code"], "page_changed_since_screenshot")
        self.assertIn("page_changed_since_screenshot", agent.operation_state.last_error)
        self.assertEqual(retry["status"], "blocked")
        self.assertEqual(retry["error_code"], "retry_suppressed_after_browser_failure")
        self.assertIn("page_changed_since_screenshot", agent.operation_state.last_error)
        self.assertEqual(calls, ["browser_screenshot", "browser_click_at", "browser_inspect"])

        list(agent.ask_stream("Tente novamente nesta nova solicitação."))
        self.assertNotIn(42, agent._failed_browser_tabs)

    def test_browser_visual_click_does_not_click_uncertain_or_tied_targets(self):
        image = {
            "type": "image",
            "image_kind": "browser_screenshot",
            "screenshot_id": "shot-uncertain",
            "width": 800,
            "height": 600,
            "mime_type": "image/jpeg",
            "data": "image-bytes",
        }
        analyses = [
            {"status": "uncertain", "targets": [{"label": "Entrar", "x": 20, "y": 30, "confidence": 0.99, "actionable": True}]},
            {"status": "targets_found", "targets": [{"label": "Entrar", "x": 20, "y": 30, "confidence": 0.71, "actionable": False}]},
            {"status": "targets_found", "targets": [{"label": "Fora da tela", "x": 900, "y": 30, "confidence": 0.99, "actionable": True}]},
            {"status": "targets_found", "targets": [
                {"label": "Entrar", "x": 20, "y": 30, "confidence": 0.9, "actionable": True},
                {"label": "Continuar", "x": 40, "y": 30, "confidence": 0.9, "actionable": True},
            ]},
        ]

        for analysis in analyses:
            with self.subTest(analysis=analysis):
                calls = []

                def execute(name, arguments):
                    calls.append(name)
                    return image if name == "browser_screenshot" else {"status": "success"}

                class Vision:
                    def analyze(self, screenshot, task):
                        return {
                            "type": "vision_analysis",
                            "status": "success",
                            "screenshot_id": "shot-uncertain",
                            "analysis": analysis,
                        }

                agent = CompatibleAgent(FakeCompletionClient(), "test-model", execute, vision_agent=Vision())
                result = agent._run_tool(
                    "browser_visual_click",
                    {"tab_id": 42, "goal": "Clique no controle correto"},
                )

                self.assertEqual(calls, ["browser_screenshot"])
                self.assertEqual(result["status"], "uncertain")
                self.assertIn(result["error_code"], {"no_actionable_target", "ambiguous_visual_target"})
                self.assertNotEqual(agent.operation_state.last_successful_operation, "browser_visual_click")
                self.assertEqual(agent.operation_state.last_error, "browser_visual_click: uncertain")

    def test_browser_visual_click_preserves_confirmation_without_claiming_success(self):
        image = {
            "type": "image",
            "image_kind": "browser_screenshot",
            "screenshot_id": "shot-confirm",
            "width": 800,
            "height": 600,
            "mime_type": "image/jpeg",
            "data": "image-bytes",
        }
        calls = []

        def execute(name, arguments):
            calls.append(name)
            if name == "browser_screenshot":
                return image
            return {
                "status": "confirmation_required",
                "error_code": "user_confirmation_required",
                "data": {"confirmation_token": "confirm-1", "label": "Enviar"},
            }

        class Vision:
            def analyze(self, screenshot, task):
                return {
                    "type": "vision_analysis",
                    "status": "success",
                    "screenshot_id": "shot-confirm",
                    "analysis": {
                        "status": "targets_found",
                        "targets": [{"label": "Enviar", "x": 250, "y": 90, "confidence": 0.95, "actionable": True}],
                    },
                }

        agent = CompatibleAgent(FakeCompletionClient(), "test-model", execute, vision_agent=Vision())
        result = agent._run_tool(
            "browser_visual_click",
            {"tab_id": 42, "goal": "Enviar o formulário"},
        )

        self.assertEqual(calls, ["browser_screenshot", "browser_click_at"])
        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(result["click"]["data"]["confirmation_token"], "confirm-1")
        self.assertNotIn("verification", result)
        self.assertNotEqual(agent.operation_state.last_successful_operation, "browser_visual_click")

    def test_browser_visual_click_rejects_analysis_for_another_screenshot(self):
        image = {
            "type": "image",
            "image_kind": "browser_screenshot",
            "screenshot_id": "shot-current",
            "width": 800,
            "height": 600,
            "mime_type": "image/jpeg",
            "data": "image-bytes",
        }
        calls = []

        def execute(name, arguments):
            calls.append(name)
            return image

        class Vision:
            def analyze(self, screenshot, task):
                return {
                    "type": "vision_analysis",
                    "status": "success",
                    "screenshot_id": "shot-old",
                    "analysis": {
                        "status": "targets_found",
                        "targets": [{"label": "Entrar", "x": 123, "y": 84, "confidence": 0.99, "actionable": True}],
                    },
                }

        agent = CompatibleAgent(FakeCompletionClient(), "test-model", execute, vision_agent=Vision())
        result = agent._run_tool(
            "browser_visual_click",
            {"tab_id": 42, "goal": "Clique em Entrar"},
        )

        self.assertEqual(calls, ["browser_screenshot"])
        self.assertEqual(result["status"], "uncertain")
        self.assertEqual(result["error_code"], "screenshot_id_mismatch")

    def test_browser_visual_click_preserves_screenshot_setup_failure(self):
        calls = []

        def execute(name, arguments):
            calls.append(name)
            return {
                "status": "setup_needed",
                "error_code": "bridge_setup_needed",
                "observation": "Abra o popup da extensão para conectar.",
            }

        agent = CompatibleAgent(FakeCompletionClient(), "test-model", execute, vision_agent=object())
        result = agent._run_tool(
            "browser_visual_click",
            {"tab_id": 42, "goal": "Clique em Entrar"},
        )

        self.assertEqual(calls, ["browser_screenshot"])
        self.assertEqual(result["status"], "setup_needed")
        self.assertEqual(result["error_code"], "bridge_setup_needed")

    def test_browser_visual_click_keeps_uncertain_click_uncertain_after_inspection(self):
        image = {
            "type": "image",
            "image_kind": "browser_screenshot",
            "screenshot_id": "shot-unclear-result",
            "width": 800,
            "height": 600,
            "mime_type": "image/jpeg",
            "data": "image-bytes",
        }
        calls = []

        def execute(name, arguments):
            calls.append((name, arguments))
            if name == "browser_screenshot":
                return image
            if name == "browser_click_at":
                return {"status": "uncertain", "error_code": "postcondition_not_observed"}
            if name == "browser_inspect":
                return {"status": "success", "data": {"title": "Página"}}
            self.fail(f"tool inesperada: {name}")

        class Vision:
            def analyze(self, screenshot, task):
                return {
                    "type": "vision_analysis",
                    "status": "success",
                    "screenshot_id": "shot-unclear-result",
                    "analysis": {
                        "status": "targets_found",
                        "targets": [{"label": "Próxima", "x": 300, "y": 200, "confidence": 0.93, "actionable": True}],
                    },
                }

        agent = CompatibleAgent(FakeCompletionClient(), "test-model", execute, vision_agent=Vision())
        result = agent._run_tool(
            "browser_visual_click",
            {"tab_id": 42, "goal": "Avançar para a próxima etapa"},
        )

        self.assertEqual([name for name, _ in calls], [
            "browser_screenshot", "browser_click_at", "browser_inspect",
        ])
        self.assertEqual(result["status"], "uncertain")
        self.assertEqual(result["error_code"], "post_click_verification_uncertain")

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
