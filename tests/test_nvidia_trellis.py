import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.headers = {}
        self.text = str(payload)

    def json(self):
        return self.payload


class NvidiaTrellisTests(unittest.TestCase):
    @patch.dict(os.environ, {"NVIDIA_TRELLIS_API_KEY": "test-key"}, clear=False)
    def test_text_request_decodes_glb_artifact(self):
        from tools import nvidia_trellis

        encoded = base64.b64encode(b"glb-data").decode("ascii")
        response = FakeResponse({"artifacts": [{"base64": encoded}]})
        with tempfile.TemporaryDirectory() as directory, patch(
            "tools.nvidia_trellis.requests.post", return_value=response
        ) as post, patch.object(nvidia_trellis, "OUTPUT_ROOT", Path(directory) / "models"), patch(
            "tools.nvidia_trellis._finish", return_value="Modelo NVIDIA"
        ):
            result = nvidia_trellis.generate_nvidia_trellis("foguete vermelho")
            self.assertEqual(result, "Modelo NVIDIA")
            request = post.call_args
            self.assertEqual(request.kwargs["json"]["mode"], "text")
            self.assertEqual(request.kwargs["json"]["prompt"], "foguete vermelho")
            self.assertEqual(request.kwargs["headers"]["Authorization"], "Bearer test-key")
            outputs = list((Path(directory) / "models").glob("*.glb"))
            self.assertEqual(len(outputs), 1)
            self.assertEqual(outputs[0].read_bytes(), b"glb-data")

    def test_prompt_limit_is_validated_before_request(self):
        from tools import nvidia_trellis

        with patch("tools.nvidia_trellis.requests.post") as post:
            with self.assertRaises(ValueError):
                nvidia_trellis.generate_nvidia_trellis("x" * 78)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
