import os
import subprocess
import uuid
from pathlib import Path

from huggingface_hub import InferenceClient

from ui import ui


DEFAULT_MODEL = "black-forest-labs/FLUX.1-schnell"


class ImageGenerator:
    def __init__(self, output_dir: str | None = None):
        self.api_key = (
            os.getenv("HF_TOKEN")
            or os.getenv("HF_API_KEY")
            or ""
        ).strip()

        self.model = (
            os.getenv("HF_IMAGE_MODEL")
            or DEFAULT_MODEL
        ).strip()

        self.provider = (
            os.getenv("HF_IMAGE_PROVIDER")
            or "auto"
        ).strip()

        self.output_dir = Path(
            output_dir
            or (
                Path.home()
                / "Pictures"
                / "AgentePessoal"
            )
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.client = None

        if self.api_key:
            self.client = InferenceClient(
                provider=self.provider,
                api_key=self.api_key,
            )

    def generate(self, prompt: str) -> str:
        prompt = (prompt or "").strip()

        if not prompt:
            return "Descreva o que a imagem deve conter."

        if not self.client:
            return (
                "HF_TOKEN não configurado. "
                "Adicione sua chave do Hugging Face no .env."
            )

        ui.module_header(
            "Imagem",
            icon="🎨",
        )

        try:
            with ui.spinner(
                f"Gerando imagem via Hugging Face "
                f"({self.model})..."
            ):
                image = self.client.text_to_image(
                    prompt=prompt,
                    model=self.model,
                )

        except Exception as error:
            ui.error(
                f"Erro ao gerar imagem: {error}"
            )

            return (
                "Não consegui gerar a imagem agora. "
                "Verifique o modelo, provider e seu token "
                "do Hugging Face."
            )

        filename = (
            f"imagem_{uuid.uuid4().hex[:8]}.png"
        )

        path = self.output_dir / filename

        try:
            image.save(path)
        except Exception as error:
            ui.error(
                f"Erro ao salvar imagem: {error}"
            )

            return (
                "A imagem foi gerada, mas não consegui "
                "salvá-la localmente."
            )

        ui.ok(
            f"Imagem salva em {path}"
        )

        self._open(path)

        return (
            "Imagem gerada com sucesso e "
            f"salva em: {path}"
        )

    @staticmethod
    def _open(path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(
                    str(path)
                )
            else:
                subprocess.Popen(
                    [
                        "xdg-open",
                        str(path),
                    ]
                )

        except Exception:
            pass