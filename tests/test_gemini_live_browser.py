import asyncio
import base64
import unittest

from gemini_live.client import FUNCTION_DECLARATIONS, GeminiLive


class FakeBrowser:
    def __init__(self):
        self.screenshot_id = "shot-live"
        self.clicks = []
        self.capture = {
            "status": "success",
            "data": {
                "type": "image",
                "mime_type": "image/jpeg",
                "data": base64.b64encode(b"jpeg-bytes").decode("ascii"),
                "screenshot_id": self.screenshot_id,
                "width": 800,
                "height": 600,
            },
        }

    def screenshot(self, tab_id):
        return self.capture

    def click_at(self, tab_id, screenshot_id, x, y, confirmation_token="", expected_label=""):
        self.clicks.append((tab_id, screenshot_id, x, y, confirmation_token, expected_label))
        return {"status": "success", "data": {"clicked": True}}

    def inspect(self, tab_id):
        return {"status": "success", "data": {"title": "Resultado"}}


class FakeVisionAgent:
    def __init__(self, targets=None):
        self.targets = targets or [{
            "label": "Continuar",
            "x": 247,
            "y": 118,
            "confidence": 0.93,
            "actionable": True,
        }]
        self.calls = []

    def analyze(self, image, goal):
        self.calls.append((image, goal))
        return {
            "status": "success",
            "screenshot_id": image["screenshot_id"],
            "analysis": {"status": "targets_found", "targets": self.targets},
        }


class FakeSession:
    def __init__(self):
        self.inputs = []

    async def send_realtime_input(self, **kwargs):
        self.inputs.append(kwargs)


class GeminiLiveBrowserTests(unittest.TestCase):
    def make_agent(self, targets=None):
        agent = GeminiLive.__new__(GeminiLive)
        agent.browser = FakeBrowser()
        agent.vision_agent = FakeVisionAgent(targets)
        return agent

    def test_browser_visual_click_uses_analyzed_screenshot_coordinates(self):
        agent = self.make_agent()

        result = agent._browser_visual_click(42, "Clique em Continuar")

        self.assertEqual(result["status"], "success")
        self.assertEqual(agent.vision_agent.calls[0][1], "Clique em Continuar")
        self.assertEqual(agent.browser.clicks, [(42, "shot-live", 247, 118, "", "Continuar")])
        self.assertEqual(result["target"]["label"], "Continuar")

    def test_browser_visual_click_does_not_click_ambiguous_targets(self):
        targets = [
            {"label": "Continuar", "x": 247, "y": 118, "confidence": 0.9, "actionable": True},
            {"label": "Enviar", "x": 400, "y": 118, "confidence": 0.9, "actionable": True},
        ]
        agent = self.make_agent(targets)

        result = agent._browser_visual_click(42, "Clique em Continuar")

        self.assertEqual(result["status"], "uncertain")
        self.assertEqual(result["error_code"], "ambiguous_visual_target")
        self.assertEqual(agent.browser.clicks, [])

    def test_browser_screenshot_sends_image_bytes_to_live_session(self):
        agent = self.make_agent()
        agent.session = FakeSession()

        result = asyncio.run(agent._send_browser_screenshot(42))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["screenshot_id"], "shot-live")
        self.assertEqual(agent.session.inputs[0]["video"].data, b"jpeg-bytes")

    def test_live_tool_registry_exposes_screenshot_and_visual_click(self):
        names = {tool["name"] for tool in FUNCTION_DECLARATIONS}

        self.assertTrue({"browser_screenshot", "browser_visual_click", "browser_inspect", "browser_list_tabs"}.issubset(names))


if __name__ == "__main__":
    unittest.main()