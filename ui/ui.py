"""Camada visual compartilhada, baseada em rich.

Centraliza o console, o tema de cores e os widgets (paineis, tabelas,
spinners) usados pelo app.py e pelos modulos de audio/providers/memoria,
para manter uma identidade visual consistente no terminal.

Visual: tema vermelho moderno. O gradiente da familia do vermelho percorre o
banner, as reguas e o indicador "pensando...", e a borda das respostas troca de
paleta (vermelho, rosa, carmesim, framboesa, brasa, tijolo) a cada mensagem.
Os estados continuam diferenciados: sucesso em rosa claro, falha em vermelho
profundo reverso, aviso em ambar.
"""

from __future__ import annotations

import colorsys
import itertools
import json
import math
import os
import re
import sys
import time
from contextlib import contextmanager

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from prompt_toolkit import prompt as terminal_prompt
from prompt_toolkit.patch_stdout import patch_stdout


# Garante UTF-8 na saida (evita caracteres quebrados no CMD).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError, OSError):
        pass


# Paleta da CLI: esquema convencional e organizado, uma cor por papel. O vermelho
# fica reservado para FALHA (e para a coruja, que e' a identidade do agente).
#   marca/ chrome = azul      (reguas, molduras, titulos)
#   sucesso       = verde
#   aviso         = ambar
#   falha         = vermelho
#   informacao    = azul claro
#   agente        = violeta calmo
#   secundario    = cinza
THEME = Theme(
    {
        "brand": "bold #38BDF8",
        "muted": "#9CA3AF",
        "ok": "bold #4ADE80",
        "warn": "bold #FBBF24",
        "error": "bold #F87171",
        "info": "bold #7DD3FC",
        "user": "bold #7DD3FC",
        "agent": "bold #C4B5FD",
        "accent": "bold #F1F5F9",
    }
)

console = Console(theme=THEME, highlight=False, soft_wrap=True)


OWL_ART = [
    "     ▄▄▄▄     ▄▄▄▄",
    "   ▄██████▄▄▄██████▄",
    "  ████▀▀▀▀▀▀▀▀▀████",
    "  ██  ▄▄▄▄  ▄▄▄▄  ██",
    "  ██  █◉◉█  █◉◉█  ██",
    "  ██  ▀▀▀█▄▄█▀▀▀  ██",
    "  ████▄▄▄▄▄▄▄▄▄████",
    "   ███████████████",
    "    ▀▀▀▀     ▀▀▀▀",
]

# Com soft_wrap=True o rich NAO corta linhas maiores que o terminal: numa janela
# minimizada (largura minima) cada quadro da animacao quebra em varias linhas
# visuais, o Live perde a conta e o logo aparece repetido na tela. Por isso a
# animacao exige tamanho minimo e para sozinha se a janela for redimensionada.
BANNER_MIN_WIDTH = 40
BANNER_MIN_HEIGHT = len(OWL_ART) + 5

# Paletas que se alternam na borda das respostas (uma por mensagem). Tons frios e
# calmos, para a CLI ficar organizada e ainda assim dar para distinguir uma
# mensagem da outra. As cores quentes ficam reservadas para os estados.
BORDER_COLORS = [
    "#38BDF8",  # azul
    "#7DD3FC",  # azul claro
    "#A78BFA",  # violeta
    "#5EEAD4",  # agua
    "#818CF8",  # indigo
    "#93C5FD",  # azul suave
]
_border_cycle = itertools.cycle(BORDER_COLORS)


def _next_border() -> str:
    return next(_border_cycle)


# ---------------------------------------------------------------------------
# Gradientes (os nomes "rainbow" ficaram por compatibilidade)
# ---------------------------------------------------------------------------

# Dois gradientes com papeis diferentes:
#   "owl"    -> vermelho, so na coruja: e' a identidade visual do agente;
#   "chrome" -> azul calmo, em reguas, molduras e titulos, para o resto da CLI
#               parecer um terminal normal.
# Em ambos o que varia ao longo do texto e' saturacao e brilho dentro de uma
# faixa estreita de matiz, em vez de atravessar o circulo cromatico.
_GRADIENTES = {
    # centro 356 graus (vermelho), +/- 16 graus: rosa-avermelhado a vermelho-alaranjado
    "owl": {"centro": 0.99, "span": 0.044, "sat": (0.78, 0.20), "val": (0.86, 0.14)},
    # centro 205 graus (azul), +/- 13 graus: azul-esverdeado a azul
    "chrome": {"centro": 0.57, "span": 0.036, "sat": (0.42, 0.28), "val": (0.72, 0.28)},
}


def _gradient_hex(position: float, scheme: str = "chrome") -> str:
    """Cor de um dos gradientes do app.

    "owl"    -> familia do vermelho: identidade visual da coruja.
    "chrome" -> azul calmo: reguas, molduras e titulos, para a CLI parecer um
                terminal normal em vez de um painel vermelho.
    """
    perfil = _GRADIENTES.get(scheme, _GRADIENTES["chrome"])
    ciclo = position % 1.0
    angulo = ciclo * math.tau
    matiz = (perfil["centro"] + perfil["span"] * math.sin(angulo)) % 1.0
    # Pisos altos evitam tom lavado, que some no fundo preto do console.
    saturacao = min(perfil["sat"][0] + perfil["sat"][1] * (0.5 + 0.5 * math.sin(angulo * 2 + 1.1)), 1.0)
    brilho = min(perfil["val"][0] + perfil["val"][1] * (0.5 + 0.5 * math.sin(angulo * 3 + 2.3)), 1.0)
    r, g, b = colorsys.hsv_to_rgb(matiz, saturacao, brilho)
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"


def _red_hex(position: float) -> str:
    """Gradiente vermelho. Usado SOMENTE na coruja."""
    return _gradient_hex(position, "owl")


def rainbow_text(
    text: str,
    shift: float = 0.0,
    step: float = 0.035,
    bold: bool = True,
    scheme: str = "chrome",
) -> Text:
    """Texto com uma cor diferente por caractere, dentro do gradiente escolhido."""
    out = Text()
    prefix = "bold " if bold else ""
    for i, ch in enumerate(text):
        if ch.isspace():
            out.append(ch)
        else:
            out.append(ch, style=f"{prefix}{_gradient_hex(shift + i * step, scheme)}")
    return out


class RainbowLine:
    """Linha do gradiente que anima sozinha dentro de um Live."""

    def __init__(self, text: str, speed: float = 0.6, step: float = 0.035, scheme: str = "chrome") -> None:
        self.text = text
        self.speed = speed
        self.step = step
        self.scheme = scheme

    def __rich_console__(self, console: Console, options):
        # Numa janela minimizada a linha nao cabe e o rich NAO corta (soft_wrap):
        # ela quebraria em varias linhas visuais e desalinharia o Live, deixando
        # o indicador repetido na tela. Melhor nao desenhar nada.
        if options.max_width < len(self.text) + 6:
            return
        yield rainbow_text(self.text, time.monotonic() * self.speed, self.step, scheme=self.scheme)


class RainbowRule:
    """Regua horizontal no gradiente da interface, com titulo opcional. speed>0 anima."""

    def __init__(self, title: str = "", speed: float = 0.0, char: str = "─", scheme: str = "chrome") -> None:
        self.title = title
        self.speed = speed
        self.char = char
        self.scheme = scheme

    def __rich_console__(self, console: Console, options):
        width = max(options.max_width, 1)
        shift = time.monotonic() * self.speed if self.speed else 0.0
        if self.title:
            label = f" {self.title} "
            side = max((width - len(label)) // 2, 0)
            line = self.char * side + label + self.char * max(width - side - len(label), 0)
        else:
            line = self.char * width
        yield rainbow_text(line, shift, 1.0 / width, scheme=self.scheme)


def _centered(text: Text, width: int) -> Text:
    """Centraliza UMA linha com espaco so a esquerda.

    O Align.center preenche a linha ate a largura toda do terminal, e linhas
    nesse limite sao justamente as que dependem do comportamento de quebra do
    console. Preenchendo so a esquerda a linha termina cedo.
    """
    pad = max((max(width, 1) - len(text.plain)) // 2, 0)
    if not pad or not text.plain:
        return text
    return Text(" " * pad) + text


def _banner_frame(shift: float, width: int) -> Group:
    # Uma entrada por linha: cada uma e' centralizada individualmente.
    # A coruja e' a unica parte com o gradiente vermelho (identidade do agente);
    # titulo e subtitulo usam o azul calmo do resto da interface.
    linhas = [
        rainbow_text(line, shift + i * 0.08, 0.05, scheme="owl")
        for i, line in enumerate(OWL_ART)
    ]
    linhas.append(Text(""))
    linhas.append(rainbow_text("AGENTE PESSOAL", shift, 0.06))
    linhas.append(Text("assistente de voz local", style="muted"))
    return Group(*[_centered(linha, width) for linha in linhas])


def _animacao_ligada() -> bool:
    """Animacao e OPT-IN: AGENTE_ANIMACAO=1 liga; AGENTE_SEM_ANIMACAO=1 forca off.

    Medido no fluxo ANSI: o rich acerta a contabilidade (quadro de 12 linhas,
    11 subidas de cursor), mas o cmd.exe do usuario nao honra as subidas como o
    rich espera e cada quadro fica na tela, empilhando o logo. Como e' so um
    enfeite de abertura, o padrao seguro e' desenhar uma vez, sem regiao Live.
    """
    if os.getenv("AGENTE_SEM_ANIMACAO", "").strip().lower() in {"1", "true", "sim", "yes", "on"}:
        return False
    return os.getenv("AGENTE_ANIMACAO", "").strip().lower() in {"1", "true", "sim", "yes", "on"}


def _banner_fits() -> bool:
    """A animacao so roda com espaco de sobra: ver BANNER_MIN_WIDTH/HEIGHT."""
    if not _animacao_ligada() or not console.is_terminal:
        return False
    return (console.width or 0) >= BANNER_MIN_WIDTH and (console.height or 0) >= BANNER_MIN_HEIGHT


def banner() -> None:
    """Cabecalho exibido ao iniciar o app: coruja + titulo.

    Estatico por padrao: o logo aparece uma unica vez. Com AGENTE_ANIMACAO=1 roda
    o gradiente vermelho animado, parando sozinho se a janela mudar de tamanho.
    """
    console.print()
    if not _banner_fits():
        console.print(_banner_frame(0.0, console.width))
        console.print()
        console.print(RainbowRule())
        return

    tamanho_inicial = (console.width, console.height)
    animou = False
    try:
        with Live(_banner_frame(0.0, console.width), console=console, refresh_per_second=30) as live:
            animou = True
            for frame in range(30):
                # Redimensionou ou minimizou no meio? O rich nao consegue mais
                # apagar os quadros anteriores e cada um vira um logo novo na
                # tela. Parar aqui preserva o ultimo quadro bom.
                if (console.width, console.height) != tamanho_inicial:
                    break
                live.update(_banner_frame(frame * 0.03, console.width))
                time.sleep(0.04)
    except (OSError, ValueError):
        if not animou:
            console.print(_banner_frame(0.0, console.width))
    console.print()
    console.print(RainbowRule())


def section(title: str) -> None:
    """Titulo de secao com regua, para separar etapas do fluxo."""
    console.print()
    console.print(RainbowRule(title))
    console.print()


def module_header(name: str, icon: str = "▸") -> None:
    """Cabecalho de modulo (STT, TTS, Memoria, Ferramentas...)."""
    console.print()
    console.print()
    console.print(rainbow_text(f" {icon} {name.upper()} "))
    console.print(RainbowRule())


def menu_table(title: str, rows: list[dict]) -> None:
    """Renderiza uma tabela numerada de opcoes.

    rows: lista de dicts com chaves 'label' e opcionalmente 'description'
    e 'tag' (ex.: "(configurado)").
    """
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2, 1, 0),
        expand=True,
    )
    table.add_column("idx", style="info", justify="right", no_wrap=True)
    table.add_column("content")
    for index, row in enumerate(rows, 1):
        label = Text(row["label"], style="bold white")
        tag = row.get("tag")
        if tag:
            label.append(f" {tag}", style="muted")
        content = Text()
        content.append_text(label)
        description = row.get("description")
        if description:
            content.append("\n")
            content.append(f"    {description}", style="muted")
        table.add_row(f"[{index}]", content)
    console.print()
    console.print(
        Panel(
            table,
            title=rainbow_text(f" {title} "),
            border_style=_next_border(),
            box=box.ROUNDED,
            padding=(1, 1),
        )
    )


def dialog(
    title: str,
    body: str,
    subtitle: str | None = None,
    style: str = "brand",
) -> None:
    """Exibe uma decisão ou estado em um painel visual consistente."""
    console.print(
        Panel(
            body,
            title=f"[accent]{title}[/accent]",
            subtitle=(
                f"[muted]{subtitle}[/muted]"
                if subtitle
                else None
            ),
            border_style=style,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


# Simbolos sem variation selector (evita erro de largura no CMD).
def ok(message: str) -> None:
    console.print(f"[ok]✔ {message}[/ok]")


def warn(message: str) -> None:
    console.print(f"[warn]⚠ {message}[/warn]")


def error(message: str) -> None:
    console.print(f"[error]✖ {message}[/error]")


def info(message: str) -> None:
    console.print(f"[info]ℹ {message}[/info]")


def status(message: str) -> None:
    """Uma linha de status discreta (ex.: 'STT: groq | TTS: edge')."""
    console.print(f"[muted]{message}[/muted]")


@contextmanager
def thinking(message: str = "pensando..."):
    """Indicador animado no gradiente vermelho. Use: with ui.thinking(): ... lento ..."""
    if not _animacao_ligada() or not console.is_terminal or (console.height or 0) < 3:
        yield
        return
    live = None
    try:
        live = Live(
            RainbowLine(f"● {message}"),
            console=console,
            refresh_per_second=20,
            transient=True,
        )
        live.start()
    except (OSError, ValueError):
        # Sem animacao o app continua; o indicador e cosmetico.
        yield
        return
    try:
        yield
    finally:
        try:
            live.stop()
        except (OSError, ValueError):
            pass


@contextmanager
def spinner(message: str):
    """Indicador para operacoes que bloqueiam (STT, carregar modelo)."""
    with thinking(message):
        yield


def user_line(text: str) -> None:
    console.print()
    console.print(
        Panel(
            Text(text, style="white"),
            title="[user] Você [/user]",
            border_style="info",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def agent_prefix() -> None:
    console.print()
    console.print(rainbow_text("Agente"), end="")
    console.print(" [muted]›[/muted] ", end="")


def chat_agent_prefix() -> None:
    console.print()
    console.print(rainbow_text(" Agente "), end="")
    console.print(" [muted]está pensando...[/muted]", end="")


_EMOTION_TAGS = re.compile(
    r"\[(?:happy|excited|calm|empathetic|curious|confident|sad|angry|surprised|"
    r"laughing|whispering|serious|friendly|playful|neutral)\]",
    flags=re.IGNORECASE,
)


def chat_response(text: str) -> None:
    # Tags de emoção são instruções internas do Fish TTS, não texto da UI.
    text = _EMOTION_TAGS.sub("", text)
    # Linha nova: chat_agent_prefix() deixa o cursor no meio da linha, e o
    # painel precisa comecar na coluna 0 para nao estourar a largura.
    console.print()
    # Sem pre-quebra com textwrap e sem width fixo: o Markdown/Panel do Rich
    # ja se ajustam a largura real do terminal.
    console.print(
        Panel(
            Markdown(text),
            title=rainbow_text(" Agente "),
            title_align="left",
            border_style=_next_border(),
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def chat_tool(
    name: str,
    repeated: bool = False,
    arguments: dict | None = None,
    result: object = None,
) -> None:
    """Compat wrapper used by the agent execution flow."""
    if repeated:
        console.print(
            f"\n[warn]↻ Ferramenta repetida ignorada:[/warn] [muted]{name}()[/muted]"
        )
        return
    if arguments is not None or result is not None:
        chat_tool_card(name, repeated=repeated, arguments=arguments, result=result)
        return
    console.print(f"\n[info]⚙ IA →[/info] [accent]{name}()[/accent]")


def chat_notice(message: str) -> None:
    console.print(f"\n[warn]⚠ {message}[/warn]")


def interrupted() -> None:
    console.print("\n[warn]■ Interrompido.[/warn]")


def prompt(message: str) -> str:
    """
    Entrada de texto compatível com saída concorrente.

    O prompt é mantido sem markup Rich para evitar que códigos ANSI
    apareçam literalmente no terminal.
    """

    with patch_stdout(raw=False):
        return terminal_prompt(
            message,
        )


# ---------------------------------------------------------------------------
# Visualização de operações de código
# ---------------------------------------------------------------------------

def _glass_compact_path(value: str) -> str:
    if not value:
        return ""
    try:
        from pathlib import Path
        path = Path(value).expanduser()
        try:
            return f"~/{path.relative_to(Path.home())}"
        except ValueError:
            pass
    except (TypeError, ValueError, OSError):
        pass
    return str(value)


def _glass_lexer(path: str) -> str:
    from pathlib import Path
    suffix = Path(path).suffix.lower() if path else ""
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".tsx": "tsx", ".jsx": "jsx", ".html": "html", ".htm": "html",
        ".css": "css", ".json": "json", ".xml": "xml", ".sql": "sql",
        ".md": "markdown", ".yml": "yaml", ".yaml": "yaml",
        ".ps1": "powershell", ".sh": "bash", ".bat": "batch",
    }.get(suffix, "text")


# Modo verboso: por padrao os cartoes de ferramenta mostram um resumo legivel
# em vez do JSON cru. "/verboso" liga o despejo completo para depuracao.
_VERBOSE = False


def set_verbose(enabled: bool) -> bool:
    global _VERBOSE
    _VERBOSE = bool(enabled)
    return _VERBOSE


def verbose() -> bool:
    return _VERBOSE


def _short_url(url: object, limit: int = 60) -> str:
    text = str(url or "")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _browser_target_label(arguments: dict, result: dict) -> str:
    """Descreve em poucas palavras o alvo ou o valor da acao no Chrome."""
    operation = str(result.get("operation") or "")
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    target = result.get("target") if isinstance(result.get("target"), dict) else {}

    if target:
        label = str(target.get("label") or "")
        coordinates = f"({target.get('x')}, {target.get('y')})" if target.get("x") is not None else ""
        described = (label + " " + coordinates).strip()
        if described:
            return described

    if operation in {"open_tab", "navigate"}:
        after = result.get("after") if isinstance(result.get("after"), dict) else {}
        return _short_url(after.get("url") or arguments.get("url") or "")
    if operation in {"fill", "select"}:
        value = " ".join(str(arguments.get("value", "")).split())
        if not value:
            return ""
        return '"' + (value[:40] + "…" if len(value) > 40 else value) + '"'
    if operation == "press":
        return str(arguments.get("key") or "")
    if operation == "click_at":
        label = str(arguments.get("expected_label") or "")
        coordinates = f"({arguments.get('x')}, {arguments.get('y')})" if arguments.get("x") is not None else ""
        return (label + " " + coordinates).strip()
    if operation == "click":
        return str(data.get("target") or data.get("label") or "element_ref")
    if operation == "inspect":
        elements = data.get("elements")
        return f"{len(elements)} elementos" if isinstance(elements, list) else ""
    if operation == "list_tabs":
        tabs = data.get("tabs")
        return f"{len(tabs)} abas" if isinstance(tabs, list) else ""
    if operation == "screenshot":
        width, height = result.get("width"), result.get("height")
        return f"{width}x{height}" if width and height else ""
    if operation == "download":
        return str(data.get("file_path") or "")[:80]
    if operation == "wait":
        return " ".join(str(arguments.get("text") or arguments.get("url_contains") or "").split())[:60]
    if operation == "close_tab":
        return "aba fechada"
    return ""


def _url_origin(url: object) -> str:
    match = re.match(r"^([a-z]+://[^/]+)", str(url or ""), re.IGNORECASE)
    return match.group(1).lower() if match else ""


def _url_path(url: object) -> str:
    match = re.match(r"^[a-z]+://[^/]+(/.*)?$", str(url or ""), re.IGNORECASE)
    return (match.group(1) or "/") if match else str(url or "")


def _browser_state_change(result: dict) -> str:
    """Mostra o efeito observavel: mudanca de URL, de titulo ou de conteudo."""
    before = result.get("before") if isinstance(result.get("before"), dict) else {}
    after = result.get("after") if isinstance(result.get("after"), dict) else {}
    if not before or not after:
        return ""
    before_url, after_url = str(before.get("url") or ""), str(after.get("url") or "")
    if before_url != after_url:
        if _url_origin(before_url) and _url_origin(before_url) == _url_origin(after_url):
            # Mesmo site: o caminho e a informacao util, nao o dominio repetido.
            return f"{_short_url(_url_path(before_url), 22)} → {_short_url(_url_path(after_url), 40)}"
        return f"{_short_url(before_url, 26)} → {_short_url(after_url, 34)}"
    if str(before.get("title") or "") != str(after.get("title") or ""):
        return 'titulo: "' + str(after.get("title"))[:50] + '"'
    if str(before.get("text") or "") != str(after.get("text") or ""):
        return "conteudo da pagina mudou"
    return ""


def browser_action_line(name: str, arguments: dict | None, result: dict) -> str:
    """Uma unica linha legivel com o que a acao fez no Chrome."""
    operation = str(result.get("operation") or name.replace("browser_", "", 1) or name)
    pieces = [operation]
    label = _browser_target_label(arguments or {}, result)
    if label:
        pieces.append(label)
    change = _browser_state_change(result)
    if change:
        pieces.append(change)
    error = str(result.get("error_code") or "")
    if error:
        pieces.append(error)
    return " · ".join(piece for piece in pieces if piece)


def browser_compact_lines(result: dict) -> list[str]:
    """Lista sem UUIDs para inspecao e abas: o que um humano precisa ler."""
    operation = str(result.get("operation") or "")
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    lines: list[str] = []
    if operation == "inspect":
        title = str(data.get("title") or "")
        url = _short_url(data.get("url") or "", 72)
        if title or url:
            lines.append((title + "  " + url).strip())
        elements = data.get("elements")
        if isinstance(elements, list):
            for element in elements[:8]:
                if not isinstance(element, dict):
                    continue
                role = str(element.get("role") or "?")
                name = " ".join(str(element.get("name") or "").split()) or "(sem nome)"
                extra = str(element.get("type") or element.get("placeholder") or "")
                if extra:
                    name = f"{name}  [{extra}]"
                lines.append(f"  {role:<9} {name[:70]}")
            if len(elements) > 8:
                lines.append(f"  … mais {len(elements) - 8} elementos (o agente recebe todos)")
    elif operation == "list_tabs":
        tabs = data.get("tabs")
        if isinstance(tabs, list):
            for tab in tabs[:8]:
                if not isinstance(tab, dict):
                    continue
                lines.append(f"  {tab.get('id')}  {str(tab.get('title') or '')[:44]}")
                lines.append(f"            {_short_url(tab.get('url') or '', 70)}")
            if len(tabs) > 8:
                lines.append(f"  … mais {len(tabs) - 8} abas")
    return lines


def chat_tool_pending(name: str, arguments: dict | None = None) -> None:
    """Aviso imediato, antes de a ferramenta rodar.

    Uma captura com analise visual leva segundos; sem esta linha o terminal fica
    parado durante a acao e parece travado.
    """
    arguments = arguments or {}
    detail = ""
    if name in {"browser_fill", "browser_select"}:
        value = " ".join(str(arguments.get("value", "")).split())
        detail = '"' + (value[:32] + "…" if len(value) > 32 else value) + '"'
    elif name == "browser_press":
        detail = str(arguments.get("key") or "")
    elif name in {"browser_navigate", "browser_open_tab"}:
        detail = _short_url(arguments.get("url") or "", 48)
    elif name == "run_terminal":
        detail = str(arguments.get("command") or "")[:48]
    elif name in {"read_file", "write_file", "edit_file", "read_file_range"}:
        detail = str(arguments.get("path") or "")[-48:]
    console.print(
        f"[info]⚙[/info] [accent]{name}[/accent]"
        + (f" [muted]{detail}[/muted]" if detail else "")
    )


def _browser_preview_value(value: object, text_limit: int = 400) -> dict | None:
    if not isinstance(value, dict):
        return None
    compact = {}
    for key in ("id", "status", "error_code", "url", "title", "summary", "observation", "retry_hint"):
        item = value.get(key)
        if item not in (None, ""):
            compact[key] = str(item)[:text_limit] if isinstance(item, str) else item
    return compact


def _browser_tool_preview(result: dict) -> str:
    """Render the useful browser result fields before any verbose analysis data."""
    compact = {}
    for key in ("type", "image_kind", "status", "operation", "error_code", "previous_error_code", "screenshot_id", "width", "height", "mime_type", "description", "observation", "retry_hint"):
        value = result.get(key)
        if value not in (None, ""):
            compact[key] = value

    for key in ("target", "tab", "before", "after", "click", "verification"):
        value = result.get(key)
        if isinstance(value, dict):
            if key == "target":
                compact[key] = {
                    field: str(value.get(field, ""))[:120] if field == "label" else value.get(field)
                    for field in ("label", "x", "y", "confidence")
                    if field in value
                }
            else:
                compact[key] = _browser_preview_value(value, 240)

    analysis = result.get("analysis")
    if isinstance(analysis, dict):
        brief_analysis = _browser_preview_value(analysis, 300) or {}
        nested = analysis.get("analysis")
        if isinstance(nested, dict):
            details = _browser_preview_value(nested, 240) or {}
            targets = nested.get("targets")
            if isinstance(targets, list):
                details["targets"] = [
                    {key: str(target.get(key, ""))[:80] if key == "label" else target.get(key)
                     for key in ("label", "x", "y", "confidence", "actionable") if key in target}
                    for target in targets[:4]
                    if isinstance(target, dict)
                ]
            brief_analysis["analysis"] = details
        compact["analysis"] = brief_analysis

    data = result.get("data")
    if isinstance(data, dict) and result.get("operation") == "list_tabs":
        tabs = data.get("tabs")
        if isinstance(tabs, list):
            compact["data"] = {
                "tabs": [_browser_preview_value(tab, 240) for tab in tabs[:12] if isinstance(tab, dict)]
            }
    elif isinstance(data, dict) and result.get("operation") == "inspect":
        brief_data = _browser_preview_value(data, 600) or {}
        elements = data.get("elements")
        if isinstance(elements, list):
            brief_data["elements"] = [
                {key: str(element.get(key, ""))[:80] if key in {"name", "href", "placeholder"} else element.get(key)
                 for key in ("element_ref", "role", "name", "tag", "type", "href", "disabled") if key in element}
                for element in elements[:8]
                if isinstance(element, dict)
            ]
        compact["data"] = brief_data
    elif isinstance(data, dict):
        brief_data = _browser_preview_value(data, 240)
        if brief_data:
            compact["data"] = brief_data

    return json.dumps(compact, ensure_ascii=False, indent=2)


def show_browser_screenshot(image: dict) -> None:
    """Render a temporary screenshot in the terminal without writing it to disk."""
    if not isinstance(image, dict) or not image.get("data"):
        return
    try:
        import base64
        from io import BytesIO
        from PIL import Image
        from rich.color import Color
        from rich.style import Style

        raw = base64.b64decode(image["data"], validate=True)
        with Image.open(BytesIO(raw)) as source:
            screenshot = source.convert("RGB")
        columns = max(40, min(96, console.width - 8))
        pixel_height = max(2, round(columns * screenshot.height / screenshot.width))
        if pixel_height % 2:
            pixel_height += 1
        screenshot = screenshot.resize((columns, pixel_height), Image.Resampling.LANCZOS)

        def rgb(pixel):
            if isinstance(pixel, tuple):
                return tuple(int(channel) for channel in pixel[:3])
            value = int(pixel)
            return value, value, value

        rendered = Text(no_wrap=True, overflow="crop")
        for y in range(0, pixel_height, 2):
            for x in range(columns):
                top = rgb(screenshot.getpixel((x, y)))
                bottom = rgb(screenshot.getpixel((x, y + 1)))
                rendered.append(
                    "▀",
                    style=Style(color=Color.from_rgb(*top), bgcolor=Color.from_rgb(*bottom)),
                )
            if y + 2 < pixel_height:
                rendered.append("\n")
        dimensions = f"{image.get('width', screenshot.width)}x{image.get('height', screenshot.height)}"
        screenshot_id = str(image.get("screenshot_id") or "")[:12]
        title = f"Screenshot Chrome {dimensions}"
        if screenshot_id:
            title += f" · {screenshot_id}"
        console.print(
            Panel(
                rendered,
                title=f"[accent]{title}[/accent]",
                border_style="info",
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )
    except (ImportError, OSError, ValueError, TypeError):
        console.print("[muted]Screenshot do Chrome capturado; prévia indisponível neste terminal.[/muted]")


def _glass_preview(name: str, arguments: dict | None, result: object) -> tuple[str, str]:
    """Seleciona uma única prévia útil, evitando despejar o mesmo conteúdo duas vezes."""
    arguments = arguments or {}
    path = str(arguments.get("path", ""))
    preview = ""
    if name == "write_file":
        preview = str(arguments.get("content", ""))
    elif name in {"write_file_chunk", "edit_file"}:
        preview = str(arguments.get("content", "") or arguments.get("replace", ""))
        if name == "edit_file" and arguments.get("find"):
            preview = f"- {arguments['find']}\n+ {preview}"
    elif name in {"read_file", "read_file_range", "inspect_project"}:
        preview = str(result or "")
        marker = "Conteúdo:\n\n"
        if marker in preview:
            preview = preview.split(marker, 1)[1]
        elif "Linhas " in preview and "\n\n" in preview:
            preview = preview.split("\n\n", 1)[1]
    elif name.startswith("browser_") and isinstance(result, dict):
        preview = _browser_tool_preview(result)
    else:
        preview = str(result or "")
    preview = preview.strip()
    if len(preview) > 1800:
        preview = preview[:1800].rstrip() + "\n... previa reduzida"
    return preview, path


def chat_operation_header(objective: str) -> None:
    short = " ".join(str(objective or "").split())
    if len(short) > 100:
        short = short[:97] + "..."
    console.print(
        Panel(
            Text.assemble(
                ("[+]  WORKSPACE / CODIGO\n", "brand"),
                (short or "Operacao iniciada", "white"),
            ),
            title="[accent]visualizacao da operacao[/accent]",
            subtitle="[muted]acoes, arquivos e previas aparecem aqui[/muted]",
            border_style="brand",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )


def chat_tool_card(
    name: str,
    repeated: bool = False,
    arguments: dict | None = None,
    result: object = None,
) -> None:
    """Mostra uma operação como um cartão de vidro compacto."""
    preview, path = _glass_preview(name, arguments, result)
    result_status = result.get("status") if isinstance(result, dict) else None
    result_text = (json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, dict) else str(result or "")).strip()
    failed = result_status in {"failure", "blocked"} or result_text.lower().startswith((
        "erro", "error", "edição não aplicada", "ediÃ§Ã£o nÃ£o aplicada"
    ))
    status_label = "IGNORADA" if repeated else ("FALHOU" if failed else {"partial": "PARCIAL", "uncertain": "INCERTO", "confirmation_required": "AGUARDA CONFIRMAÇÃO", "setup_needed": "CONFIGURAÇÃO NECESSÁRIA"}.get(str(result_status), "CONCLUÍDA"))
    status_style = "warn" if repeated or result_status in {"partial", "uncertain", "confirmation_required", "setup_needed"} else ("error" if failed else "ok")

    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(style="muted", width=12, no_wrap=True)
    table.add_column(style="white")
    table.add_row("acao", f"{name}()")
    action_kind = {
        "write_file": "CRIAR / ATUALIZAR",
        "write_file_chunk": "ACRESCENTAR TRECHO",
        "edit_file": "ALTERAR TRECHO",
        "read_file": "LER CODIGO",
        "read_file_range": "LER LINHAS",
        "inspect_project": "INSPECIONAR",
        "run_terminal": "EXECUTAR COMANDO",
        "run_code_file": "EXECUTAR CODIGO",
        "validate_file": "VALIDAR",
    }.get(name)
    if action_kind:
        table.add_row("tipo", action_kind)
    if path:
        table.add_row("arquivo", _glass_compact_path(path))
    if arguments and name == "run_terminal":
        command = str(arguments.get("command", ""))
        table.add_row("comando", command[:120] + ("..." if len(command) > 120 else ""))
    table.add_row("status", f"[{status_style}]{status_label}[/{status_style}]")

    # Leitura em tempo real: uma linha dizendo o que a acao fez no Chrome, sem
    # UUIDs de element_ref e sem o JSON cru (que so aparece em /verboso).
    browser_result = result if (name.startswith("browser_") and isinstance(result, dict)) else None
    if browser_result is not None:
        summary = browser_action_line(name, arguments, browser_result)
        if summary:
            table.add_row("resumo", summary[:150])

    body = [table]
    if repeated:
        body.append(Text("mesmos argumentos ja executados nesta solicitacao", style="muted"))
    elif browser_result is not None and not verbose():
        lines = browser_compact_lines(browser_result)
        observation = str(browser_result.get("observation") or "").strip()
        if observation and failed:
            lines.append(observation[:200])
        for line in lines:
            body.append(Text(line, style="white"))
    elif result_text:
        first_line = next((line.strip() for line in result_text.splitlines() if line.strip()), "")
        if first_line and first_line.lower() not in preview.lower():
            body.append(Text(first_line[:220], style="muted"))
    if preview and not repeated and (browser_result is None or verbose()):
        body.append(Syntax(preview, _glass_lexer(path), theme="monokai", line_numbers=True, word_wrap=True))

    console.print(
        Panel(
            Group(*body),
            title=f"[info][AI][/info]  [accent]{name}[/accent]  [{status_style}]{status_label}[/{status_style}]",
            border_style="error" if failed else ("warn" if repeated else "brand"),
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def chat_operation_summary(summary: str) -> None:
    console.print(
        Panel(
            Text(summary, style="white"),
            title="[brand][+] resumo da operacao[/brand]",
            border_style="brand",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )