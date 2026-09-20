import functools
import http.server
import shutil
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from tools.browser import BrowserTools


class BrowserToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="agent-browser-", dir=Path.cwd()))
        (cls.root / "index.html").write_text(
            """<!doctype html><html><body>
            <h1 id='title'>Browser OK</h1>
            <input id='name'><button id='go' onclick=\"document.body.dataset.clicked='yes'\">Enviar</button>
            <a id='download' href='/asset.txt' download>Baixar</a>
            </body></html>""",
            encoding="utf-8",
        )
        (cls.root / "asset.txt").write_text("download-ok", encoding="utf-8")
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(cls.root))
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/index.html"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        self.profile = Path(tempfile.mkdtemp(prefix="agent-browser-profile-", dir=Path.cwd()))
        self.browser = BrowserTools(user_data_dir=self.profile, headless=True)

    def tearDown(self):
        self.browser.close()
        shutil.rmtree(self.profile, ignore_errors=True)

    def test_navigation_snapshot_and_read(self):
        self.assertIn(self.url, self.browser.navigate(self.url))
        self.assertIn("Browser OK", self.browser.snapshot())
        self.assertIn("Browser OK", self.browser.read())

    def test_selector_fill_and_keyboard(self):
        self.browser.navigate(self.url)
        self.assertIn("Preenchi", self.browser.fill("#name", "Thomas"))
        self.assertIn("Cliquei", self.browser.click("#go"))

    def test_screenshot_and_download(self):
        self.browser.navigate(self.url)
        screenshot = self.browser.screenshot()
        self.assertEqual(screenshot.get("type"), "image")
        target = self.profile / "asset.txt"
        self.assertIn("Download salvo", self.browser.download("#download", str(target)))
        self.assertEqual(target.read_text(encoding="utf-8"), "download-ok")


if __name__ == "__main__":
    unittest.main()
