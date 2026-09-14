import unittest

from providers.huggingface_catalog import available_models


class HuggingFaceCatalogTests(unittest.TestCase):
    def test_north_mini_code_is_available_for_chat(self):
        self.assertIn("CohereLabs/North-Mini-Code-1.0", available_models("chat"))


if __name__ == "__main__":
    unittest.main()
