import asyncio
import os
import re
import tempfile
import threading
import time
import wave

try:
    import msvcrt
except ImportError:
    msvcrt = None

import edge_tts
import numpy as np
import requests
import sounddevice as sd
from ui import ui

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
    ("Gojo", "96a2c896ed7846848cdd83e484b23eb3"),
    ("Petter Griffin", "6a88fe5df52d49d3a063241edc9f32b9"),
    ("Michel Jackson", "af1d2052ea8d441a972ca51a5bf547e4"),
    ("L Death Note", "4e8e6f7ce2b4444bacdc8b9f47922657")
]


FISH_VOICE_PERSONALITIES = {
    "Goku": (
        "Persona inspirada em um herói shonen alegre e determinado. "
        "Fale com energia, otimismo e curiosidade, trate desafios como treinamento "
        "e incentive o usuário. Seja simples e espontâneo; evite formalidade "
        "e complexidade desnecessária."
    ),
    "Lula": (
        "Persona inspirada no estilo público de um líder sindical e político brasileiro. "
        "Fale de modo caloroso, popular e persuasivo, usando exemplos do cotidiano "
        "e valorizando diálogo e inclusão."
    ),
    "Bolsonaro": (
        "Persona inspirada no estilo público de um político brasileiro de fala direta. "
        "Seja objetivo, informal e assertivo, com humor seco quando couber."
    ),
    "São Cipriano": (
        "Persona inspirada em uma figura tradicional de misticismo popular. "
        "Fale com serenidade, solenidade e um toque enigmático, oferecendo "
        "conselhos práticos e respeitosos."
    ),
    "Isabela": (
        "Persona de uma mulher brasileira acolhedora, perspicaz e confiante. "
        "Fale com calma, empatia e clareza, percebendo nuances e ajudando "
        "o usuário a organizar as ideias sem soar formal demais."
    ),
    "Capitão Nascimento": (
        "Persona inspirada em um instrutor militar fictício, disciplinado e exigente. "
        "Seja firme, direto e pragmático, transforme tarefas em objetivos claros "
        "e cobre foco sem humilhar, ameaçar ou incentivar violência."
    ),
    "Loli": (
        "Persona de uma personagem jovem fictícia, fofa e muito animada. "
        "Use linguagem leve, curiosidade e entusiasmo, mantendo conteúdo apropriado "
        "e sem sexualização. Não afirme ser uma personagem existente."
    ),
    "Fluttershy": (
        "Persona inspirada em uma personagem fictícia gentil e tímida. "
        "Fale suavemente, com empatia e carinho por animais e pessoas, "
        "mas demonstre coragem quando necessário."
    ),
    "Anya": (
        "Persona inspirada em uma personagem infantil fictícia, expressiva e brincalhona. "
        "Use frases curtas, curiosidade e humor inocente, mantendo o conteúdo "
        "apropriado para todas as idades."
    ),
    "Gojo": (
        "Persona inspirada em um personagem fictício confiante e espirituoso. "
        "Fale com humor, sarcasmo leve e inteligência, mantendo o conteúdo "
        "apropriado e evitando referências a violência ou sexualidade."
    ),
    "Petter Griffin": (
        "Persona inspirada em um personagem fictício de comédia. "
        "Fale com humor, sarcasmo e ironia, mantendo o conteúdo apropriado "
        "e evitando referências a violência ou sexualidade."
    ),
    "Michel Jackson": (
        "Persona inspirada em um cantor e dançarino fictício. "
        "Fale com ritmo, emoção e entusiasmo, mantendo o conteúdo apropriado "
        "e evitando referências a violência ou sexualidade."
    ),
    "L Death Note": (
        "Persona inspirada em um personagem fictício de anime. "
        "Fale com inteligência, mistério e calma, mantendo o conteúdo apropriado "
        "e evitando referências a violência ou sexualidade."
    ),
}


def available_fish_voices():
    configured = os.getenv("FISH_VOICES", "")
    voices = []

    for item in configured.split(","):
        name, separator, voice_id = item.partition("=")

        if separator and name.strip() and voice_id.strip():
            voices.append((name.strip(), voice_id.strip()))

    if voices:
        return voices

    configured_id = (
        os.getenv("FISH_VOICE_ID")
        or os.getenv("FISH_REFERENCE_ID")
    )

    if configured_id:
        return [("Voz configurada", configured_id.strip())]

    return DEFAULT_FISH_VOICES


def fish_voice_personality(voice_id: str | None) -> str:
    selected_name = ""

    for name, configured_id in DEFAULT_FISH_VOICES:
        if configured_id == voice_id:
            selected_name = name
            break

    for name, configured_id in available_fish_voices():
        if configured_id == voice_id:
            selected_name = name
            break

    if not selected_name:
        return ""

    return (
        f"A persona escolhida para esta sessão é {selected_name}. "
        f"Você é {selected_name} durante a interpretação. "
        "Responda em primeira pessoa como essa persona e mantenha sua identidade, "
        "vocabulário e atitude em todas as respostas. Não diga que é um agente, "
        "assistente pessoal, modelo de IA ou sistema; se perguntarem quem você é, "
        f"responda que é {selected_name}. "
        + FISH_VOICE_PERSONALITIES.get(selected_name, "")
        + " Use marcadores de emoção do Fish Audio no texto que será falado: "
        "[happy], [excited], [calm], [empathetic], [curious], [confident], "
        "[laughing], [sighing], [whispering] ou [surprised]. "
        "Coloque o marcador no começo da frase que ele deve influenciar, use "
        "no máximo um ou dois por frase, escolha a emoção de acordo com o contexto "
        "e não escreva explicações sobre os marcadores. Os marcadores são instruções "
        "para a voz e não devem ser pronunciados como palavras."
    )


class TextToSpeech:
    def __init__(
        self,
        voice: str = "pt-BR-AntonioNeural",
        rate: str = "+0%",
        fish_voice_id: str | None = None,
        provider: str | None = None,
    ):
        self.voice = voice
        self.rate = rate
        self.provider = (
            provider or os.getenv("TTS_PROVIDER", "edge")
        ).strip().lower()

        if self.provider not in {"edge", "fish", "gemini"}:
            raise ValueError(
                "TTS_PROVIDER deve ser 'edge', 'fish' ou 'gemini'"
            )

        # ---------------------------------------------------------
        # FISH AUDIO
        # ---------------------------------------------------------

        self.fish_api_key = (
            os.getenv("FISH_API_KEY")
            or os.getenv("FISH_API")
        )

        self.fish_voice_id = (
            fish_voice_id
            or os.getenv("FISH_VOICE_ID")
            or os.getenv("FISH_REFERENCE_ID")
        )

        self.fish_model = os.getenv(
            "FISH_MODEL",
            "s2.1-pro-free",
        )

        # ---------------------------------------------------------
        # GEMINI
        # ---------------------------------------------------------

        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

        self.gemini_tts_model = os.getenv(
            "GEMINI_TTS_MODEL",
            "gemini-2.5-flash-preview-tts",
        )

        self.gemini_tts_voice = os.getenv(
            "GEMINI_TTS_VOICE",
            "Kore",
        )

        # ---------------------------------------------------------
        # CONTROLE DE REPRODUÇÃO
        # ---------------------------------------------------------

        self.stopped = False

        self.interrupt_enabled = (
            os.getenv(
                "TTS_INTERRUPT_ENABLED",
                "false",
            )
            .strip()
            .lower()
            in {
                "1",
                "true",
                "sim",
                "yes",
            }
        )

        self._interrupt_requested = threading.Event()

        self.interrupt_delay = float(
            os.getenv(
                "TTS_INTERRUPT_DELAY",
                "0.7",
            )
        )

        self.interrupt_threshold = float(
            os.getenv(
                "TTS_INTERRUPT_THRESHOLD",
                "0.08",
            )
        )

        self._monitor_stop = threading.Event()
        self._monitor_thread = None
        self._keyboard_thread = None

        pygame.mixer.init()

    # =============================================================
    # LIMPEZA DO TEXTO
    # =============================================================

    @staticmethod
    def _speech_text(
        text: str,
        keep_fish_tags: bool = False,
    ) -> str:
        text = re.sub(
            r"\[([^\]]+)\]\([^)]+\)",
            r"\1",
            text,
        )

        text = re.sub(
            r"https?://\S+|www\.\S+",
            " link ",
            text,
        )

        punctuation = r"[`*_#|]"
        text = re.sub(
            punctuation,
            " ",
            text,
        )

        if not keep_fish_tags:
            text = re.sub(
                r"\[[^\]]+\]",
                " ",
                text,
            )

        text = re.sub(
            r"[\\/]",
            " ",
            text,
        )

        text = re.sub(
            r"[-]{2,}",
            " ",
            text,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # =============================================================
    # SÍNTESE
    # =============================================================

    async def _synthesize(
        self,
        text: str,
        output_file: str,
    ):
        if self.provider == "fish":
            self._synthesize_fish(
                text,
                output_file,
            )
            return

        if self.provider == "gemini":
            self._synthesize_gemini(
                text,
                output_file,
            )
            return

        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=self.rate,
        )

        await communicate.save(
            output_file,
        )

    # =============================================================
    # GEMINI TTS
    # =============================================================

    def _synthesize_gemini(
        self,
        text: str,
        output_file: str,
    ):
        if not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY não encontrada no .env"
            )

        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=self.gemini_api_key,
        )

        response = client.models.generate_content(
            model=self.gemini_tts_model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=self.gemini_tts_voice
                        )
                    )
                ),
            ),
        )

        part = response.candidates[0].content.parts[0]
        blob = part.inline_data
        data = blob.data

        mime = (
            getattr(
                blob,
                "mime_type",
                None,
            )
            or ""
        ).lower()

        if "wav" in mime or data[:4] == b"RIFF":
            with open(
                output_file,
                "wb",
            ) as audio_file:
                audio_file.write(data)

            return

        with wave.open(
            output_file,
            "wb",
        ) as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(data)

    # =============================================================
    # FISH AUDIO TTS
    # =============================================================

    def _synthesize_fish(
        self,
        text: str,
        output_file: str,
    ):
        if not self.fish_api_key:
            raise ValueError(
                "FISH_API_KEY não encontrada no .env"
            )

        if not self.fish_voice_id:
            raise ValueError(
                "FISH_VOICE_ID não encontrada no .env"
            )

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
                f"A API Fish Audio retornou HTTP "
                f"{response.status_code}"
                + (
                    f": {detail}"
                    if detail
                    else "."
                )
            ) from error

        with open(
            output_file,
            "wb",
        ) as audio_file:
            audio_file.write(
                response.content
            )

    # =============================================================
    # MONITORAMENTO DO MICROFONE
    # =============================================================

    def _monitor_microphone(self):
        speech_frames = 0

        def callback(
            indata,
            frames,
            time_info,
            status,
        ):
            nonlocal speech_frames

            audio = indata.astype(
                np.float32
            )

            rms = float(
                np.sqrt(
                    np.mean(
                        audio * audio
                    )
                )
            )

            if rms >= self.interrupt_threshold:
                speech_frames += 1

                if speech_frames >= 3:
                    self.stopped = True
                    self._interrupt_requested.set()
                    self._monitor_stop.set()
                    pygame.mixer.music.stop()

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

    # =============================================================
    # MONITORAMENTO DO TECLADO
    # =============================================================

    def _monitor_keyboard(self):
        if msvcrt is None:
            return

        while not self._monitor_stop.is_set():
            if msvcrt.kbhit():
                key = msvcrt.getwch()

                if key == "\x1b":
                    self.stopped = True
                    self._interrupt_requested.set()
                    self._monitor_stop.set()
                    pygame.mixer.music.stop()
                    return

            self._monitor_stop.wait(0.05)

    def _start_keyboard_monitor(self):
        self._keyboard_thread = threading.Thread(
            target=self._monitor_keyboard,
            daemon=True,
        )

        self._keyboard_thread.start()

    # =============================================================
    # PARAR MONITORES
    # =============================================================

    def _stop_microphone_monitor(self):
        self._monitor_stop.set()

        if (
            self._monitor_thread
            and self._monitor_thread.is_alive()
        ):
            self._monitor_thread.join(
                timeout=0.5
            )

        self._monitor_thread = None

        if (
            self._keyboard_thread
            and self._keyboard_thread.is_alive()
        ):
            self._keyboard_thread.join(
                timeout=0.5
            )

        self._keyboard_thread = None

    # =============================================================
    # FALAR UMA RESPOSTA COMPLETA
    # =============================================================

    def speak(
        self,
        text: str,
    ):
        text = self._speech_text(
            text,
            keep_fish_tags=self.provider == "fish",
        )

        if not text:
            return

        self.stopped = False

        suffix = (
            ".wav"
            if self.provider == "gemini"
            else ".mp3"
        )

        output_file = tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ).name

        try:
            asyncio.run(
                self._synthesize(
                    text,
                    output_file,
                )
            )

            if self.stopped:
                return

            pygame.mixer.music.load(
                output_file
            )

            pygame.mixer.music.play()

            self._start_keyboard_monitor()

            if self.interrupt_enabled:
                time.sleep(
                    self.interrupt_delay
                )

                if not self.stopped:
                    self._start_microphone_monitor()

            while (
                pygame.mixer.music.get_busy()
                and not self.stopped
            ):
                time.sleep(0.05)

            pygame.mixer.music.stop()

            self._stop_microphone_monitor()

        finally:
            self._stop_microphone_monitor()

            try:
                os.remove(
                    output_file
                )
            except OSError:
                pass

    # =============================================================
    # AGRUPAMENTO DE FRASES
    # =============================================================

    def _extract_speech_block(
        self,
        buffer: str,
        force: bool = False,
    ):
        """
        Extrai um bloco de fala sem cortar frases.

        O bloco:
        - sempre termina em pontuação natural;
        - tenta juntar várias frases;
        - evita chamadas pequenas demais ao TTS;
        - nunca corta uma palavra ou frase arbitrariamente.

        Retorna:
            (bloco_pronto, restante)
        """

        text = buffer.strip()

        if not text:
            return None, buffer

        # ---------------------------------------------------------
        # Procura todos os finais de frase existentes.
        # ---------------------------------------------------------

        matches = list(
            re.finditer(
                r"[.!?…](?:[\"'»”)]*)?(?=\s|$)",
                text,
            )
        )

        if not matches:
            if force:
                return text, ""

            return None, buffer

        # ---------------------------------------------------------
        # Queremos agrupar algumas frases antes de falar.
        #
        # Isso evita:
        #
        # "Oi!" -> TTS
        # "Tudo bem?" -> TTS
        #
        # E prefere:
        #
        # "Oi! Tudo bem? Como você está?"
        # -> TTS
        # ---------------------------------------------------------

        for match in matches:
            candidate_end = match.end()
            candidate = text[:candidate_end].strip()

            # Se já temos um bloco razoável, podemos enviar.
            if len(candidate) >= 120:
                remaining = text[candidate_end:].strip()
                return candidate, remaining

        # ---------------------------------------------------------
        # Se existe uma resposta curta, junta todas as frases
        # disponíveis que chegaram até agora.
        # ---------------------------------------------------------

        last_match = matches[-1]
        candidate_end = last_match.end()

        candidate = text[:candidate_end].strip()

        # Se já chegou uma quantidade razoável de texto,
        # fala o bloco inteiro.
        if len(candidate) >= 60:
            remaining = text[candidate_end:].strip()
            return candidate, remaining

        # ---------------------------------------------------------
        # Se o modelo terminou a resposta, não deixa sobra sem falar.
        # ---------------------------------------------------------

        if force:
            remaining = text[candidate_end:].strip()

            if remaining:
                return candidate, remaining

            return candidate, ""

        return None, buffer

    # =============================================================
    # STREAMING → TTS
    # =============================================================

    def speak_stream(
        self,
        chunks,
    ):
        """
        Recebe chunks do LLM e transforma o texto em blocos naturais
        para o TTS.

        Diferente da versão anterior, não envia uma requisição Fish
        para cada frase curta.

        Exemplo:

            "Oi! "
            "Tudo bem? "
            "O que você está fazendo?"

        vira preferencialmente:

            "Oi! Tudo bem? O que você está fazendo?"

        Isso reduz as pausas artificiais entre frases.
        """

        self.stopped = False
        self._interrupt_requested.clear()

        collected = []
        buffer = ""

        for chunk in chunks:
            if self.stopped:
                break

            if not chunk:
                continue

            ui.console.print(
                chunk,
                style="agent",
                end="",
                highlight=False,
            )

            collected.append(chunk)
            buffer += chunk

            # -----------------------------------------------------
            # Extrai blocos completos enquanto possível.
            # -----------------------------------------------------

            while not self.stopped:
                block, remaining = self._extract_speech_block(
                    buffer
                )

                if block is None:
                    break

                buffer = remaining

                if block.strip():
                    self.speak(
                        block.strip()
                    )

        # ---------------------------------------------------------
        # Fim da resposta.
        #
        # Não deixa texto sobrando.
        # ---------------------------------------------------------

        while (
            buffer.strip()
            and not self.stopped
        ):
            block, remaining = self._extract_speech_block(
                buffer,
                force=True,
            )

            if not block:
                break

            buffer = remaining

            self.speak(
                block.strip()
            )

        return (
            self.stopped,
            "".join(
                collected
            ).strip(),
        )

    # =============================================================
    # INTERRUPÇÃO EXTERNA
    # =============================================================

    def stop(self):
        self.stopped = True

        self._interrupt_requested.set()

        self._monitor_stop.set()

        pygame.mixer.music.stop()