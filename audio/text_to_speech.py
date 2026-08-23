import asyncio
import os
import re
import tempfile
import threading
import time

import edge_tts
import numpy as np
import requests
import sounddevice as sd

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

DEFAULT_FISH_VOICES = [
    ("Goku", "dece2a4c7f8d476b8da3c3a6707298d4"),
    ("Lula", "a4ac1426e4a749839c86853ad613eebe"),
    ("Bolsonaro", "92510e31ce4d4737813edc0409c378dc"),
    ("São Cipriano", "0b12d715e4c741399594fccb12d4bbe2"),
    ("Isabela", "5661bf8cb97740fcb10d2f756abf7779"),
    ("Capitão Nascimento", "102bccca7dc64b6b8f8494c199c5d153"),
    ("Loli", "97630cc4349d4a169bf242b8c819081c"),
    ("Fluttershy", "3351971c57f64d14ada2628fdc770112"),
    ("Anya", "ffe41701970d4b339ef7906300716f99"),
]


def available_fish_voices():
    configured = os.getenv("FISH_VOICES", "")
    voices = []
    for item in configured.split(","):
        name, separator, voice_id = item.partition("=")
        if separator and name.strip() and voice_id.strip():
            voices.append((name.strip(), voice_id.strip()))

    if voices:
        return voices

    configured_id = os.getenv("FISH_VOICE_ID") or os.getenv("FISH_REFERENCE_ID")
    if configured_id:
        return [("Voz configurada", configured_id.strip())]

    return DEFAULT_FISH_VOICES


class TextToSpeech:
    def __init__(
        self,
        voice: str = "pt-BR-AntonioNeural",
        rate: str = "+0%",
        fish_voice_id: str | None = None,
    ):
        self.voice = voice
        self.rate = rate
        self.provider = os.getenv("TTS_PROVIDER", "edge").strip().lower()
        if self.provider not in {"edge", "fish"}:
            raise ValueError("TTS_PROVIDER deve ser 'edge' ou 'fish'")
        self.fish_api_key = os.getenv("FISH_API_KEY") or os.getenv("FISH_API")
        self.fish_voice_id = fish_voice_id or os.getenv("FISH_VOICE_ID") or os.getenv("FISH_REFERENCE_ID")
        self.fish_model = os.getenv("FISH_MODEL", "s2.1-pro-free")
        self.stopped = False
        self.interrupt_threshold = float(
            os.getenv("TTS_INTERRUPT_THRESHOLD", "0.08")
        )
        self._monitor_stop = threading.Event()
        self._monitor_thread = None
        pygame.mixer.init()

    @staticmethod
    def _speech_text(text: str, keep_fish_tags: bool = False) -> str:
        text = re.sub(
            r"\[([^\]]+)\]\([^\)]+\)",
            r"\1",
            text,
        )
        text = re.sub(
            r"https?://\S+|www\.\S+",
            " link ",
            text,
        )
        punctuation = r"[`*_#|]" if not keep_fish_tags else r"[`*_#|]"
        text = re.sub(punctuation, " ", text)
        text = re.sub(r"[\\/]", " ", text)
        text = re.sub(r"[-]{2,}", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def _synthesize(self, text: str, output_file: str):
        if self.provider == "fish":
            self._synthesize_fish(text, output_file)
            return

        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=self.rate,
        )
        await communicate.save(output_file)

    def _synthesize_fish(self, text: str, output_file: str):
        if not self.fish_api_key:
            raise ValueError("FISH_API_KEY não encontrada no .env")
        if not self.fish_voice_id:
            raise ValueError("FISH_VOICE_ID não encontrada no .env")

        response = requests.post(
            "https://api.fish.audio/v1/tts",
            headers={
                "Authorization": f"Bearer {self.fish_api_key}",
                "Content-Type": "application/json",
                "model": self.fish_model,
            },
            json={
                "text": text,
                "reference_id": self.fish_voice_id,
                "format": "mp3",
            },
            timeout=60,
        )
        if response.status_code == 402:
            raise RuntimeError(
                "A API Fish Audio recusou a síntese por falta de créditos "
                "ou plano ativo. Verifique o saldo da conta Fish Audio."
            )
        if response.status_code in {401, 403}:
            raise RuntimeError(
                "A chave da API Fish Audio foi recusada. "
                "Confira FISH_API_KEY no .env."
            )
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            detail = response.text.strip()
            if len(detail) > 300:
                detail = detail[:300] + "..."
            raise RuntimeError(
                f"A API Fish Audio retornou HTTP {response.status_code}"
                + (f": {detail}" if detail else ".")
            ) from error
        with open(output_file, "wb") as audio_file:
            audio_file.write(response.content)

    def _monitor_microphone(self):
        speech_frames = 0

        def callback(indata, frames, time_info, status):
            nonlocal speech_frames
            audio = indata.astype(np.float32)
            rms = float(np.sqrt(np.mean(audio * audio)))
            if rms >= self.interrupt_threshold:
                speech_frames += 1
                if speech_frames >= 3:
                    self.stopped = True
                    self._monitor_stop.set()
            else:
                speech_frames = 0

        try:
            with sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                blocksize=480,
                callback=callback,
            ):
                while not self._monitor_stop.is_set():
                    self._monitor_stop.wait(0.05)
        except Exception:
            return

    def _start_microphone_monitor(self):
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_microphone,
            daemon=True,
        )
        self._monitor_thread.start()

    def _stop_microphone_monitor(self):
        self._monitor_stop.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=0.5)
        self._monitor_thread = None

    def speak(self, text: str):
        text = self._speech_text(text, keep_fish_tags=self.provider == "fish")
        if not text:
            return

        self.stopped = False
        output_file = tempfile.NamedTemporaryFile(
            suffix=".mp3",
            delete=False,
        ).name
        try:
            asyncio.run(self._synthesize(text, output_file))
            pygame.mixer.music.load(output_file)
            pygame.mixer.music.play()
            self._start_microphone_monitor()
            while pygame.mixer.music.get_busy() and not self.stopped:
                time.sleep(0.05)
            pygame.mixer.music.stop()
            self._stop_microphone_monitor()
        finally:
            self._stop_microphone_monitor()
            try:
                os.remove(output_file)
            except OSError:
                pass

    def speak_stream(self, chunks):
        self.stopped = False
        collected = []
        sentence = ""
        for chunk in chunks:
            if self.stopped:
                break
            print(chunk, end="", flush=True)
            collected.append(chunk)
            sentence += chunk
            if sentence.rstrip().endswith((".", "!", "?", ":")):
                self.speak(sentence)
                sentence = ""
        if sentence.strip() and not self.stopped:
            self.speak(sentence)
        return self.stopped, "".join(collected).strip()

    def stop(self):
        self.stopped = True
        self._monitor_stop.set()
        pygame.mixer.music.stop()