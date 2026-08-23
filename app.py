import asyncio
import os

from dotenv import load_dotenv

from gemini_live.client import GeminiLive
from providers.router import ProviderRouter
from screen.screen import Screen
from tools.computer import ComputerTools
from tools.files import FileTools
from webcam.webcam import Webcam

load_dotenv()


class LocalToolExecutor:
    def __init__(self, screen, webcam):
        self.screen = screen
        self.webcam = webcam
        self.computer = ComputerTools()
        self.files = FileTools()

    def execute(self, name, arguments):
        if name == "open_application":
            return self.computer.open_application(arguments.get("application", ""))
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
        return f"Ferramenta desconhecida: {name}"


def select_model(provider_name, models, configured_model):
    print(f"\nModelos {provider_name}:")
    for index, model in enumerate(models, 1):
        marker = " (configurado)" if model == configured_model else ""
        print(f"[{index}] {model}{marker}")
    while True:
        choice = input(f"Escolha o modelo [1-{len(models)}] (Enter mantém configuração): ").strip()
        if not choice:
            return configured_model or models[0]
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice) - 1]
        print("❌ Escolha inválida.")


def run_text_provider(provider_name, agent):
    from audio.microphone import Microphone
    from audio.speech_to_text import SpeechToText
    from audio.text_to_speech import TextToSpeech

    microphone = Microphone()
    stt = SpeechToText()
    tts = TextToSpeech(voice="pt-BR-AntonioNeural", rate="+15%")
    print(f"\n✅ {provider_name} pronto. Fale normalmente.\n")
    try:
        while True:
            audio_file = microphone.record(output_file="audio.wav")
            text = stt.transcribe(audio_file).strip()
            if not text:
                continue
            print(f"\nVocê: {text}")
            if text.lower() in {"sair", "encerrar", "tchau", "desligar"}:
                tts.speak("Até mais.")
                break
            print("Agente: ", end="", flush=True)
            try:
                interrupted, _ = tts.speak_stream(agent.ask_stream(text))
                print()
                if interrupted:
                    print("🛑 Interrompido.")
            except Exception as error:
                print(f"\n❌ Erro: {error}")
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        tts.stop()


def menu():
    from providers.groq_provider import available_models as groq_models
    from providers.openrouter_provider import available_models as openrouter_models

    print("\n======================================\n           AGENTE PESSOAL\n======================================\n")
    print("[1] Gemini Live\n")
    print("[2] Groq\n    ├── seleção de modelo")
    print("[3] OpenRouter\n    ├── seleção de modelo")
    print("[4] Automático\n")
    choice = input("Escolha [1-4]: ").strip()
    while choice not in {"1", "2", "3", "4"}:
        print("❌ Escolha inválida.")
        choice = input("Escolha [1-4]: ").strip()
    if choice == "2":
        model = select_model("Groq", groq_models(), os.getenv("GROQ_MODEL"))
        return choice, model, None
    if choice == "3":
        model = select_model("OpenRouter", openrouter_models(), os.getenv("OPENROUTER_MODEL"))
        return choice, None, model
    return choice, None, None


def run():
    screen = Screen()
    webcam = Webcam()
    choice, groq_model, openrouter_model = menu()
    agent = None
    try:
        if choice == "1":
            agent = GeminiLive(screen=screen, webcam=webcam)
            asyncio.run(agent.run())
        else:
            executor = LocalToolExecutor(screen, webcam)
            router = ProviderRouter(executor.execute)
            if choice == "2":
                agent = router.groq(groq_model)
                run_text_provider(f"Groq ({groq_model})", agent)
            elif choice == "3":
                agent = router.openrouter(openrouter_model)
                run_text_provider(f"OpenRouter ({openrouter_model})", agent)
            else:
                agent = router.automatic(groq_model, openrouter_model)
                run_text_provider("Modo automático", agent)
    except KeyboardInterrupt:
        print("\nEncerrando agente...")
    except Exception as error:
        print(f"\n❌ Erro: {error}")
    finally:
        if choice == "1" and agent is not None:
            agent.close()
        webcam.close()


if __name__ == "__main__":
    run()
