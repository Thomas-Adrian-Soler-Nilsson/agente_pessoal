from faster_whisper import WhisperModel


class SpeechToText:

    def __init__(
        self,
        model_size: str = "small",
    ):
        print(
            "🧠 Carregando reconhecimento de voz..."
        )

        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
        )

        print("✅ STT pronto.")

    def transcribe(
        self,
        audio_file: str,
    ) -> str:

        segments, _ = self.model.transcribe(
            audio_file,
            language="pt",
            beam_size=2,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 300
            },
        )

        return " ".join(
            segment.text.strip()
            for segment in segments
        ).strip()