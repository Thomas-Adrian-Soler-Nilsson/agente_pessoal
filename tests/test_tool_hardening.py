"""Testes do endurecimento de ferramentas (Tarefa 8 da missão).

Cobrem: bloqueio de credenciais e de caminhos fora das pastas permitidas em
tools/files.py, o fallback dinâmico de tools/web_research.py (que nunca rodava e
deixava a aba anônima aberta) e a classificação de erro de JSON de ferramenta.
"""
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.files import FileTools
from tools.tool_call_parser import is_tool_json_error
from tools.web_research import open_public_page


class FileCredentialGuardTests(unittest.TestCase):
    def setUp(self):
        self.tools = FileTools()
        self.desktop = Path.home() / "Desktop"

    def test_env_file_inside_allowed_root_is_blocked(self):
        with self.assertRaises(PermissionError):
            self.tools._resolve_path(str(self.desktop / ".env"))

    def test_credential_names_are_blocked(self):
        blocked = (
            ".env",
            ".env.local",
            ".env.production",
            "id_rsa",
            "id_rsa.pub",
            "chave.pem",
            "certificado.PEM",
            "browser-bridge.json",
            "subpasta/.env",
        )
        for name in blocked:
            with self.subTest(name=name):
                with self.assertRaises(PermissionError):
                    self.tools._resolve_path(str(self.desktop / name))

    def test_env_extension_is_no_longer_allowed(self):
        self.assertNotIn(".env", FileTools.ALLOWED_EXTENSIONS)

    def test_ordinary_file_inside_allowed_root_still_resolves(self):
        target = self.desktop / "notas.txt"
        self.assertEqual(self.tools._resolve_path(str(target)), target.resolve())

    def test_path_outside_allowed_roots_is_rejected(self):
        # Antes, explicit_roots (raiz do disco + todas as unidades) aceitava
        # qualquer caminho e o teste equivalente já falhava no repositório.
        for outside in (Path.home().parent, Path.home(), Path("C:/Windows")):
            with self.subTest(outside=str(outside)):
                with self.assertRaises(PermissionError):
                    self.tools._resolve_path(str(outside))


class ToolJsonErrorTests(unittest.TestCase):
    def test_real_tool_json_errors_are_recognized(self):
        for text in (
            "Failed to parse tool call arguments as JSON",
            "tool_use_failed",
            "ToolArgumentsError: argumentos inválidos",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_tool_json_error(RuntimeError(text)))

    def test_generic_400_errors_are_not_mistaken_for_json_errors(self):
        for text in (
            "invalid_request_error: model 'x' not found",
            "Error code: 400 - invalid_request_error",
            "JSONDecodeError: Expecting value: line 1 column 1",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_tool_json_error(RuntimeError(text)))


class _FakeResponse:
    status_code = 200
    url = "https://exemplo.test/js"
    headers = {"Content-Type": "text/html; charset=utf-8"}
    encoding = "utf-8"

    def iter_content(self, _size):
        # Página que exige JavaScript: dispara o fallback dinâmico.
        yield "<html><body>Please enable JavaScript to continue.</body></html>".encode("utf-8")

    def close(self):
        return None


class _FakeBrowserTools:
    last = None
    inspect_status = "success"

    def __init__(self):
        self.calls = []
        _FakeBrowserTools.last = self

    def open_tab(self, url="", incognito=False):
        self.calls.append(("open_tab", url, incognito))
        # Formato real da extensão: "tab" preenchido e "data" com valor None.
        return {"status": "success", "tab": {"id": 77}, "data": None}

    def wait(self, tab_id, text="", url_contains="", timeout=10):
        self.calls.append(("wait", tab_id))
        return {"status": "success"}

    def inspect(self, tab_id, max_chars=12000):
        self.calls.append(("inspect", tab_id))
        if self.inspect_status != "success":
            return {"status": "failure", "error_code": "stale_element_reference"}
        return {"status": "success", "data": {"text": "conteudo dinamico do site " * 4}}

    def close_tab(self, tab_id):
        self.calls.append(("close_tab", tab_id))
        return {"status": "success"}

    def close(self):
        self.calls.append(("close",))


class WebResearchFallbackTests(unittest.TestCase):
    def _run(self):
        with patch("tools.web_research._public_destination", return_value=("https://exemplo.test/js", None)), \
                patch("tools.web_research._fetch_public", return_value=(_FakeResponse(), None)), \
                patch("tools.browser.BrowserTools", _FakeBrowserTools):
            return open_public_page("https://exemplo.test/js")

    def test_fallback_extracts_content_from_a_js_locked_page(self):
        result = self._run()

        self.assertEqual(result["status"], "success", "resposta: " + str(result)[:400])
        self.assertIn("conteudo dinamico", result["content"])
        browser = _FakeBrowserTools.last
        self.assertIn(("open_tab", "https://exemplo.test/js", True), browser.calls)
        self.assertIn(("wait", 77), browser.calls)
        self.assertIn(("inspect", 77), browser.calls)

    def test_tab_is_closed_even_when_inspection_fails(self):
        _FakeBrowserTools.inspect_status = "failure"
        self.addCleanup(setattr, _FakeBrowserTools, "inspect_status", "success")

        self._run()

        browser = _FakeBrowserTools.last
        self.assertIn(("close_tab", 77), browser.calls, "a aba anônima precisa ser fechada")
        self.assertIn(("close",), browser.calls, "o bridge compartilhado precisa ser liberado")


if __name__ == "__main__":
    unittest.main()
