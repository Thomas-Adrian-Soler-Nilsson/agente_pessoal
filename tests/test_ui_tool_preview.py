import unittest
import base64
from io import BytesIO
from io import StringIO
from unittest.mock import patch

from PIL import Image
from rich.console import Console
from ui import ui


class ToolPreviewTests(unittest.TestCase):
    def test_browser_screenshot_is_rendered_inline_without_saving(self):
        image = Image.new("RGB", (8, 4), "#2878D0")
        payload = BytesIO()
        image.save(payload, format="PNG")
        result = {
            "type": "image",
            "image_kind": "browser_screenshot",
            "screenshot_id": "shot-preview-123",
            "width": 8,
            "height": 4,
            "mime_type": "image/png",
            "data": base64.b64encode(payload.getvalue()).decode("ascii"),
        }
        output = StringIO()

        with patch.object(ui, "console", Console(file=output, width=64, force_terminal=True, color_system="truecolor", theme=ui.THEME)):
            ui.show_browser_screenshot(result)

        rendered = output.getvalue()
        self.assertIn("Screenshot Chrome 8x4", rendered)
        self.assertIn("shot-preview", rendered)
        self.assertIn("▀", rendered)

    def test_browser_tab_list_preview_keeps_tab_identity(self):
        result = {
            "status": "success",
            "operation": "list_tabs",
            "data": {
                "tabs": [{"id": 1214948272, "title": "Menu - Área do Candidato", "url": "https://www.comvest.unicamp.br/AreaDoCandidato/"}],
            },
        }

        preview, _ = ui._glass_preview("browser_list_tabs", {}, result)

        self.assertIn("1214948272", preview)
        self.assertIn("Menu - Área do Candidato", preview)
        self.assertIn("https://www.comvest.unicamp.br/AreaDoCandidato/", preview)

    def test_browser_failure_preview_keeps_error_code_before_large_analysis(self):
        result = {
            "type": "browser_visual_click",
            "status": "failure",
            "analysis": {"status": "success", "details": "x" * 2400},
            "target": {"label": "Minha Conta", "x": 240, "y": 90},
            "click": {"status": "failure", "error_code": "page_changed_since_screenshot"},
            "error_code": "page_changed_since_screenshot",
            "observation": "A página mudou após a captura; nenhum clique foi confirmado.",
        }

        preview, _ = ui._glass_preview("browser_visual_click", {}, result)

        self.assertIn("page_changed_since_screenshot", preview)
        self.assertIn("Minha Conta", preview)
        self.assertIn("A página mudou após a captura", preview)
        self.assertNotIn("x" * 100, preview)
        self.assertNotIn("previa reduzida", preview)

    def test_narrow_terminal_card_still_shows_browser_error_code(self):
        result = {
            "type": "browser_visual_click",
            "status": "failure",
            "analysis": {"status": "success", "details": "x" * 2400},
            "target": {"label": "Minha Conta", "x": 240, "y": 90},
            "click": {"status": "failure", "error_code": "page_changed_since_screenshot"},
            "error_code": "page_changed_since_screenshot",
            "observation": "A página mudou após a captura.",
        }
        output = StringIO()

        with patch.object(ui, "console", Console(file=output, width=72, force_terminal=False, theme=ui.THEME)):
            ui.chat_tool_card("browser_visual_click", result=result)

        rendered = output.getvalue()
        self.assertIn("page_changed_since_screenshot", rendered)
        self.assertIn("Minha Conta", rendered)
        self.assertNotIn("previa reduzida", rendered)


if __name__ == "__main__":
    unittest.main()