import os
import unittest
from unittest.mock import patch

from providers.tokenharbor_provider import DEFAULT_TOKENHARBOR_MODELS, TokenHarborAgent, available_models


class TokenHarborProviderTests(unittest.TestCase):
    def test_free_catalog_has_current_default_models(self):
        self.assertEqual(available_models(), DEFAULT_TOKENHARBOR_MODELS)
        self.assertIn("deepseek-v4.1-flash:free", available_models())

    @patch("providers.tokenharbor_provider.OpenAI")
    def test_builds_openai_compatible_client(self, openai):
        with patch.dict(os.environ, {"TOKENHARBOR_API_KEY": "test-key"}, clear=False):
            agent = TokenHarborAgent(lambda name, args: "ok")

        openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://tokenharbor.ai/v1",
        )
        self.assertEqual(agent.model, "deepseek-v4.1-flash:free")


if __name__ == "__main__":
    unittest.main()
