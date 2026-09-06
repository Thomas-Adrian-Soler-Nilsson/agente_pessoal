import os
import unittest
from unittest.mock import patch


class HuggingFaceProviderTests(unittest.TestCase):
    @patch.dict(os.environ, {"HF_TOKEN": "test-token", "HF_MODEL": "test-model", "HF_PROVIDER": "auto"}, clear=False)
    @patch("providers.huggingface_provider.CompatibleAgent")
    @patch("providers.huggingface_provider.InferenceClient")
    def test_provider_uses_inference_client_and_compatible_agent(
        self,
        inference_client,
        compatible_agent,
    ):
        from providers.huggingface_provider import HuggingFaceAgent

        agent = HuggingFaceAgent(lambda name, args: "ok")

        inference_client.assert_called_once_with(
            api_key="test-token",
            provider="auto",
        )
        compatible_agent.assert_called_once()
        self.assertEqual(agent.model, "test-model")

    @patch.dict(os.environ, {}, clear=True)
    def test_provider_requires_token(self):
        from providers.huggingface_provider import HuggingFaceAgent

        with self.assertRaises(ValueError):
            HuggingFaceAgent(lambda name, args: "ok")


if __name__ == "__main__":
    unittest.main()
