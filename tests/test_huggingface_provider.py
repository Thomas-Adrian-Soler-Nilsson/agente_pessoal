import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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

    @patch.dict(os.environ, {"HF_TOKEN": "", "HF_API_KEY": ""}, clear=False)
    def test_provider_requires_token(self):
        from providers.huggingface_provider import HuggingFaceAgent

        with self.assertRaises(ValueError):
            HuggingFaceAgent(lambda name, args: "ok")

    @patch.dict(os.environ, {"HF_TOKEN": "test-token", "HF_3D_SPACE": "demo/space"}, clear=False)
    def test_generate_3d_uses_space_contract_and_saves_mesh(self):
        from tools import huggingface_multimodal as multimodal

        class FakeClient:
            def __init__(self, space, token):
                self.space = space
                self.token = token
                self.calls = []

            def predict(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return {"mesh": self.mesh}

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "mesh.glb"
            source.write_bytes(b"glb")
            client_holder = {}

            def make_client(space, token):
                client = FakeClient(space, token)
                client.mesh = source
                client_holder["client"] = client
                return client

            with patch("gradio_client.Client", side_effect=make_client), patch(
                "gradio_client.handle_file", side_effect=lambda value: value
            ), patch.object(multimodal, "OUTPUT_ROOT", Path(directory) / "output"):
                result = multimodal.generate_3d("uma cadeira", image_path=str(source))

            client = client_holder["client"]
            args, kwargs = client.calls[0]
            self.assertEqual(args[0], "uma cadeira")
            self.assertEqual(args[1], str(source))
            self.assertEqual(kwargs["api_name"], "/generation_all")
            self.assertIn(".glb", result)

    @patch.dict(os.environ, {"TRIPOSR_DEVICE": "cpu", "TRIPOSR_TIMEOUT": "30"}, clear=False)
    def test_local_triposr_backend_runs_official_script_and_copies_glb(self):
        from tools import triposr

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "TripoSR"
            repo.mkdir()
            (repo / "run.py").write_text("# fake", encoding="utf-8")
            image = root / "rocket.png"
            image.write_bytes(b"png")

            def fake_run(command, **kwargs):
                output_dir = Path(command[command.index("--output-dir") + 1])
                mesh_dir = output_dir / "0"
                mesh_dir.mkdir(parents=True)
                (mesh_dir / "mesh.glb").write_bytes(b"glb")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.dict(os.environ, {"TRIPOSR_PATH": str(repo)}, clear=False), patch(
                "tools.triposr.subprocess.run", side_effect=fake_run
            ), patch.object(triposr, "OUTPUT_ROOT", root / "models"):
                result = triposr.generate_triposr(str(image))

            self.assertIn("Modelo 3D local", result)
            self.assertTrue(any((root / "models").glob("*.glb")))


if __name__ == "__main__":
    unittest.main()
