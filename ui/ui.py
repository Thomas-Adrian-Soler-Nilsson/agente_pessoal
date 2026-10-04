"""Camada visual compartilhada, baseada em rich.

Centraliza o console, o tema de cores e os widgets (paineis, tabelas,
spinners) usados pelo app.py e pelos modulos de audio/providers/memoria,
para manter uma identidade visual consistente no terminal.

Visual: arco-iris animado (banner, reguas, "pensando...") e borda das
respostas trocando de cor a cada mensagem.
"""

from __future__ import annotations

import colorsys
import itertools
import json
import re
import sys
import time
from contextlib import contextmanager

from rich import box
from rich.align import Align
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


THEME = Theme(
    {
        "brand": "bold #22D3EE",
        "muted": "grey62",
        "ok": "bold #4ADE80",
        "warn": "bold #FACC15",
        "error": "bold #F87171",
        "info": "bold #38BDF8",
        "user": "bold #38BDF8",
        "agent": "bold #F472B6",
        "accent": "bold white",
    }
)

console = Console(theme=THEME, highlight=False, soft_wrap=True)

ROBOT_ART = [
    "  ╭──────╮",
    "  │ ◉  ◉ │",
    "  │  ──  │",
    "  ╰┬────┬╯",
    "   │    │",
]

# Cores que se alternam na borda das respostas (uma por mensagem).
BORDER_COLORS = [
    "#F472B6",  # rosa
    "#FB923C",  # laranja
    "#FACC15",  # amarelo
    "#4ADE80",  # verde
    "#22D3EE",  # ciano
    "#60A5FA",  # azul
    "#F87171",  # vermelho
]
_border_cycle = itertools.cycle(BORDER_COLORS)


def _next_border() -> str:
    return next(_border_cycle)


# ---------------------------------------------------------------------------
# Arco-iris
# ---------------------------------------------------------------------------

def _hue_hex(hue: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(hue % 1.0, 0.65, 1.0)
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"


def rainbow_text(text: str, shift: float = 0.0, step: float = 0.035, bold: bool = True) -> Text:
    """Texto com uma cor diferente por caractere (gradiente arco-iris)."""
    out = Text()
    prefix = "bold " if bold else ""
    for i, ch in enumerate(text):
        if ch.isspace():
            out.append(ch)
        else:
            out.append(ch, style=f"{prefix}{_hue_hex(shift + i * step)}")
    return out


class RainbowLine:
    """Texto arco-iris que anima sozinho quando usado dentro de um Live."""

    def __init__(self, text: str, speed: float = 0.6, step: float = 0.035) -> None:
        self.text = text
        self.speed = speed
        self.step = step

    def __rich_console__(self, console: Console, options):
        yield rainbow_text(self.text, time.monotonic() * self.speed, self.step)


class RainbowRule:
    """Regua horizontal em arco-iris, com titulo opcional. speed>0 anima."""

    def __init__(self, title: str = "", speed: float = 0.0, char: str = "─") -> None:
        self.title = title
        self.speed = speed
        self.char = char

    def __rich_console__(self, console: Console, options):
        width = max(options.max_width, 1)
        shift = time.monotonic() * self.speed if self.speed else 0.0
        if self.title:
            label = f" {self.title} "
            side = max((width - len(label)) // 2, 0)
            line = self.char * side + label + self.char * max(width - side - len(label), 0)
        else:
            line = self.char * width
        yield rainbow_text(line, shift, 1.0 / width)


def _banner_frame(shift: float) -> Align:
    robot = Text()
    for i, line in enumerate(ROBOT_ART):
        robot.append_text(rainbow_text(line, shift + i * 0.08, 0.05))
        if i < len(ROBOT_ART) - 1:
            robot.append("\n")
    title = rainbow_text("AGENTE PESSOAL", shift, 0.06)
    subtitle = Text("assistente de voz local", style="muted")
    return Align.center(
        Group(Align.center(robot), Text(""), Align.center(title), Align.center(subtitle))
    )


def banner() -> None:
    """Cabecalho principal exibido ao iniciar o app: robozinho animado + titulo."""
    console.print()
    if console.is_terminal:
        with Live(_banner_frame(0.0), console=console, refresh_per_second=30) as live:
            for frame in range(30):
                live.update(_banner_frame(frame * 0.03))
                time.sleep(0.04)
    else:
        console.print(_banner_frame(0.0))
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
    """Indicador animado em arco-iris. Use: with ui.thinking(): ... chamada lenta ..."""
    if not console.is_terminal:
        yield
        return
    with Live(
        RainbowLine(f"● {message}"),
        console=console,
        refresh_per_second=20,
        transient=True,
    ):
        yield


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

    body = [table]
    if repeated:
        body.append(Text("mesmos argumentos ja executados nesta solicitacao", style="muted"))
    elif result_text:
        first_line = next((line.strip() for line in result_text.splitlines() if line.strip()), "")
        if first_line and first_line.lower() not in preview.lower():
            body.append(Text(first_line[:220], style="muted"))
    if preview and not repeated:
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