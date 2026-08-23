import os
import wave

import numpy as np
import sounddevice as sd

from ui import ui


class Microphone:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_ms: int = 30,
        silence_duration: float | None = None,
        max_duration: float = 25.0,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = int(sample_rate * chunk_ms / 1000)
        self.silence_duration = silence_duration or float(
            os.getenv("MIC_SILENCE_DURATION", "1.15")
        )
        self.max_duration = max_duration
        self.pre_roll = float(os.getenv("MIC_PRE_ROLL", "0.55"))

    def record(self, output_file: str = "audio.wav") -> str:
        ui.console.print("[info]🎤 Ouvindo...[/info]")

        chunks = []
        pre_buffer = []
        speech_started = False
        silence_time = 0.0
        elapsed = 0.0
        noise_samples = []
        chunk_seconds = self.chunk_size / self.sample_rate
        max_pre_buffer = max(1, int(self.pre_roll / chunk_seconds))

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=self.chunk_size,
        ) as stream:
            for _ in range(20):
                data, _ = stream.read(self.chunk_size)
                audio = data.astype(np.float32) / 32768.0
                noise_samples.append(float(np.sqrt(np.mean(audio ** 2))))

            noise_floor = float(np.percentile(noise_samples, 35))
            start_threshold = max(0.006, noise_floor * 2.4)
            hold_threshold = start_threshold * 0.5

            while elapsed < self.max_duration:
                data, _ = stream.read(self.chunk_size)
                data = data.copy()
                audio = data.astype(np.float32) / 32768.0
                rms = float(np.sqrt(np.mean(audio ** 2)))
                threshold = hold_threshold if speech_started else start_threshold
                is_speech = rms > threshold

                if not speech_started:
                    pre_buffer.append(data)
                    if len(pre_buffer) > max_pre_buffer:
                        pre_buffer.pop(0)
                    if is_speech:
                        speech_started = True
                        chunks.extend(pre_buffer)
                        silence_time = 0.0
                else:
                    chunks.append(data)
                    if is_speech:
                        silence_time = 0.0
                    else:
                        silence_time += chunk_seconds
                    if silence_time >= self.silence_duration:
                        break

                elapsed += chunk_seconds

        if not speech_started or not chunks:
            audio = np.zeros((1, self.channels), dtype=np.int16)
        else:
            audio = np.concatenate(chunks, axis=0)
            pad = np.zeros((int(self.sample_rate * 0.2), self.channels), dtype=np.int16)
            audio = np.concatenate([pad, audio, pad], axis=0)

        with wave.open(output_file, "wb") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(audio.tobytes())

        return output_file
