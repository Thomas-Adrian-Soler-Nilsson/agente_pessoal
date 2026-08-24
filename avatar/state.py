from dataclasses import dataclass


@dataclass
class AvatarState:
    status: str = "idle"
    emotion: str = "neutral"
    intensity: float = 0.0

    def set_status(self, status: str):
        self.status = status

    def set_emotion(
        self,
        emotion: str,
        intensity: float = 1.0,
    ):
        self.emotion = emotion
        self.intensity = max(
            0.0,
            min(1.0, intensity),
        )

    def reset(self):
        self.status = "idle"
        self.emotion = "neutral"
        self.intensity = 0.0