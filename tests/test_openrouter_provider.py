import os
import unittest
from unittest.mock import patch

from providers.openrouter_provider import available_models


class OpenRouterCatalogTests(unittest.TestCase):
    def test_default_catalog_contains_chat_and_multimodal_models(self):
        with patch.dict(os.environ, {"OPENROUTER_MODELS": ""}, clear=False):
            models = available_models()

        self.assertIn("inclusionai/ling-3.0-flash-vl:free", models)
        self.assertIn("nex-agi/nex-n2.5-pro:free", models)
        self.assertIn("cohere/north-mini-code:free", models)
        self.assertNotIn("liquid/lfm-2.5-embedding-350m:free", models)

    def test_configured_catalog_is_trimmed_and_deduplicated(self):
        with patch.dict(
            os.environ,
            {"OPENROUTER_MODELS": " foo/bar:free, foo/bar:free , baz/qux:free "},
            clear=False,
        ):
            self.assertEqual(
                ["foo/bar:free", "baz/qux:free"],
                available_models(),
            )


if __name__ == "__main__":
    unittest.main()
