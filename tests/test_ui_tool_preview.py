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


class BrowserActionReadabilityTests(unittest.TestCase):
    """A leitura em tempo real: uma linha por acao, sem UUIDs e sem JSON cru."""

    def _inspect_result(self):
        return {
            "status": "success",
            "operation": "inspect",
            "tab": {"id": 12, "url": "https://chat.deepseek.com/", "title": "DeepSeek"},
            "before": {"url": "https://chat.deepseek.com/", "title": "DeepSeek"},
            "after": {"url": "https://chat.deepseek.com/", "title": "DeepSeek"},
            "data": {
                "url": "https://chat.deepseek.com/",
                "title": "DeepSeek - Rumo ao Desconhecido",
                "elements": [
                    {"element_ref": "540badbe-8855-495f-9651-33fc34c3322e", "role": "textbox", "name": "Mensagem para DeepSeek"},
                    {"element_ref": "845a16fa-d599-4fb9-99ab-df2768769052", "role": "button", "name": ""},
                ],
            },
        }

    def test_inspect_summary_is_one_short_line(self):
        line = ui.browser_action_line("browser_inspect", {"tab_id": 12}, self._inspect_result())
        self.assertEqual(line, "inspect · 2 elementos")

    def test_compact_lines_drop_element_refs_and_name_empty_controls(self):
        rendered = "\n".join(ui.browser_compact_lines(self._inspect_result()))
        self.assertIn("DeepSeek - Rumo ao Desconhecido", rendered)
        self.assertIn("Mensagem para DeepSeek", rendered)
        self.assertIn("(sem nome)", rendered)
        self.assertIn("textbox", rendered)
        self.assertNotIn("540badbe", rendered, "UUID de element_ref não ajuda quem lê")

    def test_press_summary_shows_the_observable_url_change(self):
        result = {
            "status": "success",
            "operation": "press",
            "before": {"url": "https://chat.deepseek.com/", "title": "DeepSeek"},
            "after": {
                "url": "https://chat.deepseek.com/a/chat/s/af7acbf0-dc0c-4994-b5d9-68330662d14a",
                "title": "Oi - DeepSeek",
            },
        }

        line = ui.browser_action_line("browser_press", {"key": "Enter"}, result)

        self.assertIn("press", line)
        self.assertIn("Enter", line)
        self.assertIn("→", line)
        self.assertIn("/a/chat/s/af7acbf0", line)

    def test_fill_summary_shows_value_and_error_code(self):
        result = {"status": "failure", "operation": "fill", "error_code": "stale_element_reference"}

        line = ui.browser_action_line("browser_fill", {"value": "oi"}, result)

        self.assertIn('"oi"', line)
        self.assertIn("stale_element_reference", line)

    def test_visual_click_summary_keeps_the_target_label(self):
        result = {
            "type": "browser_visual_click",
            "status": "failure",
            "error_code": "visual_state_unavailable",
            "target": {"label": "Enviar mensagem", "x": 1584, "y": 200},
        }

        line = ui.browser_action_line("browser_visual_click", {}, result)

        self.assertIn("Enviar mensagem", line)
        self.assertIn("visual_state_unavailable", line)

    def test_card_hides_raw_json_and_verbose_brings_it_back(self):
        output = StringIO()
        with patch.object(ui, "console", Console(file=output, width=110, force_terminal=False, theme=ui.THEME)):
            ui.chat_tool_card("browser_inspect", arguments={"tab_id": 12}, result=self._inspect_result())

        rendered = output.getvalue()
        self.assertIn("inspect · 2 elementos", rendered)
        self.assertIn("Mensagem para DeepSeek", rendered)
        self.assertNotIn("element_ref", rendered, "o JSON cru não deve aparecer por padrão")

        verbose_output = StringIO()
        ui.set_verbose(True)
        try:
            with patch.object(ui, "console", Console(file=verbose_output, width=110, force_terminal=False, theme=ui.THEME)):
                ui.chat_tool_card("browser_inspect", arguments={"tab_id": 12}, result=self._inspect_result())
        finally:
            ui.set_verbose(False)

        self.assertIn("element_ref", verbose_output.getvalue(), "/verboso precisa restaurar o JSON completo")

    def test_pending_notice_is_a_single_line_with_the_value(self):
        output = StringIO()
        with patch.object(ui, "console", Console(file=output, width=100, force_terminal=False, theme=ui.THEME)):
            ui.chat_tool_pending("browser_fill", {"value": "mensagem bem longa " * 4})

        rendered = output.getvalue().strip()
        self.assertEqual(len(rendered.splitlines()), 1)
        self.assertIn("browser_fill", rendered)
        self.assertIn("mensagem bem longa", rendered)


if __name__ == "__main__":
    unittest.main()