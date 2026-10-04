import unittest
from unittest.mock import patch

from providers.vision_agent import VisionAgent, _COOLDOWN, _decode_analysis


class VisionAgentTests(unittest.TestCase):
    def setUp(self):
        # _COOLDOWN é estado de módulo compartilhado entre análises.
        _COOLDOWN.clear()

    def tearDown(self):
        _COOLDOWN.clear()

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


    def test_normalized_coordinates_are_converted_to_pixels(self):
        """O contrato agora é 0-1000; a conversão para pixels é feita no código."""
        analysis = _decode_analysis(
            '{"status":"targets_found","targets":['
            '{"label":"Enviar","x":500,"y":250,"confidence":0.9}'
            ']}',
            width=1582,
            height=1104,
        )

        target = analysis["targets"][0]
        self.assertEqual(target["x"], round(500 / 1000 * 1582))
        self.assertEqual(target["y"], round(250 / 1000 * 1104))
        self.assertEqual((target["x"], target["y"]), (791, 276))

    def test_edges_of_the_normalized_scale_stay_inside_the_image(self):
        analysis = _decode_analysis(
            '{"status":"targets_found","targets":['
            '{"label":"Canto","x":1000,"y":1000,"confidence":0.9}'
            ']}',
            width=100,
            height=50,
        )

        target = analysis["targets"][0]
        self.assertEqual((target["x"], target["y"]), (99, 49))

    def test_coordinates_above_the_normalized_scale_are_rejected(self):
        """Risco documentado: um modelo que responda em pixels (1200 numa imagem
        de 1582) tem o alvo descartado, porque o contrato agora é 0-1000."""
        with self.assertRaisesRegex(ValueError, "vision_targets_invalid"):
            _decode_analysis(
                '{"status":"targets_found","targets":['
                '{"label":"Enviar","x":1200,"y":300,"confidence":0.9}'
                ']}',
                width=1582,
                height=1104,
            )

    def test_provider_in_cooldown_is_skipped_on_the_next_analysis(self):
        candidates = [
            {"id": "openrouter/model-x", "provider": "openrouter", "model": "model-x", "transport": "openrouter"}
        ]
        agent = VisionAgent(candidates)
        calls = []

        class RateLimited(RuntimeError):
            status_code = 429

        def fail(_candidate, _image, _prompt, timeout=None):
            calls.append(1)
            raise RateLimited("429 too many requests")

        image = {
            "width": 800,
            "height": 600,
            "data": "image-data",
            "mime_type": "image/jpeg",
            "screenshot_id": "shot-1",
        }

        with patch.object(agent, "_call_openai_compatible", side_effect=fail):
            first = agent.analyze(image, "Clique em Enviar")
            second = agent.analyze(image, "Clique em Enviar")

        self.assertEqual(first["attempts"][0]["error_code"], "http_429")
        self.assertEqual(len(calls), 1, "provedor em cooldown não pode ser tentado de novo")
        self.assertEqual(second["error_code"], "all_vision_providers_failed")
        self.assertEqual(second["attempts"], [])

    def test_original_cause_is_logged_locally_and_not_sent_to_the_model(self):
        candidates = [
            {"id": "gemini/vision-x", "provider": "gemini", "model": "vision-x", "transport": "gemini"}
        ]
        agent = VisionAgent(candidates)
        image = {
            "width": 800,
            "height": 600,
            "data": "image-data",
            "mime_type": "image/jpeg",
            "screenshot_id": "shot-1",
        }

        with patch.object(agent, "_call_openai_compatible", return_value="isto nao e json"):
            with self.assertLogs("providers.vision_agent", level="DEBUG") as captured:
                result = agent.analyze(image, "Clique em Enviar")

        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["attempts"][0]["error_code"], "ValueError")
        self.assertNotIn("invalid_vision_json", str(result))
        self.assertTrue(
            any("invalid_vision_json" in line for line in captured.output),
            "a causa original precisa ficar registrada no log local: " + str(captured.output),
        )


if __name__ == "__main__":
    unittest.main()
