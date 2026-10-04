import unittest
from unittest.mock import patch

from providers.vision_agent import VisionAgent, _decode_analysis


class VisionAgentTests(unittest.TestCase):
    def test_analysis_stops_fallback_chain_at_total_deadline(self):
        candidates = [
            {"id": f"provider/model-{index}", "provider": "gemini", "model": f"model-{index}", "transport": "gemini"}
            for index in range(4)
        ]
        agent = VisionAgent(candidates)
        clock = [0.0]
        timeouts = []

        def fail_provider(_candidate, _image, _prompt, timeout=None):
            timeouts.append(timeout)
            clock[0] += timeout
            raise TimeoutError("provider timeout")

        with patch("time.monotonic", side_effect=lambda: clock[0]), patch.object(
            agent, "_call_openai_compatible", side_effect=fail_provider
        ):
            result = agent.analyze(
                {"width": 800, "height": 600, "data": "image-data", "mime_type": "image/jpeg", "screenshot_id": "shot-1"},
                "Clique em Minha Conta",
            )

        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["error_code"], "vision_analysis_deadline_exceeded")
        self.assertEqual(len(timeouts), 3)
        self.assertEqual(timeouts, [8.0, 8.0, 4.0])

    def test_rejects_boolean_coordinates_and_confidence(self):
        malformed = (
            '{"status":"targets_found","targets":['
            '{"label":"Entrar","x":true,"y":20,"confidence":0.99},'
            '{"label":"Continuar","x":20,"y":30,"confidence":true}'
            ']}'
        )

        with self.assertRaisesRegex(ValueError, "vision_targets_invalid"):
            _decode_analysis(malformed, width=800, height=600)

    def test_rejects_string_coordinates(self):
        malformed = (
            '{"status":"targets_found","targets":['
            '{"label":"Entrar","x":"20","y":"30","confidence":0.99}'
            ']}'
        )

        with self.assertRaisesRegex(ValueError, "vision_targets_invalid"):
            _decode_analysis(malformed, width=800, height=600)


if __name__ == "__main__":
    unittest.main()
