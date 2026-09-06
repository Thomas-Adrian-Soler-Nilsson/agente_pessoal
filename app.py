import asyncio
import os
import threading

from dotenv import load_dotenv
from prompt_toolkit import prompt as terminal_prompt

from ui import ui
from gemini_live.client import GeminiLive
from providers.router import ProviderRouter
from providers.huggingface_catalog import available_models as hf_models
from screen.screen import Screen
from tools.computer import ComputerTools
from tools.browser import BrowserTools
from tools.files import FileTools
from tools.image_generation import ImageGenerator
from tools.huggingface_multimodal import hf_tool_executor
from webcam.webcam import Webcam
from tools.web_search import search_and_read
from tools import web_search as search_web

Avatar = None
load_dotenv()


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
            return self.computer.open_application(arguments.get("application", ""))
        if name == "open_directory":
            return self.computer.open_directory(arguments.get("path", "~"))
        if name == "open_url":
            return self.computer.open_url(arguments.get("url", ""))
        if name == "web_search":
            return search_and_read(arguments.get("query", ""))
        if name == "deep_search":
            return search_web.deep_search(arguments.get("query", ""))
        if name == "code_search":
            return search_web.code_search(arguments.get("query", ""))
        if name == "browser_navigate":
            return self.browser.navigate(arguments.get("url", ""))
        if name == "browser_read":
            return self.browser.read(arguments.get("max_chars"))
        if name == "browser_click":
            return self.browser.click(arguments.get("selector", ""))
        if name == "browser_fill":
            return self.browser.fill(arguments.get("selector", ""), arguments.get("value", ""))
        if name == "list_directory":
            return self.files.list_directory(arguments.get("path", "~"))
        if name == "inspect_project":
            return self.files.inspect_project(arguments.get("path", ""), arguments.get("max_chars", 24000))
        if name == "search_files":
            return self.files.search_files(arguments.get("query", ""), arguments.get("path", "~"))
        if name == "read_file":
            return self.files.read_file(arguments.get("path", ""))
        if name == "read_file_range":
            return self.files.read_file_range(arguments.get("path", ""), arguments.get("start_line", 1), arguments.get("end_line", 200))
        if name == "write_file":
            result = self.files.write_file(arguments.get("path", ""), arguments.get("content", ""))
            path = arguments.get("path", "")
            if "sucesso" in result.lower() and path.lower().endswith((".py", ".js", ".html", ".htm")):
                result += "\n" + self.files.validate_file(path)
            return result
        if name == "write_file_chunk":
            return self.files.write_file_chunk(arguments.get("path", ""), arguments.get("content", ""), arguments.get("append", True))
        if name == "edit_file":
            result = self.files.edit_file(arguments.get("path", ""), arguments.get("find", ""), arguments.get("replace", ""), arguments.get("expected_replacements", 1))
            path = arguments.get("path", "")
            if "sucesso" in result.lower() and path.lower().endswith((".py", ".js", ".html", ".htm")):
                result += "\n" + self.files.validate_file(path)
            return result
        if name == "execute_file":
            return self.files.execute_file(arguments.get("path", ""))
        if name == "validate_file":
            return self.files.validate_file(arguments.get("path", ""))
        if name == "get_file_info":
            return self.files.get_file_info(arguments.get("path", ""))
        if name == "capture_screen":
            return {"type": "image", "data": self.screen.capture(), "description": "Captura atual da tela."}
        if name == "capture_webcam":
            return {"type": "image", "data": self.webcam.capture(), "description": "Captura atual da webcam."}
        if name == "generate_image":
            return self.images.generate(arguments.get("prompt", ""))
        return f"Ferramenta desconhecida: {name}"

    def execute_huggingface(self, name, arguments):
        return hf_tool_executor(name, arguments, self.execute)


def _has_key(*names):
    return any(os.getenv(name, "").strip() for name in names)


def _prompt_choice(title, options):
    rows = [{"label": option["label"], "description": option["description"]} for option in options]
    ui.menu_table(title, rows)
    valid = {str(index) for index in range(1, len(options) + 1)}
    while True:
        choice = ui.prompt(f"Escolha [1-{len(options)}]:").strip()
        if choice in valid:
            return options[int(choice) - 1]["id"]
        ui.error("Escolha inválida.")


def _chat_prompt():
    return terminal_prompt("Você › ")


def select_avatar_enabled():
    ui.section("Personalização")
    ui.dialog("Modelo 3D", "☐  Exibir modelo 3D\n\nO avatar fica desligado por padrão e só será carregado se você confirmar esta opção.", subtitle="Recurso opcional · nenhum processamento em segundo plano")
    while True:
        choice = ui.prompt("☐ Exibir modelo 3D [s/N]:").strip().lower()
        if choice in {"", "n", "nao", "não", "0"}:
            ui.status("Modelo 3D: desativado")
            return False
        if choice in {"s", "sim", "y", "yes", "1"}:
            ui.ok("Modelo 3D: ativado")
            return True
        ui.error("Escolha s para exibir ou Enter para manter desativado.")


def select_model(provider_name, models, configured_model):
    if not models:
        raise ValueError(f"Nenhum modelo disponível para {provider_name}.")
    rows = [{"label": model, "tag": "(configurado)" if model == configured_model else None} for model in models]
    ui.menu_table(f"Modelos {provider_name}", rows)
    while True:
        choice = ui.prompt(f"Escolha o modelo [1-{len(models)}] (Enter mantém configuração):").strip()
        if not choice:
            return configured_model or models[0]
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice) - 1]
        ui.error("Escolha inválida.")


def select_stt_provider():
    return _prompt_choice("Reconhecimento de voz (STT) — como o agente entende o que você fala:", [
        {"id": "local", "label": "Whisper local (faster-whisper)", "description": "Roda no PC sem custo de API. Boa opção offline."},
        {"id": "groq", "label": "Groq Whisper (API)", "description": "Muito rápido e preciso. Precisa de GROQ_API_KEY."},
        {"id": "fish", "label": "Fish Audio ASR (API)", "description": "Transcrição usando a conta Fish Audio. Precisa de FISH_API_KEY."},
    ])


def select_tts_provider(*, gemini_live=False):
    return _prompt_choice("Fala (TTS) — como o agente responde em voz:", [
        {"id": "gemini", "label": "Fala nativa do Gemini Live" if gemini_live else "Gemini TTS", "description": "Voz natural do Google. Precisa de GEMINI_API_KEY."},
        {"id": "edge", "label": "Edge TTS", "description": "Voz pt-BR gratuita. Sem cobrança adicional."},
        {"id": "fish", "label": "Fish Audio TTS", "description": "Vozes com clonagem e emoções. Precisa de FISH_API_KEY."},
        {"id": "huggingface", "label": "Hugging Face TTS", "description": "Modelos open-weight como Qwen3-TTS e Kokoro."},
    ])


def select_fish_voice():
    from audio.text_to_speech import available_fish_voices
    voices = available_fish_voices()
    if not voices:
        raise ValueError("Nenhuma voz Fish Audio disponível.")
    ui.menu_table("Vozes Fish Audio", [{"label": name, "description": voice_id} for name, voice_id in voices])
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
        raise ValueError("GEMINI_API_KEY é necessária para o TTS do Gemini.")
    if tts_provider == "fish" and not _has_key("FISH_API_KEY", "FISH_API"):
        raise ValueError("FISH_API_KEY é necessária para o TTS da Fish Audio.")
    if tts_provider == "huggingface" and not _has_key("HF_TOKEN", "HF_API_KEY"):
        raise ValueError("HF_TOKEN ou HF_API_KEY é necessária para o TTS do Hugging Face.")


def menu():
    from providers.groq_provider import available_models as groq_models
    from providers.mistral_provider import available_models as mistral_models
    from providers.nvidia_provider import available_models as nvidia_models
    from providers.openrouter_provider import available_models as openrouter_models
    from providers.ollama_provider import available_models as ollama_models

    ui.banner()
    rows = [
        {"label": "Gemini Live", "description": "voz nativa, tela e webcam em tempo real"},
        {"label": "Groq", "description": "modelos rápidos com seleção de modelo"},
        {"label": "Mistral", "description": "modelos Mistral com seleção de modelo"},
        {"label": "OpenRouter", "description": "acesso a diversos modelos"},
        {"label": "NVIDIA", "description": "modelos NVIDIA NIM"},
        {"label": "Ollama", "description": "modelos locais ou remotos"},
        {"label": "Hugging Face", "description": "chat, visão e modelos generativos open-weight"},
        {"label": "Automático", "description": "Groq → Mistral → OpenRouter → NVIDIA → Hugging Face"},
    ]
    choice = _prompt_choice("Modo", [{"id": str(i + 1), **row} for i, row in enumerate(rows)])

    base = {"choice": choice, "groq_model": None, "mistral_model": None, "openrouter_model": None, "nvidia_model": None, "ollama_model": None, "huggingface_model": None}
    if choice == "1":
        return base
    if choice == "2":
        base["groq_model"] = select_model("Groq", groq_models(), os.getenv("GROQ_MODEL")); return base
    if choice == "3":
        base["mistral_model"] = select_model("Mistral", mistral_models(), os.getenv("MISTRAL_MODEL")); return base
    if choice == "4":
        base["openrouter_model"] = select_model("OpenRouter", openrouter_models(), os.getenv("OPENROUTER_MODEL")); return base
    if choice == "5":
        base["nvidia_model"] = select_model("NVIDIA", nvidia_models(), os.getenv("NVIDIA_MODEL")); return base
    if choice == "6":
        base["ollama_model"] = select_model("Ollama", ollama_models(), os.getenv("OLLAMA_MODEL")); return base
    if choice == "7":
        base["huggingface_model"] = select_model("Hugging Face", hf_models("chat"), os.getenv("HF_MODEL")); return base
    return base


def run_text_provider(provider_name, agent, stt_provider, tts_provider, fish_voice_id=None, avatar=None):
    from audio.microphone import Microphone
    from audio.speech_to_text import SpeechToText
    from audio.text_to_speech import TextToSpeech, fish_voice_personality
    microphone = None
    stt = None
    tts = TextToSpeech(voice="pt-BR-AntonioNeural", rate="+15%", fish_voice_id=fish_voice_id, provider=tts_provider)
    if tts_provider == "fish" and fish_voice_id:
        agent.set_personality(fish_voice_personality(fish_voice_id))
    ui.module_header(provider_name, icon="💬")
    ui.ok("Pronto. Digite no CMD. Use /voz para falar pelo microfone.")
    recent_context = []
    response_thread = None
    speech_thread = None
    response_cancel_event = None
    response_lock = threading.Lock()
    agent_lock = threading.Lock()
    response_id = 0

    def process_message(text, current_response_id, cancel_event):
        nonlocal response_thread, speech_thread
        acquired = False
        try:
            while not cancel_event.is_set():
                if agent_lock.acquire(timeout=0.1): acquired = True; break
            if not acquired or cancel_event.is_set(): return
            with response_lock:
                if current_response_id != response_id or cancel_event.is_set(): return
            if avatar and not cancel_event.is_set(): avatar.thinking()
            ui.chat_agent_prefix()
            if avatar and not cancel_event.is_set(): avatar.speaking()
            spoken = "".join(agent.ask_stream(text, cancel_event=cancel_event))
            if cancel_event.is_set(): return
            display_text = tts._speech_text(spoken)
            if display_text: ui.chat_response(display_text)
            speech_thread = threading.Thread(target=tts.speak, args=(spoken,), kwargs={"cancel_event": cancel_event}, daemon=True)
            speech_thread.start()
            with response_lock: still_current = current_response_id == response_id
            if still_current and not cancel_event.is_set():
                recent_context.append(f"Usuário: {text}")
                if spoken: recent_context.append(f"Agente: {spoken[:500]}")
                if avatar: avatar.idle()
        except Exception as error:
            with response_lock: still_current = current_response_id == response_id
            if still_current and not cancel_event.is_set():
                if avatar: avatar.neutral()
                ui.error(f"Erro: {error}")
        finally:
            with response_lock:
                if current_response_id == response_id: response_thread = None
            if acquired: agent_lock.release()

    try:
        while True:
            if avatar: avatar.idle()
            text = _chat_prompt().strip()
            if not text: continue
            if text.lower() in {"/voz", "voz", "/voice"}:
                with response_lock:
                    response_id += 1
                    if response_cancel_event is not None: response_cancel_event.set()
                tts.stop()
                if speech_thread is not None: speech_thread.join(timeout=0.5)
                if avatar: avatar.listening()
                ui.info("🎤 Fale agora...")
                if microphone is None: microphone = Microphone()
                if stt is None: stt = SpeechToText(stt_provider)
                audio_file = microphone.record(output_file="audio.wav")
                recognized_text = stt.transcribe(audio_file, context=" | ".join(recent_context[-3:])).strip()
                if not recognized_text:
                    ui.warn("Não consegui entender.")
                    if avatar: avatar.idle()
                    continue
                text = recognized_text
                ui.console.print(f"[user]Você[/user] [muted]›[/muted] {text}")
            if text.lower() in {"sair", "encerrar", "tchau", "desligar"}:
                with response_lock:
                    response_id += 1
                    if response_cancel_event is not None: response_cancel_event.set()
                tts.stop()
                if speech_thread is not None: speech_thread.join(timeout=0.5)
                if avatar: avatar.happy(0.6)
                tts.speak("Até mais.")
                break
            with response_lock:
                response_id += 1
                if response_cancel_event is not None: response_cancel_event.set()
                response_cancel_event = threading.Event()
                current_response_id = response_id
                if response_thread is not None: tts.stop()
                if speech_thread is not None: speech_thread.join(timeout=0.5)
                response_thread = threading.Thread(target=process_message, args=(text, current_response_id, response_cancel_event), daemon=True)
                response_thread.start()
            response_thread.join()
    except KeyboardInterrupt:
        ui.console.print(); ui.warn("Encerrando...")
    finally:
        with response_lock:
            response_id += 1
            if response_cancel_event is not None: response_cancel_event.set()
        tts.stop()
        if speech_thread is not None: speech_thread.join(timeout=0.5)
        if response_thread is not None:
            try: response_thread.join(timeout=0.5)
            except Exception: pass
        if avatar: avatar.idle()


def run_gemini_live(screen, webcam, avatar):
    from audio.text_to_speech import TextToSpeech
    tts_provider = select_tts_provider(gemini_live=True)
    _require_audio_keys(None, tts_provider)
    external_tts = None
    if tts_provider != "gemini":
        fish_voice_id = select_fish_voice() if tts_provider == "fish" else None
        external_tts = TextToSpeech(voice="pt-BR-AntonioNeural", rate="+15%", fish_voice_id=fish_voice_id, provider=tts_provider)
        ui.status("Escuta: Gemini nativo  | Fala: biblioteca/API escolhida")
    else:
        ui.status("Escuta e fala: nativas do Gemini Live")
    if avatar: avatar.listening()
    agent = GeminiLive(screen=screen, webcam=webcam, tts=external_tts)
    try: asyncio.run(agent.run())
    finally:
        if external_tts:
            try: external_tts.stop()
            except Exception: pass
        try: agent.close()
        except Exception: pass


def create_text_agent(router, choice, groq_model=None, mistral_model=None, openrouter_model=None, nvidia_model=None, ollama_model=None, huggingface_model=None):
    if choice == "2": return router.groq(groq_model), f"Groq ({groq_model})"
    if choice == "3": return router.mistral(mistral_model), f"Mistral ({mistral_model})"
    if choice == "4": return router.openrouter(openrouter_model), f"OpenRouter ({openrouter_model})"
    if choice == "5": return router.nvidia(nvidia_model), f"NVIDIA ({nvidia_model})"
    if choice == "6": return router.ollama(ollama_model), f"Ollama ({ollama_model})"
    if choice == "7":
        return router.huggingface(huggingface_model), f"Hugging Face ({huggingface_model})"
    return router.automatic(groq_model, openrouter_model, nvidia_model, mistral_model, huggingface_model), "Modo automático"


def run_text_mode(screen, webcam, avatar, selection):
    stt_provider = select_stt_provider()
    tts_provider = select_tts_provider(gemini_live=False)
    _require_audio_keys(stt_provider, tts_provider)
    fish_voice_id = select_fish_voice() if tts_provider == "fish" else None
    executor = LocalToolExecutor(screen, webcam)
    router = ProviderRouter(executor.execute)
    agent, label = create_text_agent(router, selection["choice"], selection["groq_model"], selection["mistral_model"], selection["openrouter_model"], selection["nvidia_model"], selection["ollama_model"], selection.get("huggingface_model"))
    ui.status(f"STT: {stt_provider}  | TTS: {tts_provider}")
    run_text_provider(label, agent, stt_provider, tts_provider, fish_voice_id, avatar=avatar)


def start_avatar():
    try: from avatar.avatar import Avatar as AvatarClass
    except Exception as error:
        ui.warn(f"Avatar Live2D indisponível: {error}"); return None
    try:
        from pathlib import Path
        avatar_root = Path(__file__).resolve().parent / "avatar" / "models" / "miku_free" / "runtime"
        model_file = avatar_root / "miku.model3.json"
        texture_file = avatar_root / "miku.2048" / "texture_00.png"
        if not model_file.exists(): ui.warn("Avatar indisponível: miku.model3.json não encontrado. Continuando sem avatar."); return None
        if not texture_file.exists(): ui.warn("Avatar indisponível: texture_00.png não encontrado. Continuando sem avatar."); return None
        avatar = AvatarClass(); avatar.start(); ui.ok("Avatar Live2D iniciado."); return avatar
    except Exception as error:
        ui.warn(f"Avatar indisponível: {error}"); return None


def close_avatar(avatar):
    if not avatar: return
    try: avatar.close()
    except Exception: pass


def run():
    screen = Screen(); webcam = Webcam(); avatar = None; selection = None
    try:
        selection = menu()
        selection["show_avatar"] = select_avatar_enabled()
        if selection["show_avatar"]: avatar = start_avatar()
        if selection["choice"] == "1": run_gemini_live(screen, webcam, avatar)
        else: run_text_mode(screen, webcam, avatar, selection)
    except KeyboardInterrupt:
        ui.warn("Encerrando agente...")
        if avatar:
            try: avatar.neutral()
            except Exception: pass
    except Exception as error:
        if avatar:
            try: avatar.neutral()
            except Exception: pass
        ui.error(f"Erro: {error}")
    finally:
        close_avatar(avatar)
        try: webcam.close()
        except Exception: pass


if __name__ == "__main__":
    run()
