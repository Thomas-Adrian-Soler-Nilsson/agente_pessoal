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
from tools.browser import BrowserTools, confirmar_acoes_arriscadas
from tools.developer import DeveloperTools
from tools.files import FileTools
from tools.image_generation import ImageGenerator
from tools.huggingface_multimodal import hf_tool_executor
from tools.remote_3d import generate_rodin, generate_trify
from tools.nvidia_trellis import generate_nvidia_trellis
from tools.three_d_router import generate_3d_auto
from tools.threews_3d import generate_threews
from tools.triposr import generate_triposr
from webcam.webcam import Webcam
from tools.web_research import discover_sources, open_public_page, deep_search as research_deep_search, code_search as research_code_search

Avatar = None
load_dotenv()

# Enquanto uma pergunta [s/N] estiver na thread da resposta, a thread principal
# precisa parar de consumir teclas (msvcrt), senão as duas disputam o teclado e a
# resposta do usuário se perde.
INPUT_PAUSE = threading.Event()


class LocalToolExecutor:
    def __init__(self, screen, webcam, browser_tools=None):
        self.screen = screen
        self.webcam = webcam
        self.computer = ComputerTools()
        self.browser = browser_tools if browser_tools is not None else BrowserTools()
        self._owns_browser = browser_tools is None
        self.files = FileTools()
        self.developer = DeveloperTools(self.files)
        self.images = ImageGenerator()

    def _confirm_browser_outcome(self, outcome, retry):
        if not isinstance(outcome, dict) or outcome.get("status") != "confirmation_required":
            return outcome
        data = outcome.get("data") or {}
        label = data.get("label", "ação externa")
        if not confirmar_acoes_arriscadas():
            # Sem confirmacao configurada: segue direto com o token que a
            # extensao devolveu, sem interromper o usuario.
            aprovado = retry(data.get("confirmation_token", ""))
            if isinstance(aprovado, dict) and aprovado.get("status") == "confirmation_required":
                # Defensivo: se o token nao for aceito, falha com codigo claro em
                # vez de devolver "aguarda confirmacao" e deixar o modelo repetir.
                return {
                    **aprovado,
                    "status": "failure",
                    "error_code": "confirmation_not_accepted",
                    "observation": "A extensão não aceitou a autorização automática; nada foi executado.",
                }
            return aprovado
        INPUT_PAUSE.set()
        try:
            answer = ui.prompt(f"O Chrome vai executar '{label}'. Autorizar? [s/N]: ").strip().lower()
        finally:
            INPUT_PAUSE.clear()
        if answer not in {"s", "sim", "y", "yes"}:
            return {**outcome, "status": "failure", "error_code": "user_denied", "observation": "Ação cancelada pelo usuário; nada foi enviado."}
        return retry(data.get("confirmation_token", ""))

    def close(self):
        if self._owns_browser:
            try:
                self.browser.close()
            except Exception:
                pass

    def execute(self, name, arguments):
        arguments = arguments or {}
        if name == "open_application":
            return self.computer.open_application(arguments.get("application", ""))
        if name == "open_directory":
            return self.computer.open_directory(arguments.get("path", "~"))
        if name == "open_url":
            return self.computer.open_url(arguments.get("url", ""))
        if name == "web_search":
            return discover_sources(arguments.get("query", ""), arguments.get("max_results", 5))
        if name == "web_open":
            return open_public_page(arguments.get("url", ""), arguments.get("max_chars", 12000), arguments.get("focus_query", ""))
        if name == "deep_search":
            return research_deep_search(arguments.get("query", ""), arguments.get("max_sites", 7), arguments.get("max_chars_per_site", 3000))
        if name == "code_search":
            return research_code_search(arguments.get("query", ""), arguments.get("max_sites", 5), arguments.get("max_chars_per_site", 3000))
        if name == "browser_list_tabs":
            return self.browser.list_tabs()
        if name == "browser_inspect":
            return self.browser.inspect(arguments.get("tab_id"), arguments.get("max_chars", 12000))
        if name == "browser_navigate":
            return self.browser.navigate(arguments.get("url", ""), arguments.get("tab_id"))
        if name == "browser_open_tab":
            return self.browser.open_tab(arguments.get("url", ""))
        if name == "browser_click":
            outcome = self.browser.click(arguments.get("tab_id"), arguments.get("element_ref", ""))
            return self._confirm_browser_outcome(outcome, lambda token: self.browser.click(arguments.get("tab_id"), arguments.get("element_ref", ""), token))
        if name == "browser_visual_click":
            return {"status": "failure", "error_code": "handled_by_agent",
                    "observation": "browser_visual_click é tratado pelo agente, não pelo executor."}
        if name == "browser_click_at":
            tab_id = arguments.get("tab_id")
            screenshot_id = arguments.get("screenshot_id", "")
            x, y = arguments.get("x"), arguments.get("y")
            expected_label = str(arguments.get("expected_label", ""))
            outcome = self.browser.click_at(tab_id, screenshot_id, x, y, expected_label=expected_label)
            return self._confirm_browser_outcome(outcome, lambda token: self.browser.click_at(tab_id, screenshot_id, x, y, token, expected_label))
        if name == "browser_fill":
            return self.browser.fill(arguments.get("tab_id"), arguments.get("element_ref", ""), arguments.get("value", ""))
        if name == "browser_select":
            return self.browser.select(arguments.get("tab_id"), arguments.get("element_ref", ""), arguments.get("value", ""))
        if name == "browser_press":
            return self.browser.press(arguments.get("tab_id"), arguments.get("key", "Enter"))
        if name == "browser_wait":
            return self.browser.wait(arguments.get("tab_id"), arguments.get("text", ""), arguments.get("url_contains", ""), arguments.get("timeout", 10))
        if name == "browser_back":
            return self.browser.back(arguments.get("tab_id"))
        if name == "browser_screenshot":
            outcome = self.browser.screenshot(arguments.get("tab_id"))
            if outcome.get("status") == "success" and isinstance(outcome.get("data"), dict):
                shot = outcome["data"]
                return {
                    "type": "image",
                    "image_kind": "browser_screenshot",
                    "screenshot_id": shot.get("screenshot_id"),
                    "width": shot.get("width"),
                    "height": shot.get("height"),
                    "mime_type": shot.get("mime_type", "image/jpeg"),
                    "data": shot.get("data", ""),
                    "description": (
                        f"{outcome.get('observation', 'Screenshot do Chrome')} "
                        f"screenshot_id={shot.get('screenshot_id')}; "
                        f"dimensões={shot.get('width')}x{shot.get('height')} px; "
                        "clique visual usa coordenadas da imagem desde o canto superior esquerdo."
                    ),
                }
            return outcome
        if name == "browser_download":
            outcome = self.browser.download(arguments.get("tab_id"), arguments.get("element_ref", ""), arguments.get("path", ""))
            return self._confirm_browser_outcome(outcome, lambda token: self.browser.download(arguments.get("tab_id"), arguments.get("element_ref", ""), arguments.get("path", ""), token))
        if name == "browser_search_site":
            outcome = self.browser.search_site(arguments.get("tab_id"), arguments.get("query", ""), arguments.get("max_pages", 5))
            if outcome.get("error_code") != "site_search_not_available":
                return outcome
            tabs = self.browser.list_tabs().get("data", {}).get("tabs", [])
            selected = next((tab for tab in tabs if tab.get("id") == int(arguments.get("tab_id"))), None)
            if not selected:
                return outcome
            from urllib.parse import urlsplit
            domain = urlsplit(selected.get("url", "")).hostname or ""
            result = discover_sources(f"site:{domain} {arguments.get('query', '')}", arguments.get("max_pages", 5))
            result["strategy"] = "site_scoped_discovery"
            result["scope_domain"] = domain
            result["coverage"] = "Resultados indexados pelo mecanismo de busca; não é varredura completa do site."
            return result
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
        if name == "write_files":
            return self.files.write_files(arguments.get("files", []))
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
        if name == "run_terminal":
            return self.developer.run_terminal(
                arguments.get("command", ""),
                arguments.get("cwd"),
                arguments.get("timeout", 120),
                arguments.get("input_text"),
            )
        if name == "open_terminal":
            return self.developer.open_terminal(
                arguments.get("command", ""),
                arguments.get("cwd"),
            )
        if name == "detect_runtimes":
            return self.developer.detect_runtimes()
        if name == "run_code_file":
            return self.developer.run_code_file(
                arguments.get("path", ""),
                arguments.get("arguments", ""),
                arguments.get("timeout", 120),
                arguments.get("input_text"),
            )
        if name == "install_dependencies":
            return self.developer.install_dependencies(
                arguments.get("path", "workspace"),
                arguments.get("manager", "auto"),
                arguments.get("packages", ""),
                arguments.get("dev", False),
                arguments.get("timeout", 900),
            )
        if name == "download_file":
            url = arguments.get("url", "")
            path = arguments.get("path", "")
            # Download e uma acao externa: pede autorizacao pontual, sem
            # transformar edicoes locais e testes em confirmacoes repetitivas.
            try:
                INPUT_PAUSE.set()
                try:
                    answer = input(
                        f"\nAutorizar download para '{path}'? [s/N]: "
                    ).strip().lower()
                finally:
                    INPUT_PAUSE.clear()
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer not in {"s", "sim", "y", "yes"}:
                return "Download cancelado: autorização não concedida pelo usuário."
            return self.developer.download_file(
                url,
                path,
                arguments.get("overwrite", False),
                arguments.get("timeout", 120),
            )
        if name == "get_file_info":
            return self.files.get_file_info(arguments.get("path", ""))
        if name == "capture_screen":
            return {"type": "image", "data": self.screen.capture(), "description": "Captura atual da tela."}
        if name == "capture_webcam":
            return {"type": "image", "data": self.webcam.capture(), "description": "Captura atual da webcam."}
        if name == "generate_image":
            return self.images.generate(arguments.get("prompt", ""))
        if name == "generate_3d_local":
            return generate_triposr(
                arguments.get("image_path", ""),
                arguments.get("timeout"),
            )
        if name == "generate_3d_rodin":
            return generate_rodin(
                arguments.get("prompt", ""),
                arguments.get("image_path"),
            )
        if name == "generate_3d_trify":
            return generate_trify(
                arguments.get("prompt", ""),
                arguments.get("image_path"),
            )
        if name == "generate_3d_free":
            return generate_threews(
                arguments.get("prompt", ""),
                arguments.get("timeout"),
            )
        if name == "generate_3d_nvidia":
            return generate_nvidia_trellis(
                arguments.get("prompt", ""),
                arguments.get("image_path"),
                arguments.get("timeout"),
            )
        if name == "generate_3d_auto":
            return generate_3d_auto(
                arguments.get("prompt", ""),
                arguments.get("image_path"),
                arguments.get("timeout"),
            )
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


def _chat_prompt(default=""):
    return terminal_prompt("Você › ", default=default)


def _read_console_key():
    if os.name != "nt":
        return None
    try:
        import msvcrt
        return msvcrt.getwch() if msvcrt.kbhit() else None
    except (ImportError, OSError):
        return None


def _wait_for_response_or_escape(response_thread, cancel_event, stop_speech, read_key=None):
    if read_key is None and os.name != "nt":
        response_thread.join()
        return "", False

    read_key = read_key or _read_console_key
    pending = []
    submitted = []
    skip_extended_key = False

    while response_thread.is_alive():
        if INPUT_PAUSE.is_set():
            response_thread.join(timeout=0.05)
            continue
        key = read_key()
        while key is not None:
            if skip_extended_key:
                skip_extended_key = False
            elif key in {"\x00", "\xe0"}:
                skip_extended_key = True
            elif key == "\x1b":
                cancel_event.set()
                stop_speech()
                queued = " ".join(submitted + (["".join(pending)] if pending else []))
                return queued, True
            elif key == "\x03":
                raise KeyboardInterrupt
            elif key == "\b":
                if pending:
                    pending.pop()
            elif key in {"\r", "\n"}:
                if pending:
                    submitted.append("".join(pending))
                    pending.clear()
            elif len(key) == 1 and key.isprintable():
                pending.append(key)
            key = read_key()

        response_thread.join(timeout=0.025)

    queued = " ".join(submitted + (["".join(pending)] if pending else []))
    return queued, False


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


def select_vision_agent():
    from providers.vision_agent import VisionAgent, available_candidates

    candidates = available_candidates()
    if not candidates:
        ui.warn(
            "Nenhum modelo visual configurado. Screenshots continuarão disponíveis, "
            "mas para análise visual configure um provedor em .env."
        )
        return None

    ui.dialog(
        "Privacidade da análise visual",
        "Screenshots do Chrome serão enviados aos modelos escolhidos. Se um modelo "
        "falhar, a cadeia automática pode encaminhar a mesma captura aos próximos "
        "provedores. Para páginas sensíveis, escolha somente Ollama local ou desative a análise.",
        subtitle="O agente visual só identifica alvos; o agente principal continua controlando os cliques.",
    )

    mode = _prompt_choice("Análise visual de páginas", [
        {
            "id": "automatic",
            "label": "Fallback automático",
            "description": "Tenta os modelos disponíveis na ordem de VISION_MODEL_ORDER.",
        },
        {
            "id": "ordered",
            "label": "Definir ordem desta sessão",
            "description": "Organize os modelos; os seguintes são tentados se um falhar.",
        },
        {
            "id": "fixed",
            "label": "Usar um modelo fixo",
            "description": "Não tenta outro provedor se o escolhido falhar.",
        },
        {
            "id": "disabled",
            "label": "Desativar análise visual",
            "description": "O agente usa a inspeção textual do navegador.",
        },
    ])

    if mode == "disabled":
        return None
    if mode == "fixed":
        selected = _prompt_choice(
            "Modelo visual fixo",
            [{"id": item["id"], "label": item["label"], "description": item["id"]} for item in candidates],
        )
        candidates = [item for item in candidates if item["id"] == selected]
    elif mode == "ordered":
        ui.menu_table(
            "Modelos de visão disponíveis",
            [{"label": f"{index}. {item['label']}", "description": item["id"]} for index, item in enumerate(candidates, 1)],
        )
        while True:
            raw = ui.prompt(
                "Ordem por número (ex.: 3,1,2; Enter mantém a ordem automática): "
            ).strip()
            if not raw:
                break
            try:
                indexes = [int(part.strip()) for part in raw.split(",")]
            except ValueError:
                ui.error("Use números separados por vírgula.")
                continue
            if (
                not indexes
                or len(set(indexes)) != len(indexes)
                or any(index < 1 or index > len(candidates) for index in indexes)
            ):
                ui.error("A ordem deve conter números válidos, sem repetição.")
                continue
            chosen = [candidates[index - 1] for index in indexes]
            chosen_ids = {item["id"] for item in chosen}
            candidates = chosen + [item for item in candidates if item["id"] not in chosen_ids]
            break

    ui.status("Hierarquia visual: " + " → ".join(item["label"] for item in candidates))
    return VisionAgent(candidates)


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
    from providers.gemini_provider import available_models as gemini_models
    from providers.tokenharbor_provider import available_models as tokenharbor_models
    from providers.mistral_provider import available_models as mistral_models
    from providers.nvidia_provider import available_models as nvidia_models
    from providers.openrouter_provider import available_models as openrouter_models
    from providers.ollama_provider import available_models as ollama_models

    ui.banner()
    rows = [
        {"label": "Gemini", "description": "API de texto, modelos multimodais, Live, voz e agentes"},
        {"label": "Groq", "description": "modelos rápidos com seleção de modelo"},
        {"label": "Mistral", "description": "modelos Mistral com seleção de modelo"},
        {"label": "Token Harbor", "description": "modelos gratuitos atuais via API OpenAI-compatible"},
        {"label": "OpenRouter", "description": "acesso a diversos modelos"},
        {"label": "NVIDIA", "description": "modelos NVIDIA NIM"},
        {"label": "Ollama", "description": "modelos locais ou remotos"},
        {"label": "Hugging Face", "description": "chat, visão e modelos generativos open-weight"},
        {"label": "Automático", "description": "Groq → Mistral → OpenRouter → NVIDIA → Hugging Face"},
    ]
    choice = _prompt_choice("Modo", [{"id": str(i + 1), **row} for i, row in enumerate(rows)])

    base = {"choice": choice, "gemini_model": None, "groq_model": None, "tokenharbor_model": None, "mistral_model": None, "openrouter_model": None, "nvidia_model": None, "ollama_model": None, "huggingface_model": None}
    if choice == "1":
        mode = _prompt_choice("Gemini", [
            {"id": "api", "label": "Gemini API", "description": "chat, código e ferramentas"},
            {"id": "live", "label": "Gemini Live", "description": "voz, tela e webcam em tempo real"},
        ])
        if mode == "live":
            base["choice"] = "1-live"
            return base
        base["gemini_model"] = select_model("Gemini API", gemini_models(), os.getenv("GEMINI_MODEL")); return base
    if choice == "2":
        base["groq_model"] = select_model("Groq", groq_models(), os.getenv("GROQ_MODEL")); return base
    if choice == "3":
        base["mistral_model"] = select_model("Mistral", mistral_models(), os.getenv("MISTRAL_MODEL")); return base
    if choice == "4":
        base["tokenharbor_model"] = select_model("Token Harbor", tokenharbor_models(), os.getenv("TOKENHARBOR_MODEL")); return base
    if choice == "5":
        base["openrouter_model"] = select_model("OpenRouter", openrouter_models(), os.getenv("OPENROUTER_MODEL")); return base
    if choice == "6":
        base["nvidia_model"] = select_model("NVIDIA", nvidia_models(), os.getenv("NVIDIA_MODEL")); return base
    if choice == "7":
        base["ollama_model"] = select_model("Ollama", ollama_models(), os.getenv("OLLAMA_MODEL")); return base
    if choice == "8":
        base["huggingface_model"] = select_model("Hugging Face", hf_models("chat"), os.getenv("HF_MODEL")); return base
    return base


# --------------------------------------------------------------- modo autonomo
LOOP_MAX_ROUNDS = 50
LOOP_DEFAULT_ROUNDS = 5
GOAL_DEFAULT_ROUNDS = 10
LOOP_OFF_WORDS = {"off", "parar", "stop", "0", "desligar", "limpar"}
LOOP_DONE_MARKERS = (
    "objetivo concluído",
    "objetivo concluido",
    "tarefa concluída",
    "tarefa concluida",
    "nada mais a fazer",
)


def _normalize_slash_command(text):
    """Separa o comando slash do parametro. Devolve ("", "") se nao for comando."""
    stripped = str(text or "").strip()
    if not stripped.startswith("/"):
        return "", ""
    command, _, parameter = stripped.partition(" ")
    return command.lower(), parameter.strip()


def _loop_rounds(parameter, default):
    """Le o numero de rodadas. Devolve None quando o valor e invalido."""
    value = str(parameter or "").strip().lower()
    if not value:
        return default
    if value in LOOP_OFF_WORDS:
        return 0
    try:
        number = int(value)
    except ValueError:
        return None
    return max(1, min(number, LOOP_MAX_ROUNDS))


def _autonomous_command(text):
    """Interpreta /loop e /goal.

    Devolve None quando nao e um desses comandos; caso contrario devolve
    {"goal": str|None, "rounds": int|None, "message": str}, onde None significa
    "nao mexer no que ja estava configurado" e "" significa "limpar".
    """
    command, parameter = _normalize_slash_command(text)
    if command not in {"/loop", "/meta", "/goal"}:
        return None

    if command in {"/loop", "/meta"}:
        rounds = _loop_rounds(parameter, LOOP_DEFAULT_ROUNDS)
        if rounds is None:
            return {"goal": None, "rounds": None,
                    "message": f"Use /loop [1-{LOOP_MAX_ROUNDS}] ou /loop off."}
        if rounds == 0:
            return {"goal": "", "rounds": 0, "message": "Modo autonomo desligado."}
        # goal=None: /loop nao pode apagar um objetivo em andamento.
        return {"goal": None, "rounds": rounds,
                "message": f"Modo autonomo ligado por {rounds} rodada(s). Esc interrompe."}

    if parameter.lower() in LOOP_OFF_WORDS:
        return {"goal": "", "rounds": 0, "message": "Objetivo removido; modo autonomo desligado."}
    if not parameter:
        return {"goal": None, "rounds": None,
                "message": "Use /goal <objetivo> para o agente trabalhar sozinho, ou /goal off para encerrar."}
    return {"goal": parameter, "rounds": GOAL_DEFAULT_ROUNDS,
            "message": f'Objetivo definido: "{parameter[:120]}". Vou trabalhar nele sozinho por ate '
                       f"{GOAL_DEFAULT_ROUNDS} rodadas; Esc interrompe."}


def _loop_continuation(goal, round_number, total_rounds):
    """Instrucao enviada automaticamente entre as rodadas do modo autonomo."""
    common = (
        f" (rodada automatica {round_number} de {total_rounds}; use as ferramentas e "
        "nao pare para pedir confirmacao a cada passo)"
    )
    if goal:
        return (
            "Continue trabalhando sozinho no objetivo abaixo, aproveitando o que ja foi feito "
            "e sem repetir acoes ja concluidas." + common + "\n\nObjetivo: " + goal +
            "\n\nQuando o objetivo estiver realmente concluido, comece a resposta com "
            '"OBJETIVO CONCLUÍDO" e resuma em uma linha o que foi feito.'
        )
    return (
        "Continue a tarefa anterior a partir do estado atual, sem repetir o que ja foi feito."
        + common +
        '\n\nSe nao houver mais nada util a fazer, comece a resposta com "TAREFA CONCLUÍDA".'
    )


def _loop_finished(answer):
    """O agente declarou que terminou?"""
    text = str(answer or "").lower()
    return any(marker in text for marker in LOOP_DONE_MARKERS)


def _command_help():
    return (
        "/voz — falar pelo microfone\n"
        f"/loop [n] — o agente continua sozinho por n rodadas (padrao {LOOP_DEFAULT_ROUNDS}, max {LOOP_MAX_ROUNDS})\n"
        "/loop off — encerra o modo autonomo\n"
        f"/goal <objetivo> — define o objetivo e ja comeca a trabalhar nele sozinho ({GOAL_DEFAULT_ROUNDS} rodadas)\n"
        "/goal off — remove o objetivo e encerra o modo autonomo\n"
        "/verboso — alterna entre o resumo legivel e o JSON completo das acoes\n"
        "Esc — interrompe o raciocinio e o modo autonomo"
    )


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
    ui.ok("Pronto. Digite no CMD. Use /voz para falar, /loop ou /goal para ele seguir sozinho, /ajuda para ver tudo.")
    recent_context = []
    response_thread = None
    speech_thread = None
    response_cancel_event = None
    pending_prompt = ""
    response_lock = threading.Lock()
    agent_lock = threading.Lock()
    response_id = 0
    # Estado do modo autonomo (/loop e /goal): loop_round conta as rodadas
    # automaticas ja disparadas e loop_total o limite permitido.
    loop_goal = ""
    loop_armed = False
    loop_round = 0
    loop_total = 0
    auto_prompt = ""
    last_answer = {"text": ""}

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
            # Guardado para o modo autonomo saber se o agente declarou conclusao.
            last_answer["text"] = spoken
            # O texto exibido deve preservar Markdown e quebras de linha.
            # _speech_text() é específico do TTS: ele remove URLs, tags e
            # formatação para a fala e também achata as linhas. Usá-lo aqui
            # fazia respostas longas parecerem cortadas no painel do CMD.
            if spoken: ui.chat_response(spoken)
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
            if auto_prompt and not pending_prompt:
                # Rodada automatica do modo autonomo: nao passa pelo prompt.
                text = auto_prompt
                auto_prompt = ""
                ui.console.print(f"[user]Você[/user] [muted]›[/muted] {text}")
            else:
                text = _chat_prompt(default=pending_prompt).strip()
                pending_prompt = ""
                # Texto digitado pelo usuario durante a resposta manda: a rodada
                # automatica pendente e descartada para nao atropelar quem digitou.
                auto_prompt = ""
            if not text: continue
            comando_slash = _normalize_slash_command(text)[0]
            if comando_slash in {"/ajuda", "/help", "/comandos", "/?"}:
                ui.info(_command_help())
                continue
            if comando_slash == "/verboso":
                ligado = ui.set_verbose(not ui.verbose())
                ui.info("Modo verboso LIGADO: mostrando o JSON completo das acoes."
                        if ligado else
                        "Modo verboso DESLIGADO: mostrando o resumo legivel das acoes.")
                continue
            autonomo = _autonomous_command(text)
            if autonomo is not None:
                if autonomo["goal"] is not None:
                    loop_goal = autonomo["goal"]
                if autonomo["rounds"] is not None:
                    loop_total = autonomo["rounds"]
                    loop_round = 0
                    loop_armed = bool(autonomo["rounds"])
                ui.info(autonomo["message"])
                if loop_goal:
                    # "/goal <objetivo>" ja comeca a trabalhar: a meta e o pedido.
                    text = loop_goal
                    ui.console.print(f"[user]Você[/user] [muted]›[/muted] {text}")
                else:
                    continue
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
                current_thread = response_thread
                ui.info("Pressione Esc para interromper o raciocínio atual.")
                current_thread.start()
            pending_prompt, interrupted = _wait_for_response_or_escape(
                current_thread,
                response_cancel_event,
                tts.stop,
            )
            if interrupted:
                ui.warn("Raciocínio interrompido.")
                if loop_armed:
                    ui.warn("Modo autônomo encerrado.")
                    loop_armed = False
                    loop_goal = ""
            elif loop_armed:
                if _loop_finished(last_answer["text"]):
                    ui.ok("O agente declarou a tarefa concluída; modo autônomo encerrado.")
                    loop_armed = False
                    loop_goal = ""
                elif loop_round < loop_total:
                    loop_round += 1
                    auto_prompt = _loop_continuation(loop_goal, loop_round, loop_total)
                    ui.info(f"↻ Rodada automática {loop_round}/{loop_total} (Esc interrompe)")
                else:
                    ui.warn(f"Modo autônomo encerrado: limite de {loop_total} rodadas atingido.")
                    loop_armed = False
                    loop_goal = ""
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


def run_gemini_live(screen, webcam, avatar, browser_tools=None):
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
    vision_agent = select_vision_agent()
    agent = None
    try:
        agent = GeminiLive(screen=screen, webcam=webcam, tts=external_tts, vision_agent=vision_agent, browser_tools=browser_tools)
        asyncio.run(agent.run())
    finally:
        if agent:
            try: agent.close()
            except Exception: pass
        if external_tts:
            try: external_tts.stop()
            except Exception: pass
        if vision_agent:
            try: vision_agent.close()
            except Exception: pass


def create_text_agent(router, choice, gemini_model=None, groq_model=None, mistral_model=None, openrouter_model=None, nvidia_model=None, ollama_model=None, huggingface_model=None, tokenharbor_model=None):
    if choice == "1": return router.gemini(gemini_model), f"Gemini API ({gemini_model})"
    if choice == "2": return router.groq(groq_model), f"Groq ({groq_model})"
    if choice == "3": return router.mistral(mistral_model), f"Mistral ({mistral_model})"
    if choice == "4": return router.tokenharbor(tokenharbor_model), f"Token Harbor ({tokenharbor_model})"
    if choice == "5": return router.openrouter(openrouter_model), f"OpenRouter ({openrouter_model})"
    if choice == "6": return router.nvidia(nvidia_model), f"NVIDIA ({nvidia_model})"
    if choice == "7":
        agent = router.ollama(ollama_model)
        actual_model = getattr(agent, "display_model", None) or ollama_model
        return agent, f"Ollama ({actual_model})"
    if choice == "8":
        return router.huggingface(huggingface_model), f"Hugging Face ({huggingface_model})"
    return router.automatic(groq_model, openrouter_model, nvidia_model, mistral_model, huggingface_model), "Modo automático"


def run_text_mode(screen, webcam, avatar, selection, browser_tools=None):
    stt_provider = select_stt_provider()
    tts_provider = select_tts_provider(gemini_live=False)
    _require_audio_keys(stt_provider, tts_provider)
    fish_voice_id = select_fish_voice() if tts_provider == "fish" else None
    vision_agent = select_vision_agent()
    executor = None
    try:
        executor = LocalToolExecutor(screen, webcam, browser_tools=browser_tools)
        router = ProviderRouter(executor.execute, vision_agent=vision_agent)
        agent, label = create_text_agent(router, selection["choice"], selection.get("gemini_model"), selection["groq_model"], selection["mistral_model"], selection["openrouter_model"], selection["nvidia_model"], selection["ollama_model"], selection.get("huggingface_model"), selection.get("tokenharbor_model"))
        ui.status(f"STT: {stt_provider}  | TTS: {tts_provider}")
        run_text_provider(label, agent, stt_provider, tts_provider, fish_voice_id, avatar=avatar)
    finally:
        try:
            if executor is not None:
                executor.close()
        finally:
            if vision_agent is not None:
                vision_agent.close()


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
    browser_tools = None
    webcam = None
    avatar = None
    selection = None
    try:
        browser_tools = BrowserTools()
        screen = Screen()
        webcam = Webcam()
        selection = menu()
        selection["show_avatar"] = select_avatar_enabled()
        if selection["show_avatar"]: avatar = start_avatar()
        if selection["choice"] == "1-live": run_gemini_live(screen, webcam, avatar, browser_tools=browser_tools)
        else: run_text_mode(screen, webcam, avatar, selection, browser_tools=browser_tools)
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
        if webcam is not None:
            try: webcam.close()
            except Exception: pass
        if browser_tools is not None:
            try: browser_tools.close()
            except Exception: pass


if __name__ == "__main__":
    run()
