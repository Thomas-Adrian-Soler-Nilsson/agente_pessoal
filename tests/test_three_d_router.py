import os
import unittest
from unittest.mock import patch


class ThreeDRouterTests(unittest.TestCase):
    @patch.dict(os.environ, {"NVIDIA_TRELLIS_API_KEY": "configured"}, clear=False)
    @patch("tools.three_d_router.generate_nvidia_trellis", return_value="nvidia-result")
    @patch("tools.three_d_router.generate_threews", return_value="free-result")
    def test_prefers_nvidia_when_key_is_configured(self, free, nvidia):
        from tools.three_d_router import generate_3d_auto

        self.assertEqual(generate_3d_auto("foguete"), "nvidia-result")
        nvidia.assert_called_once_with("foguete", None, None)
        free.assert_not_called()

    @patch.dict(os.environ, {"NVIDIA_TRELLIS_API_KEY": "configured"}, clear=False)
    @patch("tools.three_d_router.generate_nvidia_trellis", side_effect=RuntimeError("indisponível"))
    @patch("tools.three_d_router.generate_threews", return_value="free-result")
    def test_falls_back_to_free_text_generation(self, free, nvidia):
        from tools.three_d_router import generate_3d_auto

        self.assertEqual(generate_3d_auto("foguete"), "free-result")
        nvidia.assert_called_once()
        free.assert_called_once_with("foguete", None)

    @patch.dict(os.environ, {"HF_TOKEN": "configured"}, clear=False)
    @patch("tools.three_d_router.generate_hf_3d", return_value="hf-result")
    @patch("tools.three_d_router.generate_threews", return_value="free-result")
    def test_uses_huggingface_when_token_is_configured(self, free, hf):
        from tools.three_d_router import generate_3d_auto

        self.assertEqual(generate_3d_auto("mão de fps"), "hf-result")
        hf.assert_called_once_with("mão de fps", image_path=None)
        free.assert_not_called()


if __name__ == "__main__":
    unittest.main()
