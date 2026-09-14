import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200):
        self._payload = payload or {}
        self.content = content
        self.status_code = status_code
        self.headers = {}
        self.ok = 200 <= status_code < 300
        self.text = str(self._payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.headers = {}
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET_DOWNLOAD", url, kwargs))
        return self.responses.pop(0)


class Remote3DTests(unittest.TestCase):
    @patch.dict(os.environ, {"RODIN_API_KEY": "test-rodin", "RODIN_TIMEOUT": "30"}, clear=False)
    def test_rodin_submits_polls_downloads_and_saves_glb(self):
        from tools import remote_3d

        session = FakeSession(
            [
                FakeResponse({"uuid": "task-1", "jobs": {"subscription_key": "sub-1"}}),
                FakeResponse({"jobs": [{"status": "Done"}]}),
                FakeResponse({"list": [{"name": "rocket.glb", "url": "https://cdn.test/rocket.glb"}]}),
                FakeResponse(content=b"glb-data"),
            ]
        )
        with tempfile.TemporaryDirectory() as directory, patch(
            "tools.remote_3d.requests.Session", return_value=session
        ), patch("tools.remote_3d.time.sleep"), patch.object(
            remote_3d, "OUTPUT_ROOT", Path(directory) / "models"
        ):
            result = remote_3d.generate_rodin("um foguete")
            self.assertIn("Modelo 3D gerado via Rodin", result)
            self.assertEqual(len(list((Path(directory) / "models").glob("*.glb"))), 1)
        self.assertEqual(session.calls[0][0], "POST")
        self.assertIn("/rodin", session.calls[0][1])
        self.assertEqual(session.calls[1][2]["json"], {"subscription_key": "sub-1"})

    @patch.dict(os.environ, {"TRIFY3D_API_KEY": "test-trify", "TRIFY3D_TIMEOUT": "30"}, clear=False)
    def test_trify_image_payload_contains_required_file_metadata(self):
        from tools import remote_3d

        session = FakeSession(
            [
                FakeResponse({"data": {"taskId": "task-2", "status": "processing"}}),
                FakeResponse({"data": {"status": "completed", "outputModelUrl": "https://cdn.test/chair.glb"}}),
                FakeResponse(content=b"glb-data"),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "chair.png"
            image.write_bytes(b"png-data")
            with patch("tools.remote_3d.requests.Session", return_value=session), patch(
                "tools.remote_3d.time.sleep"
            ), patch.object(remote_3d, "OUTPUT_ROOT", Path(directory) / "models"):
                result = remote_3d.generate_trify(image_path=str(image))
                self.assertIn("Modelo 3D gerado via Trify3D", result)
                self.assertEqual(len(list((Path(directory) / "models").glob("*.glb"))), 1)
                body = session.calls[0][2]["json"]
                self.assertEqual(body["type"], "image_to_3d")
                self.assertEqual(body["fileName"], "chair.png")
                self.assertEqual(body["fileSize"], len(b"png-data"))
                self.assertEqual(body["fileType"], "image/png")
                self.assertTrue(body["imageDataUrl"].startswith("data:image/png;base64,"))
                self.assertTrue(session.headers["Idempotency-Key"])


if __name__ == "__main__":
    unittest.main()
