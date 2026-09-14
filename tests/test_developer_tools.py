import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.developer import DeveloperTools
from tools.files import FileTools


class FakeDownloadResponse:
    status_code = 200
    headers = {"Content-Length": "8"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1024 * 1024):
        yield b"download"


class DeveloperToolsTests(unittest.TestCase):
    def setUp(self):
        self.file_tools = FileTools()
        self.developer = DeveloperTools(self.file_tools)
        self.root = Path(tempfile.mkdtemp(prefix="agent-dev-", dir=Path.cwd()))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_run_terminal_executes_command_and_captures_output(self):
        command = f'"{sys.executable}" -c "print(\'terminal-ok\')"'
        result = self.developer.run_terminal(command, str(self.root), timeout=30)
        self.assertIn("Código de saída: 0", result)
        self.assertIn("terminal-ok", result)

    def test_run_terminal_blocks_destructive_and_secret_commands(self):
        self.assertIn("bloqueado", self.developer.run_terminal("git reset --hard", str(self.root)).lower())
        self.assertIn("bloqueado", self.developer.run_terminal("type .env", str(self.root)).lower())

    def test_run_terminal_feeds_stdin(self):
        command = f'"{sys.executable}" -c "print(input())"'
        result = self.developer.run_terminal(command, str(self.root), timeout=30, input_text="terminal-input\n")
        self.assertIn("Exit code: 0", result)
        self.assertIn("terminal-input", result)

    def test_run_code_file_executes_python(self):
        script = self.root / "hello.py"
        script.write_text("print('python-ok')\n", encoding="utf-8")
        result = self.developer.run_code_file(str(script))
        self.assertIn("Código de saída: 0", result)
        self.assertIn("python-ok", result)

    def test_run_code_file_feeds_interactive_stdin(self):
        script = self.root / "interactive.py"
        script.write_text("print(input('name:'))\n", encoding="utf-8")
        result = self.developer.run_code_file(str(script), input_text="Thomas\n", timeout=30)
        self.assertIn("Exit code: 0", result)
        self.assertIn("Thomas", result)

    def test_run_code_file_does_not_hang_without_stdin(self):
        script = self.root / "needs_input.py"
        script.write_text("value = input('value:')\nprint(value)\n", encoding="utf-8")
        result = self.developer.run_code_file(str(script), timeout=30)
        self.assertIn("needs_input", result)

    def test_detect_runtimes_reports_python(self):
        result = self.developer.detect_runtimes()
        self.assertIn("Python", result)

    def test_auto_install_uses_requirements_manifest(self):
        (self.root / "requirements.txt").write_text("requests\n", encoding="utf-8")
        with patch.object(self.developer, "_run_process", return_value="Código de saída: 0") as runner:
            result = self.developer.install_dependencies(str(self.root), manager="auto")
        runner.assert_called_once()
        self.assertIn("requirements.txt", result)

    def test_download_file_saves_inside_allowed_root(self):
        target = self.root / "asset.bin"
        with patch("tools.developer.requests.get", return_value=FakeDownloadResponse()):
            result = self.developer.download_file("https://example.test/asset.bin", str(target))
        self.assertIn("Download concluído", result)
        self.assertEqual(target.read_bytes(), b"download")


if __name__ == "__main__":
    unittest.main()
