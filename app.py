import asyncio
import os

from dotenv import load_dotenv

from ui import ui
from gemini_live.client import GeminiLive
from providers.router import ProviderRouter
from screen.screen import Screen
from tools.computer import ComputerTools
from tools.files import FileTools
from tools.image_generation import ImageGenerator
from webcam.webcam import Webcam

load_dotenv()


class LocalToolExecutor:
    def __init__(self, screen, webcam):
        self.screen = screen
        self.webcam = webcam
        self.computer = ComputerTools()
        self.files = FileTools()
        self.images = ImageGenerator()

    def execute(self, name, arguments):
        if name == "open_application":
            return self.computer.open_application(arguments.get("application", ""))
        if name == "open_directory":
            return self.computer.open_directory(arguments.get("path", "~"))
        if name == "open_url":
            return self.computer.open_url(arguments.get("url", ""))
        if name == "list_directory":
            return self.files.list_directory(arguments.get("path", "~"))
        if name == "search_files":
            return self.files.search_files(arguments.get("query", ""), arguments.get("path", "~"))
        if name == "read_file":
            return self.files.read_file(arguments.get("path", ""))
        if name == "get_file_info":
            return self.files.get_file_info(arguments.get("path", ""))
        if name == "capture_screen":
            return {"type": "image", "data": self.screen.capture(), "description": "Captura atual da tela."}
        if name == "capture_webcam":
            return {"type": "image", "data": self.webcam.capture(), "description": "Captura atual da webcam."}
        if name == "generate_image":
            return self.images.generate(arguments.get("prompt", ""))
        return f"Ferramenta desconhecida: {name}"


def select_model(provider_name, models, configured_model):
    rows = [
        {"label": model, "tag": "(configurado)" if model == configured_model else None}
        for model in models
    ]
    ui.menu_table(f"Modelos {provider_name}", rows)
    while True:
        choice = ui.prompt(f"Escolha o modelo [1-{len(models)}] (Enter mantém configuração):")
        choice = choice.strip()
        if not choice:
            return configured_model or models[0]
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice) - 1]
        ui.error("Escolha inválida.")


def _prompt_choice(title, options):
    rows = [{"label": option["label"], "description": option["description"]} for option in options]
    ui.menu_table(title, rows)
    valid = {str(index) for index in range(1, len(options) + 1)}
    while True:
        choice = ui.prompt(f"Escolha [1-{len(options)}]:").strip()
        if choice in valid:
            return options[int(choice) - 1]["id"]
        ui.error("Escolha inválida.")


def _has_key(*names):
    return any(os.getenv(name, "").strip() for name in names)


def select_stt_provider():
    return _prompt_choice(
        "Reconhecimento de voz (STT) — como o agente entende o que você fala:",
        [
            {
                "id": "local",
                "label": "Whisper local (biblioteca faster-whisper)",
                "description": "Roda no PC, sem custo de API. Mais lento e menos preciso; boa opção offline.",
            },
            {
                "id": "groq",
                "label": "Groq Whisper (API)",
                "description": "Rápido e preciso. Precisa de GROQ_API_KEY. Recomendado no dia a dia.",
            },
            {
                "id": "fish",
                "label": "Fish Audio ASR (API)",
                "description": "Transcrição na mesma conta Fish do TTS. Precisa de FISH_API_KEY.",
            },
        ],
    )


def select_tts_provider(*, gemini_live=False):
    if gemini_live:
        gemini = {
            "id": "gemini",
            "label": "Fala nativa do Gemini Live",
            "description": "Voz do próprio Live (Kore): conversa contínua, baixa latência. O Gemini também ouve direto.",
        }
    else:
        gemini = {
            "id": "gemini",
            "label": "Fala do Gemini (API de voz)",
            "description": "Voz natural do Google (Kore), usada só para falar a resposta. Precisa de GEMINI_API_KEY.",
        }
    return _prompt_choice(
        "Fala (TTS) — como o agente responde em voz:",
        [
            gemini,
            {
                "id": "edge",
                "label": "Edge TTS (biblioteca local)",
                "description": "Voz pt-BR gratuita no Windows (Antonio). Estável, sem cobrança extra.",
            },
            {
                "id": "fish",
                "label": "Fish Audio TTS (API)",
                "description": "Clones e emoções (Lula, Bolsonaro, etc.). Precisa de FISH_API_KEY.",
            },
        ],
    )


def select_fish_voice():
    from audio.text_to_speech import available_fish_voices

    voices = available_fish_voices()
    rows = [{"label": f"{name}", "description": voice_id} for name, voice_id in voices]
    ui.menu_table("Vozes Fish Audio", rows)

    while True:
        choice = ui.prompt(f"Escolha a voz [1-{len(voices)}] (Enter mantém a primeira):").strip()
        if not choice:
            return voices[0][1]
        if choice.isdigit() and 1 <= int(choice) <= len(voices):
            return voices[int(choice) - 1][1]
        ui.error("Escolha inválida.")


def _require_audio_keys(stt_provider, tts_provider):
    if stt_provider == "groq" and not _has_key("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY é necessária para o STT da Groq.")
    if stt_provider == "fish" and not _has_key("FISH_API_KEY", "FISH_API"):
        raise ValueError("FISH_API_KEY é necessária para o STT da Fish Audio.")
    if tts_provider == "gemini" and not _has_key("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY é necessária para a fala do Gemini.")
    if tts_provider == "fish" and not _has_key("FISH_API_KEY", "FISH_API"):
        raise ValueError("FISH_API_KEY é necessária para a fala da Fish Audio.")


def run_text_provider(provider_name, agent, stt_provider, tts_provider, fish_voice_id=None):
    from audio.microphone import Microphone
    from audio.speech_to_text import SpeechToText
    from audio.text_to_speech import TextToSpeech, fish_voice_personality

    microphone = Microphone()
    stt = SpeechToText(stt_provider)
    tts = TextToSpeech(
        voice="pt-BR-AntonioNeural",
        rate="+15%",
        fish_voice_id=fish_voice_id,
        provider=tts_provider,
    )
    if tts_provider == "fish":
        agent.set_personality(fish_voice_personality(fish_voice_id))
    ui.module_header(provider_name, icon="💬")
    ui.ok("Pronto. Fale normalmente.")
    recent_context = []
    try:
        while True:
            audio_file = microphone.record(output_file="audio.wav")
            text = stt.transcribe(audio_file, context=" | ".join(recent_context[-3:])).strip()
            if not text:
                continue
            ui.user_line(text)
            if text.lower() in {"sair", "encerrar", "tchau", "desligar"}:
                tts.speak("Até mais.")
                break
            ui.agent_prefix()
            try:
                was_interrupted, spoken = tts.speak_stream(agent.ask_stream(text))
                ui.console.print()
                recent_context.append(f"Usuário: {text}")
                if spoken:
                    recent_context.append(f"Agente: {spoken[:240]}")
                if was_interrupted:
                    ui.interrupted()
            except Exception as error:
                ui.error(f"Erro: {error}")
    except KeyboardInterrupt:
        ui.console.print()
        ui.warn("Encerrando...")
    finally:
        tts.stop()


def menu():
    from providers.groq_provider import available_models as groq_models
    from providers.nvidia_provider import available_models as nvidia_models
    from providers.openrouter_provider import available_models as openrouter_models

    ui.banner()
    rows = [
        {"label": "Gemini Live", "description": "voz nativa, tela e webcam em tempo real"},
        {"label": "Groq", "description": "STT/TTS local · seleção de modelo"},
        {"label": "OpenRouter", "description": "STT/TTS local · seleção de modelo"},
        {"label": "NVIDIA", "description": "STT/TTS local · seleção de modelo"},
        {"label": "Automático", "description": "tenta Groq → OpenRouter → NVIDIA"},
    ]
    ui.menu_table("Modo", rows)
    choice = ui.prompt("Escolha [1-5]:").strip()
    while choice not in {"1", "2", "3", "4", "5"}:
        ui.error("Escolha inválida.")
        choice = ui.prompt("Escolha [1-5]:").strip()
    if choice == "2":
        model = select_model("Groq", groq_models(), os.getenv("GROQ_MODEL"))
        return choice, model, None, None
    if choice == "3":
        model = select_model("OpenRouter", openrouter_models(), os.getenv("OPENROUTER_MODEL"))
        return choice, None, model, None
    if choice == "4":
        model = select_model("NVIDIA", nvidia_models(), os.getenv("NVIDIA_MODEL"))
        return choice, None, None, model
    return choice, None, None, None


def run():
    screen = Screen()
    webcam = Webcam()
    selection = menu()
    if len(selection) == 3:
        choice, groq_model, openrouter_model = selection
        nvidia_model = None
    else:
        choice, groq_model, openrouter_model, nvidia_model = selection
    agent = None
    try:
        from audio.text_to_speech import TextToSpeech

        if choice == "1":
            tts_provider = select_tts_provider(gemini_live=True)
            _require_audio_keys(None, tts_provider)
            external_tts = None
            if tts_provider != "gemini":
                fish_voice_id = select_fish_voice() if tts_provider == "fish" else None
                external_tts = TextToSpeech(
                    voice="pt-BR-AntonioNeural",
                    rate="+15%",
                    fish_voice_id=fish_voice_id,
                    provider=tts_provider,
                )
                ui.status("Escuta: Gemini nativo  |  Fala: biblioteca/API escolhida")
            else:
                ui.status("Escuta e fala: nativas do Gemini Live")
            agent = GeminiLive(screen=screen, webcam=webcam, tts=external_tts)
            asyncio.run(agent.run())
        else:
            stt_provider = select_stt_provider()
            tts_provider = select_tts_provider(gemini_live=False)
            _require_audio_keys(stt_provider, tts_provider)
            fish_voice_id = select_fish_voice() if tts_provider == "fish" else None
            executor = LocalToolExecutor(screen, webcam)
            router = ProviderRouter(executor.execute)
            if choice == "2":
                agent = router.groq(groq_model)
                label = f"Groq ({groq_model})"
            elif choice == "3":
                agent = router.openrouter(openrouter_model)
                label = f"OpenRouter ({openrouter_model})"
            elif choice == "4":
                agent = router.nvidia(nvidia_model)
                label = f"NVIDIA ({nvidia_model})"
            else:
                agent = router.automatic(groq_model, openrouter_model, nvidia_model)
                label = "Modo automático"
            ui.status(f"STT: {stt_provider}  |  TTS: {tts_provider}")
            run_text_provider(label, agent, stt_provider, tts_provider, fish_voice_id)
    except KeyboardInterrupt:
        ui.warn("Encerrando agente...")
    except Exception as error:
        ui.error(f"Erro: {error}")
    finally:
        if choice == "1" and agent is not None:
            agent.close()
        try:
            webcam.close()
        except Exception:
            pass


if __name__ == "__main__":
    run()