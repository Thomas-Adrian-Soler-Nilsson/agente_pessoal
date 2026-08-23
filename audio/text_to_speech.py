import asyncio
import os
import re
import tempfile
import threading
import time

import edge_tts
import numpy as np
import sounddevice as sd

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame


class TextToSpeech:
    def __init__(
        self,
        voice: str = "pt-BR-AntonioNeural",
        rate: str = "+0%",
    ):
        self.voice = voice
        self.rate = rate
        self.stopped = False
        self.interrupt_threshold = float(
            os.getenv("TTS_INTERRUPT_THRESHOLD", "0.08")
        )
        self._monitor_stop = threading.Event()
        self._monitor_thread = None
        pygame.mixer.init()

    @staticmethod
    def _speech_text(text: str) -> str:
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
        text = re.sub(r"[`*_#|]", " ", text)
        text = re.sub(r"[\\/]", " ", text)
        text = re.sub(r"[-]{2,}", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def _synthesize(self, text: str, output_file: str):
        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=self.rate,
        )
        await communicate.save(output_file)

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
        text = self._speech_text(text)
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