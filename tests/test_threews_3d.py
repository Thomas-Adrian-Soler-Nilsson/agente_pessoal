import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200):
        self.payload = payload or {}
        self.content = content
        self.status_code = status_code
        self.headers = {}
        self.ok = 200 <= status_code < 300
        self.text = str(self.payload)

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.headers = {}
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


class ThreeWsTests(unittest.TestCase):
    def test_free_api_polls_and_saves_glb_without_token(self):
        from tools import threews_3d

        session = FakeSession(
            [
                FakeResponse({"status": "pending", "job": "job-1", "retryAfter": 1}),
                FakeResponse({"status": "done", "glbUrl": "https://cdn.test/rocket.glb"}),
                FakeResponse(content=b"glb-data"),
            ]
        )
        with tempfile.TemporaryDirectory() as directory, patch(
            "tools.threews_3d.requests.Session", return_value=session
        ), patch("tools.threews_3d.time.sleep"), patch.object(
            threews_3d, "BASE_URL", "https://three.ws"
        ), patch(
            "tools.threews_3d._save_url",
            side_effect=lambda current_session, url, stem, service: Path(directory) / "rocket.glb",
        ), patch(
            "tools.threews_3d._finish", return_value="Modelo 3D gerado"
        ):
            result = threews_3d.generate_threews("um foguete")

        self.assertEqual(result, "Modelo 3D gerado")
        self.assertEqual(session.calls[0][1], "https://three.ws/api/3d/generate")
        self.assertEqual(session.calls[0][2]["json"], {"prompt": "um foguete", "format": "glb"})
        self.assertIn("job=job-1", session.calls[1][1])

    def test_free_api_rejects_empty_prompt(self):
        from tools.threews_3d import generate_threews

        with self.assertRaises(ValueError):
            generate_threews("")


if __name__ == "__main__":
    unittest.main()
