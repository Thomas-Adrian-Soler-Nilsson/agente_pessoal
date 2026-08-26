import asyncio
import os

from dotenv import load_dotenv

from ui import ui
from gemini_live.client import GeminiLive
from providers.router import ProviderRouter
from screen.screen import Screen
from tools.computer import ComputerTools
from tools.browser import BrowserTools
from tools.files import FileTools
from tools.image_generation import ImageGenerator
from webcam.webcam import Webcam
from avatar.avatar import Avatar
from tools.web_search import search_and_read
from tools import web_search as search_web

load_dotenv()


# ============================================================
# FERRAMENTAS LOCAIS
# ============================================================

class LocalToolExecutor:
    def __init__(self, screen, webcam):
        self.screen = screen
        self.webcam = webcam

        self.computer = ComputerTools()
        self.browser = BrowserTools()
        self.files = FileTools()
        self.images = ImageGenerator()

    def execute(self, name, arguments):
        arguments = arguments or {}

        if name == "open_application":
            return self.computer.open_application(
                arguments.get("application", "")
            )
        if name == "web_search":
            return search_and_read(arguments.get("query", ""))

        if name == "deep_search":
            return search_web.deep_search(arguments.get("query", ""))

        if name == "code_search":
            return search_web.code_search(arguments.get("query", ""))

        if name == "open_directory":
            return self.computer.open_directory(
                arguments.get("path", "~")
            )

        if name == "open_url":
            return self.computer.open_url(
                arguments.get("url", "")
            )

        if name == "browser_navigate":
            return self.browser.navigate(arguments.get("url", ""))

        if name == "browser_read":
            return self.browser.read(arguments.get("max_chars"))

        if name == "browser_click":
            return self.browser.click(arguments.get("selector", ""))

        if name == "browser_fill":
            return self.browser.fill(
                arguments.get("selector", ""),
                arguments.get("value", ""),
            )

        if name == "list_directory":
            return self.files.list_directory(
                arguments.get("path", "~")
            )

        if name == "search_files":
            return self.files.search_files(
                arguments.get("query", ""),
                arguments.get("path", "~"),
            )

        if name == "read_file":
            return self.files.read_file(
                arguments.get("path", "")
            )

        if name == "get_file_info":
            return self.files.get_file_info(
                arguments.get("path", "")
            )

        if name == "capture_screen":
            return {
                "type": "image",
                "data": self.screen.capture(),
                "description": "Captura atual da tela.",
            }

        if name == "capture_webcam":
            return {
                "type": "image",
                "data": self.webcam.capture(),
                "description": "Captura atual da webcam.",
            }

        if name == "generate_image":
            return self.images.generate(
                arguments.get("prompt", "")
            )

        return f"Ferramenta desconhecida: {name}"


# ============================================================
# UTILITÁRIOS
# ============================================================

def _has_key(*names):
    return any(
        os.getenv(name, "").strip()
        for name in names
    )


def _prompt_choice(title, options):
    rows = [
        {
            "label": option["label"],
            "description": option["description"],
        }
        for option in options
    ]

    ui.menu_table(title, rows)

    valid = {
        str(index)
        for index in range(1, len(options) + 1)
    }

    while True:
        choice = ui.prompt(
            f"Escolha [1-{len(options)}]:"
        ).strip()

        if choice in valid:
            return options[int(choice) - 1]["id"]

        ui.error("Escolha inválida.")


# ============================================================
# SELEÇÃO DE MODELOS
# ============================================================

def select_model(provider_name, models, configured_model):
    if not models:
        raise ValueError(
            f"Nenhum modelo disponível para {provider_name}."
        )

    rows = [
        {
            "label": model,
            "tag": "(configurado)"
            if model == configured_model
            else None,
        }
        for model in models
    ]

    ui.menu_table(
        f"Modelos {provider_name}",
        rows,
    )

    while True:
        choice = ui.prompt(
            f"Escolha o modelo [1-{len(models)}] "
            "(Enter mantém configuração):"
        ).strip()

        if not choice:
            return configured_model or models[0]

        if (
            choice.isdigit()
            and 1 <= int(choice) <= len(models)
        ):
            return models[int(choice) - 1]

        ui.error("Escolha inválida.")


# ============================================================
# STT
# ============================================================

def select_stt_provider():
    return _prompt_choice(
        "Reconhecimento de voz (STT) — como o agente entende o que você fala:",
        [
            {
                "id": "local",
                "label": "Whisper local (faster-whisper)",
                "description": (
                    "Roda no PC sem custo de API. "
                    "Boa opção offline."
                ),
            },
            {
                "id": "groq",
                "label": "Groq Whisper (API)",
                "description": (
                    "Muito rápido e preciso. "
                    "Precisa de GROQ_API_KEY."
                ),
            },
            {
                "id": "fish",
                "label": "Fish Audio ASR (API)",
                "description": (
                    "Transcrição usando a conta Fish Audio. "
                    "Precisa de FISH_API_KEY."
                ),
            },
        ],
    )


# ============================================================
# TTS
# ============================================================

def select_tts_provider(*, gemini_live=False):
    if gemini_live:
        gemini_option = {
            "id": "gemini",
            "label": "Fala nativa do Gemini Live",
            "description": (
                "Voz nativa do Gemini Live com "
                "conversa contínua e baixa latência."
            ),
        }
    else:
        gemini_option = {
            "id": "gemini",
            "label": "Gemini TTS",
            "description": (
                "Voz natural do Google. "
                "Precisa de GEMINI_API_KEY."
            ),
        }

    return _prompt_choice(
        "Fala (TTS) — como o agente responde em voz:",
        [
            gemini_option,
            {
                "id": "edge",
                "label": "Edge TTS",
                "description": (
                    "Voz pt-BR gratuita. "
                    "Sem cobrança adicional."
                ),
            },
            {
                "id": "fish",
                "label": "Fish Audio TTS",
                "description": (
                    "Vozes com clonagem e emoções. "
                    "Precisa de FISH_API_KEY."
                ),
            },
        ],
    )


def select_fish_voice():
    from audio.text_to_speech import available_fish_voices

    voices = available_fish_voices()

    if not voices:
        raise ValueError(
            "Nenhuma voz Fish Audio disponível."
        )

    rows = [
        {
            "label": name,
            "description": voice_id,
        }
        for name, voice_id in voices
    ]

    ui.menu_table(
        "Vozes Fish Audio",
        rows,
    )

    while True:
        choice = ui.prompt(
            f"Escolha a voz [1-{len(voices)}] "
            "(Enter mantém a primeira):"
        ).strip()

        if not choice:
            return voices[0][1]

        if (
            choice.isdigit()
            and 1 <= int(choice) <= len(voices)
        ):
            return voices[int(choice) - 1][1]

        ui.error("Escolha inválida.")


# ============================================================
# VALIDAÇÃO DE CHAVES
# ============================================================

def _require_audio_keys(
    stt_provider,
    tts_provider,
):
    if (
        stt_provider == "groq"
        and not _has_key("GROQ_API_KEY")
    ):
        raise ValueError(
            "GROQ_API_KEY é necessária para o STT da Groq."
        )

    if (
        stt_provider == "fish"
        and not _has_key(
            "FISH_API_KEY",
            "FISH_API",
        )
    ):
        raise ValueError(
            "FISH_API_KEY é necessária para o STT da Fish Audio."
        )

    if (
        tts_provider == "gemini"
        and not _has_key("GEMINI_API_KEY")
    ):
        raise ValueError(
            "GEMINI_API_KEY é necessária para o TTS do Gemini."
        )

    if (
        tts_provider == "fish"
        and not _has_key(
            "FISH_API_KEY",
            "FISH_API",
        )
    ):
        raise ValueError(
            "FISH_API_KEY é necessária para o TTS da Fish Audio."
        )


# ============================================================
# MENU PRINCIPAL
# ============================================================

def menu():
    from providers.groq_provider import (
        available_models as groq_models,
    )

    from providers.mistral_provider import (
        available_models as mistral_models,
    )

    from providers.nvidia_provider import (
        available_models as nvidia_models,
    )

    from providers.openrouter_provider import (
        available_models as openrouter_models,
    )

    from providers.ollama_provider import (
        available_models as ollama_models,
    )

    ui.banner()

    rows = [
        {
            "label": "Gemini Live",
            "description": (
                "voz nativa, tela e webcam em tempo real"
            ),
        },
        {
            "label": "Groq",
            "description": (
                "modelos rápidos com seleção de modelo"
            ),
        },
        {
            "label": "Mistral",
            "description": (
                "modelos Mistral com seleção de modelo"
            ),
        },
        {
            "label": "OpenRouter",
            "description": (
                "acesso a diversos modelos"
            ),
        },
        {
            "label": "NVIDIA",
            "description": (
                "modelos NVIDIA NIM"
            ),
        },
        {
            "label": "Ollama",
            "description": (
                "modelos locais ou remotos"
            ),
        },
        {
            "label": "Automático",
            "description": (
                "Groq → Mistral → OpenRouter → NVIDIA"
            ),
        },
    ]

    ui.menu_table(
        "Modo",
        rows,
    )

    choice = ui.prompt(
        "Escolha [1-7]:"
    ).strip()

    while choice not in {
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
    }:
        ui.error("Escolha inválida.")

        choice = ui.prompt(
            "Escolha [1-7]:"
        ).strip()

    # Gemini Live
    if choice == "1":
        return {
            "choice": choice,
            "groq_model": None,
            "mistral_model": None,
            "openrouter_model": None,
            "nvidia_model": None,
            "ollama_model": None,
        }

    # Groq
    if choice == "2":
        model = select_model(
            "Groq",
            groq_models(),
            os.getenv("GROQ_MODEL"),
        )

        return {
            "choice": choice,
            "groq_model": model,
            "mistral_model": None,
            "openrouter_model": None,
            "nvidia_model": None,
            "ollama_model": None,
        }

    # Mistral
    if choice == "3":
        model = select_model(
            "Mistral",
            mistral_models(),
            os.getenv("MISTRAL_MODEL"),
        )

        return {
            "choice": choice,
            "groq_model": None,
            "mistral_model": model,
            "openrouter_model": None,
            "nvidia_model": None,
            "ollama_model": None,
        }

    # OpenRouter
    if choice == "4":
        model = select_model(
            "OpenRouter",
            openrouter_models(),
            os.getenv("OPENROUTER_MODEL"),
        )

        return {
            "choice": choice,
            "groq_model": None,
            "mistral_model": None,
            "openrouter_model": model,
            "nvidia_model": None,
            "ollama_model": None,
        }

    # NVIDIA
    if choice == "5":
        model = select_model(
            "NVIDIA",
            nvidia_models(),
            os.getenv("NVIDIA_MODEL"),
        )

        return {
            "choice": choice,
            "groq_model": None,
            "mistral_model": None,
            "openrouter_model": None,
            "nvidia_model": model,
            "ollama_model": None,
        }

    # Ollama
    if choice == "6":
        model = select_model(
            "Ollama",
            ollama_models(),
            os.getenv("OLLAMA_MODEL"),
        )

        return {
            "choice": choice,
            "groq_model": None,
            "mistral_model": None,
            "openrouter_model": None,
            "nvidia_model": None,
            "ollama_model": model,
        }

    # Automático
    return {
        "choice": choice,
        "groq_model": None,
        "mistral_model": None,
        "openrouter_model": None,
        "nvidia_model": None,
        "ollama_model": None,
    }


# ============================================================
# EXECUÇÃO DO PROVIDER DE TEXTO
# ============================================================

def run_text_provider(
    provider_name,
    agent,
    stt_provider,
    tts_provider,
    fish_voice_id=None,
    avatar=None,
):
    from audio.microphone import Microphone
    from audio.speech_to_text import SpeechToText
    from audio.text_to_speech import (
        TextToSpeech,
        fish_voice_personality,
    )

    microphone = Microphone()

    stt = SpeechToText(
        stt_provider
    )

    tts = TextToSpeech(
        voice="pt-BR-AntonioNeural",
        rate="+15%",
        fish_voice_id=fish_voice_id,
        provider=tts_provider,
    )

    if (
        tts_provider == "fish"
        and fish_voice_id
    ):
        agent.set_personality(
            fish_voice_personality(
                fish_voice_id
            )
        )

    ui.module_header(
        provider_name,
        icon="💬",
    )

    ui.ok(
        "Pronto. Fale normalmente."
    )

    recent_context = []

    try:
        while True:

            # ----------------------------------------------
            # AVATAR — ESCUTANDO
            # ----------------------------------------------

            if avatar:
                avatar.listening()

            audio_file = microphone.record(
                output_file="audio.wav"
            )

            text = stt.transcribe(
                audio_file,
                context=" | ".join(
                    recent_context[-3:]
                ),
            ).strip()

            if not text:
                if avatar:
                    avatar.idle()

                continue

            ui.user_line(text)

            # ----------------------------------------------
            # COMANDOS DE SAÍDA
            # ----------------------------------------------

            if text.lower() in {
                "sair",
                "encerrar",
                "tchau",
                "desligar",
            }:

                if avatar:
                    avatar.happy(0.6)

                tts.speak(
                    "Até mais."
                )

                break

            # ----------------------------------------------
            # AVATAR — PENSANDO
            # ----------------------------------------------

            if avatar:
                avatar.thinking()

            ui.agent_prefix()

            try:

                # ------------------------------------------
                # AVATAR — FALANDO
                # ------------------------------------------

                if avatar:
                    avatar.speaking()

                was_interrupted, spoken = (
                    tts.speak_stream(
                        agent.ask_stream(text)
                    )
                )

                ui.console.print()

                # ------------------------------------------
                # CONTEXTO RECENTE
                # ------------------------------------------

                recent_context.append(
                    f"Usuário: {text}"
                )

                if spoken:
                    recent_context.append(
                        f"Agente: {spoken[:240]}"
                    )

                # ------------------------------------------
                # INTERRUPÇÃO
                # ------------------------------------------

                if was_interrupted:

                    if avatar:
                        avatar.listening()

                    ui.interrupted()

                else:

                    if avatar:
                        avatar.idle()

            except Exception as error:

                if avatar:
                    avatar.neutral()

                ui.error(
                    f"Erro: {error}"
                )

    except KeyboardInterrupt:

        ui.console.print()

        ui.warn(
            "Encerrando..."
        )

    finally:

        if avatar:
            avatar.idle()

        tts.stop()


# ============================================================
# GEMINI LIVE
# ============================================================

def run_gemini_live(
    screen,
    webcam,
    avatar,
):
    from audio.text_to_speech import TextToSpeech

    tts_provider = select_tts_provider(
        gemini_live=True
    )

    _require_audio_keys(
        None,
        tts_provider,
    )

    external_tts = None

    if tts_provider != "gemini":

        fish_voice_id = (
            select_fish_voice()
            if tts_provider == "fish"
            else None
        )

        external_tts = TextToSpeech(
            voice="pt-BR-AntonioNeural",
            rate="+15%",
            fish_voice_id=fish_voice_id,
            provider=tts_provider,
        )

        ui.status(
            "Escuta: Gemini nativo  | "
            "Fala: biblioteca/API escolhida"
        )

    else:

        ui.status(
            "Escuta e fala: nativas do Gemini Live"
        )

    if avatar:
        avatar.listening()

    agent = GeminiLive(
        screen=screen,
        webcam=webcam,
        tts=external_tts,
    )

    try:
        asyncio.run(
            agent.run()
        )
    finally:
        if external_tts:
            try:
                external_tts.stop()
            except Exception:
                pass

        try:
            agent.close()
        except Exception:
            pass


# ============================================================
# PROVIDERS DE TEXTO
# ============================================================

def create_text_agent(
    router,
    choice,
    groq_model=None,
    mistral_model=None,
    openrouter_model=None,
    nvidia_model=None,
    ollama_model=None,
):
    if choice == "2":

        agent = router.groq(
            groq_model
        )

        label = (
            f"Groq ({groq_model})"
        )

        return agent, label

    if choice == "3":

        agent = router.mistral(
            mistral_model
        )

        label = (
            f"Mistral ({mistral_model})"
        )

        return agent, label

    if choice == "4":

        agent = router.openrouter(
            openrouter_model
        )

        label = (
            f"OpenRouter ({openrouter_model})"
        )

        return agent, label

    if choice == "5":

        agent = router.nvidia(
            nvidia_model
        )

        label = (
            f"NVIDIA ({nvidia_model})"
        )

        return agent, label

    if choice == "6":

        agent = router.ollama(
            ollama_model
        )

        label = (
            f"Ollama ({ollama_model})"
        )

        return agent, label

    # Automático
    agent = router.automatic(
        groq_model,
        openrouter_model,
        nvidia_model,
        mistral_model,
    )

    label = "Modo automático"

    return agent, label


def run_text_mode(
    screen,
    webcam,
    avatar,
    selection,
):
    stt_provider = select_stt_provider()

    tts_provider = select_tts_provider(
        gemini_live=False
    )

    _require_audio_keys(
        stt_provider,
        tts_provider,
    )

    fish_voice_id = (
        select_fish_voice()
        if tts_provider == "fish"
        else None
    )

    executor = LocalToolExecutor(
        screen,
        webcam,
    )

    router = ProviderRouter(
        executor.execute
    )

    agent, label = create_text_agent(
        router,
        selection["choice"],
        selection["groq_model"],
        selection["mistral_model"],
        selection["openrouter_model"],
        selection["nvidia_model"],
        selection["ollama_model"],
    )

    ui.status(
        f"STT: {stt_provider}  | "
        f"TTS: {tts_provider}"
    )

    run_text_provider(
        label,
        agent,
        stt_provider,
        tts_provider,
        fish_voice_id,
        avatar=avatar,
    )


# ============================================================
# AVATAR
# ============================================================

def start_avatar():
    try:

        avatar = Avatar()

        avatar.start()

        ui.ok(
            "Avatar Live2D iniciado."
        )

        return avatar

    except Exception as error:

        ui.warn(
            f"Avatar indisponível: {error}"
        )

        return None


def close_avatar(avatar):
    if not avatar:
        return

    try:
        avatar.close()
    except Exception:
        pass


# ============================================================
# APLICAÇÃO PRINCIPAL
# ============================================================

def run():
    screen = Screen()
    webcam = Webcam()

    avatar = None
    selection = None

    try:

        # ----------------------------------------------
        # MENU
        # ----------------------------------------------

        selection = menu()

        # ----------------------------------------------
        # AVATAR
        # ----------------------------------------------

        avatar = start_avatar()

        # ----------------------------------------------
        # GEMINI LIVE
        # ----------------------------------------------

        if selection["choice"] == "1":

            run_gemini_live(
                screen,
                webcam,
                avatar,
            )

        # ----------------------------------------------
        # PROVIDERS DE TEXTO
        # ----------------------------------------------

        else:

            run_text_mode(
                screen,
                webcam,
                avatar,
                selection,
            )

    except KeyboardInterrupt:

        ui.warn(
            "Encerrando agente..."
        )

        if avatar:
            try:
                avatar.neutral()
            except Exception:
                pass

    except Exception as error:

        if avatar:
            try:
                avatar.neutral()
            except Exception:
                pass

        ui.error(
            f"Erro: {error}"
        )

    finally:

        # ----------------------------------------------
        # AVATAR
        # ----------------------------------------------

        close_avatar(
            avatar
        )

        # ----------------------------------------------
        # WEBCAM
        # ----------------------------------------------

        try:
            webcam.close()
        except Exception:
            pass


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    run()
