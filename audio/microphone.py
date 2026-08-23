import wave

import numpy as np
import sounddevice as sd


class Microphone:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_ms: int = 30,
        silence_duration: float = 0.65,
        max_duration: float = 20.0,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = int(
            sample_rate * chunk_ms / 1000
        )

        self.silence_duration = silence_duration
        self.max_duration = max_duration

    def record(
        self,
        output_file: str = "audio.wav",
    ) -> str:

        print("🎤 Ouvindo...")

        chunks = []
        pre_buffer = []

        speech_started = False
        silence_time = 0.0
        elapsed = 0.0

        noise_samples = []

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=self.chunk_size,
        ) as stream:

            # calibração rápida
            for _ in range(10):
                data, _ = stream.read(
                    self.chunk_size
                )

                audio = (
                    data.astype(np.float32)
                    / 32768.0
                )

                rms = float(
                    np.sqrt(
                        np.mean(audio ** 2)
                    )
                )

                noise_samples.append(rms)

            noise_floor = float(
                np.median(noise_samples)
            )

            threshold = max(
                0.007,
                noise_floor * 2.2
            )

            while elapsed < self.max_duration:

                data, _ = stream.read(
                    self.chunk_size
                )

                data = data.copy()

                audio = (
                    data.astype(np.float32)
                    / 32768.0
                )

                rms = float(
                    np.sqrt(
                        np.mean(audio ** 2)
                    )
                )

                is_speech = rms > threshold

                if not speech_started:

                    pre_buffer.append(data)

                    max_pre_buffer = max(
                        1,
                        int(
                            0.25 /
                            (
                                self.chunk_size
                                / self.sample_rate
                            )
                        ),
                    )

                    if len(pre_buffer) > max_pre_buffer:
                        pre_buffer.pop(0)

                    if is_speech:

                        speech_started = True

                        chunks.extend(
                            pre_buffer
                        )

                        silence_time = 0.0

                else:

                    chunks.append(data)

                    if is_speech:
                        silence_time = 0.0
                    else:
                        silence_time += (
                            self.chunk_size
                            / self.sample_rate
                        )

                    if (
                        silence_time
                        >= self.silence_duration
                    ):
                        break

                elapsed += (
                    self.chunk_size
                    / self.sample_rate
                )

        if not speech_started:
            audio = np.zeros(
                (1, self.channels),
                dtype=np.int16,
            )
        else:
            audio = np.concatenate(
                chunks,
                axis=0,
            )

        with wave.open(
            output_file,
            "wb",
        ) as wav:

            wav.setnchannels(
                self.channels
            )

            wav.setsampwidth(2)

            wav.setframerate(
                self.sample_rate
            )

            wav.writeframes(
                audio.tobytes()
            )

        return output_file