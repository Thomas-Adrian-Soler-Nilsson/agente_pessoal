from pathlib import Path

from .state import AvatarState
from .expressions import get_expression
from .renderer import AvatarRenderer


AVATAR_DIR = Path(__file__).resolve().parent


def find_model():
    models = list(
        AVATAR_DIR.rglob("*.model3.json")
    )

    if not models:
        raise FileNotFoundError(
            "Nenhum modelo Live2D (.model3.json) foi encontrado "
            f"dentro de: {AVATAR_DIR}"
        )

    for model in models:
        if "miku_free" in str(model).lower():
            return model

    return models[0]


class Avatar:

    def __init__(self, model_path=None):

        if model_path:
            self.model_path = Path(model_path)
        else:
            self.model_path = find_model()

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Modelo não encontrado: {self.model_path}"
            )

        print(
            f"[Avatar] Modelo encontrado: {self.model_path}"
        )

        self.state = AvatarState()

        self.renderer = AvatarRenderer(
            str(self.model_path)
        )

    def start(self):
        self.renderer.start()

        # Estado inicial
        self.renderer.set_status("idle")
        self.renderer.set_expression(
            "neutral",
            0.0,
        )

    def close(self):
        self.renderer.stop()

    def idle(self):
        self.state.set_status("idle")

        self.renderer.set_status(
            "idle"
        )

        self.renderer.set_expression(
            self.state.emotion,
            self.state.intensity,
        )

    def listening(self):
        self.state.set_status(
            "listening"
        )

        self.renderer.set_status(
            "listening"
        )

    def thinking(self):
        self.state.set_status(
            "thinking"
        )

        expression = get_expression(
            "thinking"
        )

        self.renderer.set_status(
            expression["status"]
        )

        self.renderer.set_expression(
            "thinking"
        )

    def speaking(self):
        self.state.set_status(
            "speaking"
        )

        self.renderer.set_status(
            "speaking"
        )

        self.renderer.set_expression(
            self.state.emotion,
            self.state.intensity,
        )

    def set_emotion(
        self,
        emotion: str,
        intensity: float = 1.0,
    ):

        expression = get_expression(
            emotion
        )

        self.state.set_emotion(
            emotion,
            intensity,
        )

        self.renderer.set_status(
            expression["status"]
        )

        self.renderer.set_expression(
            emotion,
            intensity,
        )

    def happy(
        self,
        intensity=1.0,
    ):
        self.set_emotion(
            "happy",
            intensity,
        )

    def sad(
        self,
        intensity=1.0,
    ):
        self.set_emotion(
            "sad",
            intensity,
        )

    def angry(
        self,
        intensity=1.0,
    ):
        self.set_emotion(
            "angry",
            intensity,
        )

    def surprised(
        self,
        intensity=1.0,
    ):
        self.set_emotion(
            "surprised",
            intensity,
        )

    def neutral(self):
        self.set_emotion(
            "neutral",
            0.0,
        )

    def set_state(
        self,
        status: str,
        emotion: str = "neutral",
        intensity: float = 0.0,
    ):

        self.state.set_status(
            status
        )

        self.state.set_emotion(
            emotion,
            intensity,
        )

        self.renderer.set_status(
            status
        )

        self.renderer.set_expression(
            emotion,
            intensity,
        )