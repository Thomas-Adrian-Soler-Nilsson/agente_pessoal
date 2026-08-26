"""Camada visual compartilhada, baseada em rich.

Centraliza o console, o tema de cores e os widgets (paineis, tabelas,
spinners) usados pelo app.py e pelos modulos de audio/providers/memoria,
para manter uma identidade visual consistente no terminal.
"""

from __future__ import annotations

from contextlib import contextmanager

from rich.align import Align
from rich.console import Console, Group
from rich.padding import Padding
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

console = Console(theme=THEME, highlight=False)

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
        padding=(0, 1, 1, 0),
        expand=False,
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
    console.print(f"[brand]{title}[/brand]")
    console.print()
    console.print(table)


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
    console.print(f"\n[user]Você[/user] [muted]›[/muted] {text}")


def agent_prefix() -> None:
    console.print(
        "\n[agent]Agente[/agent] [muted]›[/muted] ",
        end=""
    )


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