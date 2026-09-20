"""Camada visual compartilhada, baseada em rich.

Centraliza o console, o tema de cores e os widgets (paineis, tabelas,
spinners) usados pelo app.py e pelos modulos de audio/providers/memoria,
para manter uma identidade visual consistente no terminal.
"""

from __future__ import annotations

from contextlib import contextmanager
import re
import textwrap

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.rule import Rule


from prompt_toolkit import prompt as terminal_prompt
from prompt_toolkit.patch_stdout import patch_stdout


THEME = Theme(
    {
        "brand": "bold #B98CFF",
        "muted": "grey62",
        "ok": "bold #4ADE80",
        "warn": "bold #FACC15",
        "error": "bold #F87171",
        "info": "bold #38BDF8",
        "user": "bold #38BDF8",
        "agent": "bold #B98CFF",
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


def banner() -> None:
    """Cabecalho principal exibido ao iniciar o app: robozinho + titulo."""
    console.print()
    robot = Text("\n".join(ROBOT_ART), style="brand")
    title = Text()
    title.append("AGENTE", style="accent")
    title.append(" PESSOAL", style="brand")
    subtitle = Text("assistente de voz local", style="muted")
    body = Align.center(Group(Align.center(robot), Text(""), Align.center(title), Align.center(subtitle)))
    console.print(body)
    console.print()
    console.print(Rule(style="muted"))


def section(title: str) -> None:
    """Titulo de secao com regua, para separar etapas do fluxo."""
    console.print()
    console.print(Rule(f"[brand]{title}[/brand]", style="brand", characters="─"))
    console.print()


def module_header(name: str, icon: str = "▸") -> None:
    """Cabecalho de modulo (STT, TTS, Memoria, Ferramentas...).

    Mais forte que section(): usado para marcar a troca de um
    subsistema do agente, com espaco generoso acima e abaixo.
    """
    console.print()
    console.print()
    label = Text(f" {icon} {name.upper()} ", style="accent on #4C1D95")
    console.print(label)
    console.print(Rule(style="brand"))


def menu_table(title: str, rows: list[dict]) -> None:
    """Renderiza uma tabela numerada de opcoes.

    rows: lista de dicts com chaves 'label' e opcionalmente 'description'
    e 'tag' (ex.: "(configurado)").
    Cada opcao ganha uma linha em branco abaixo para respirar melhor.
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
            title=f"[brand]{title}[/brand]",
            border_style="brand",
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


def ok(message: str) -> None:
    console.print(f"[ok]✅ {message}[/ok]")


def warn(message: str) -> None:
    console.print(f"[warn]⚠️  {message}[/warn]")


def error(message: str) -> None:
    console.print(f"[error]❌ {message}[/error]")


def info(message: str) -> None:
    console.print(f"[info]ℹ️  {message}[/info]")


def status(message: str) -> None:
    """Uma linha de status discreta (ex.: 'STT: groq | TTS: edge')."""
    console.print(f"[muted]{message}[/muted]")


@contextmanager
def spinner(message: str):
    """Spinner simples para operacoes que bloqueiam (STT, carregar modelo)."""
    with console.status(f"[info]{message}[/info]", spinner="dots"):
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
    console.print(
        "\n[agent]Agente[/agent] [muted]›[/muted] ",
        end=""
    )


def chat_agent_prefix() -> None:
    console.print()
    console.print("[agent] Agente [/agent]", end="")
    console.print(" [muted]está pensando...[/muted]", end="")


def chat_response(text: str) -> None:
    # Tags de emoção são instruções internas do Fish TTS, não texto da UI.
    text = re.sub(
        r"\[(?:happy|excited|calm|empathetic|curious|confident|sad|angry|surprised|laughing|whispering|serious|friendly|playful|neutral)\]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    width = max(40, console.width - 8)
    wrapped_lines = []
    in_code = False
    for line in text.splitlines() or [""]:
        if line.strip().startswith("```"):
            in_code = not in_code
            wrapped_lines.append(line)
        elif in_code or not line.strip():
            wrapped_lines.append(line)
        else:
            wrapped_lines.extend(textwrap.wrap(
                line,
                width=width,
                break_long_words=False,
                break_on_hyphens=False,
                replace_whitespace=False,
            ) or [""])
    text = "\n".join(wrapped_lines)
    console.print(
        Panel(
            Markdown(text),
            border_style="brand",
            box=box.ROUNDED,
            padding=(1, 2),
            width=console.width,
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
    console.print("\n[warn]🛑 Interrompido.[/warn]")


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
            width=console.width,
        )
    )


def chat_tool_card(
    name: str,
    repeated: bool = False,
    arguments: dict | None = None,
    result: object = None,
) -> None:
    """Mostra uma operação como um cartão de vidro compacto."""
    from rich.console import Group
    from rich.syntax import Syntax

    preview, path = _glass_preview(name, arguments, result)
    result_text = str(result or "").strip()
    failed = result_text.lower().startswith((
        "erro", "error", "edição não aplicada", "ediÃ§Ã£o nÃ£o aplicada"
    ))
    status_label = "IGNORADA" if repeated else ("FALHOU" if failed else "CONCLUIDA")
    status_style = "warn" if repeated else ("error" if failed else "ok")

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
            width=console.width,
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
            width=console.width,
        )
    )


# Compatibilidade com o CMD legado do Windows: estes prefixos não dependem
# de emojis nem de caracteres que cp1252 não consegue imprimir.
# A implementação final da UI é mantida acima para evitar sobreposição
# duplicada e erros de análise de tipos do Pyright.
