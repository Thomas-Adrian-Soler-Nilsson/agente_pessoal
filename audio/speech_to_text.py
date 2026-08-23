import os
import re

from dotenv import load_dotenv

from ui import ui

load_dotenv()

INITIAL_PROMPT = (
    "Transcrição em português do Brasil. "
    "Termos frequentes: OAB, PDF, DOCX, Word, Downloads, OneDrive, "
    "apostila, química, documento, arquivo, pasta, leia, abra, "
    "correto, certo, ENEM."
)

PHRASE_FIXES = [
    (re.compile(r"\b(?:h)?aja correio\b", re.IGNORECASE), "aja correto"),
    (re.compile(r"\bhaja correto\b", re.IGNORECASE), "aja correto"),
    (re.compile(r"\bo a be\b", re.IGNORECASE), "OAB"),
    (re.compile(r"\bo á bê\b", re.IGNORECASE), "OAB"),
    (re.compile(r"\bo a b\b", re.IGNORECASE), "OAB"),
    (re.compile(r"\boab\b", re.IGNORECASE), "OAB"),
]

SPELLED_LETTERS = re.compile(
    r"\b(?:[A-Za-zÀ-ÿ]\s*[.\-]?\s*){1,5}[A-Za-zÀ-ÿ]\.?\b"
)


def _join_spelled_letters(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        letters = re.findall(r"[A-Za-zÀ-ÿ]", match.group(0))
        if 2 <= len(letters) <= 5:
            return "".join(letter.upper() for letter in letters)
        return match.group(0)

    return SPELLED_LETTERS.sub(replace, text)


def _normalize_transcript(text: str) -> str:
    cleaned = " ".join(text.replace("\n", " ").split()).strip()
    cleaned = _join_spelled_letters(cleaned)
    for pattern, replacement in PHRASE_FIXES:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned.strip(" .")


class SpeechToText:
    def __init__(self, provider: str | None = None):
        selected = (provider or os.getenv("STT_PROVIDER", "local")).strip().lower()
        if selected == "auto":
            selected = "groq" if os.getenv("GROQ_API_KEY", "").strip() else "local"
        if selected not in {"local", "groq", "fish"}:
            raise ValueError("STT_PROVIDER deve ser 'local', 'groq' ou 'fish'.")

        self.provider = selected
        self.local_model = None
        self.groq_client = None
        self.groq_model = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
        self.fish_api_key = os.getenv("FISH_API_KEY") or os.getenv("FISH_API")

        if selected == "groq":
            api_key = os.getenv("GROQ_API_KEY", "").strip()
            if not api_key:
                raise ValueError("GROQ_API_KEY é necessária para o STT da Groq.")
            from groq import Groq

            ui.module_header("STT", icon="🎤")
            with ui.spinner("Groq Whisper API (whisper-large-v3)..."):
                self.groq_client = Groq(api_key=api_key)
            ui.ok("STT Groq pronto.")
            return

        if selected == "fish":
            if not self.fish_api_key:
                raise ValueError("FISH_API_KEY é necessária para o STT da Fish Audio.")
            ui.module_header("STT", icon="🎤")
            ui.ok("STT Fish pronto.")
            return

        self._load_local()

    def _load_local(self):
        from faster_whisper import WhisperModel

        model_size = os.getenv("WHISPER_MODEL", "medium").strip() or "medium"
        ui.module_header("STT", icon="🎤")
        with ui.spinner(f"Whisper local ({model_size}, biblioteca faster-whisper)..."):
            self.local_model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
            )
        ui.ok("STT local pronto.")

    def transcribe(self, audio_file: str, context: str = "") -> str:
        prompt = INITIAL_PROMPT
        if context:
            prompt = f"{INITIAL_PROMPT} Contexto recente: {context}"[:800]

        try:
            if self.provider == "groq":
                return self._transcribe_groq(audio_file, prompt)
            if self.provider == "fish":
                return self._transcribe_fish(audio_file)
        except Exception as error:
            ui.warn(f"STT {self.provider} falhou ({error}). Usando Whisper local.")
            if self.local_model is None:
                self._load_local()

        return self._transcribe_local(audio_file, prompt)

    def _transcribe_groq(self, audio_file: str, prompt: str) -> str:
        with open(audio_file, "rb") as audio:
            result = self.groq_client.audio.transcriptions.create(
                file=(os.path.basename(audio_file), audio.read()),
                model=self.groq_model,
                language="pt",
                prompt=prompt,
                temperature=0,
                response_format="text",
            )
        text = result if isinstance(result, str) else getattr(result, "text", "")
        return _normalize_transcript(text or "")

    def _transcribe_fish(self, audio_file: str) -> str:
        import requests

        with open(audio_file, "rb") as audio:
            response = requests.post(
                "https://api.fish.audio/v1/asr",
                headers={"Authorization": f"Bearer {self.fish_api_key}"},
                files={"audio": (os.path.basename(audio_file), audio, "audio/wav")},
                data={"language": "pt", "ignore_timestamps": "true"},
                timeout=60,
            )
        if response.status_code in {401, 403}:
            raise RuntimeError("A chave FISH_API_KEY foi recusada no STT da Fish Audio.")
        response.raise_for_status()
        payload = response.json()
        return _normalize_transcript(payload.get("text") or "")

    def _transcribe_local(self, audio_file: str, prompt: str) -> str:
        segments, info = self.local_model.transcribe(
            audio_file,
            language="pt",
            task="transcribe",
            beam_size=5,
            temperature=0.0,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 700},
            condition_on_previous_text=False,
            initial_prompt=prompt,
            without_timestamps=True,
            no_speech_threshold=0.6,
        )
        if getattr(info, "language_probability", 1.0) < 0.35:
            return ""
        text = " ".join(segment.text.strip() for segment in segments)
        return _normalize_transcript(text)
