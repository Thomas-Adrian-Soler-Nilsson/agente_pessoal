"""O banner nao pode se multiplicar na tela ao iniciar pelo .bat.

Historico do bug: o logo (robo e depois coruja) aparecia empilhado dezenas de
vezes. Medicoes feitas no fluxo ANSI do rich:

* a contabilidade do Live esta CORRETA: quadros de 12 linhas com 11 subidas de
  cursor ("position_cursor" emite (CURSOR_UP,1) * (height-1));
* mesmo assim o cmd.exe do usuario nao reposiciona o cursor como o rich espera,
  entao cada quadro fica na tela.

Conclusao: animacao de banner depende de cooperacao exata do terminal e nao vale
o risco. O padrao passou a ser ESTATICO (logo desenhado uma vez); a animacao
ficou opt-in por AGENTE_ANIMACAO=1.
"""
import os
import re
import time
import unittest
from io import StringIO
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

from rich.console import Console, ConsoleDimensions

from ui import ui

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _render(renderable, largura: int, altura: int = 40, terminal: bool = False, soft_wrap: bool = False) -> str:
    buffer = StringIO()
    console = Console(
        file=buffer, width=largura, height=altura,
        force_terminal=terminal, soft_wrap=soft_wrap, theme=ui.THEME,
    )
    console.print(renderable)
    return buffer.getvalue()


def _limpo(saida: str) -> str:
    return ANSI.sub("", saida)


def _sem_env():
    return patch.dict(os.environ, {}, clear=False)


class StaticByDefaultTests(unittest.TestCase):
    def test_logo_appears_once_in_a_big_terminal(self):
        buffer = StringIO()
        console = Console(file=buffer, width=140, height=40, force_terminal=True, theme=ui.THEME)
        with _sem_env(), patch.object(ui, "console", console):
            os.environ.pop("AGENTE_ANIMACAO", None)
            os.environ.pop("AGENTE_SEM_ANIMACAO", None)
            ui.banner()

        saida = buffer.getvalue()
        # A coruja tem 4 olhos (◉): uma vez = 4 ocorrencias.
        self.assertEqual(saida.count("◉"), 4, "o logo tem que aparecer uma unica vez")
        self.assertNotIn("\x1b[1A", saida, "sem animacao nao pode haver subida de cursor")

    def test_animation_is_off_without_the_env_var(self):
        console = Console(file=StringIO(), width=140, height=40, force_terminal=True, theme=ui.THEME)
        with _sem_env(), patch.object(ui, "console", console):
            os.environ.pop("AGENTE_ANIMACAO", None)
            self.assertFalse(ui._banner_fits(), "animacao e opt-in")

    def test_frame_lines_end_early_instead_of_filling_the_width(self):
        for largura in (40, 80, 140, 200):
            with self.subTest(largura=largura):
                saida = _limpo(_render(ui._banner_frame(0.0, largura), largura))
                linhas = [linha for linha in saida.splitlines() if linha.strip()]
                self.assertTrue(linhas)
                mais_longa = max(len(linha) for linha in linhas)
                self.assertLess(
                    mais_longa, largura - 4,
                    "linha encostando na borda depende do comportamento de quebra do console",
                )


class OptInAnimationTests(unittest.TestCase):
    def test_env_var_enables_the_animation(self):
        console = Console(file=StringIO(), width=140, height=40, force_terminal=True, theme=ui.THEME)
        quadros = []
        quadro_original = ui._banner_frame

        def contar(shift, width):
            quadros.append(shift)
            return quadro_original(shift, width)

        tempo_falso = SimpleNamespace(monotonic=time.monotonic, sleep=lambda _s: None)
        with patch.dict(os.environ, {"AGENTE_ANIMACAO": "1"}), \
                patch.object(ui, "console", console), \
                patch.object(ui, "_banner_frame", side_effect=contar), \
                patch.object(ui, "time", tempo_falso):
            ui.banner()

        self.assertGreater(len(quadros), 5, "com AGENTE_ANIMACAO=1 a animacao deve rodar")

    def test_sem_animacao_wins_over_animacao(self):
        console = Console(file=StringIO(), width=140, height=40, force_terminal=True, theme=ui.THEME)
        with patch.dict(os.environ, {"AGENTE_ANIMACAO": "1", "AGENTE_SEM_ANIMACAO": "1"}), \
                patch.object(ui, "console", console):
            self.assertFalse(ui._banner_fits(), "a trava de emergencia tem precedencia")

    def test_resizing_the_window_stops_the_animation(self):
        console = Console(file=StringIO(), width=100, force_terminal=True, theme=ui.THEME)
        console._height = 40
        quadros = []
        quadro_original = ui._banner_frame

        def contar(shift, width):
            quadros.append(shift)
            return quadro_original(shift, width)

        def encolher(_segundos):
            console._height = 5  # usuario minimizou a janela

        tempo_falso = SimpleNamespace(monotonic=time.monotonic, sleep=encolher)
        with patch.dict(os.environ, {"AGENTE_ANIMACAO": "1"}), \
                patch.object(ui, "console", console), \
                patch.object(ui, "_banner_frame", side_effect=contar), \
                patch.object(ui, "time", tempo_falso):
            ui.banner()

        self.assertGreaterEqual(len(quadros), 1)
        self.assertLess(
            len(quadros), 5,
            f"a animacao deveria parar no primeiro sinal de resize, mas desenhou {len(quadros)} quadros",
        )

    def test_small_size_blocks_the_animation_even_when_enabled(self):
        console = Console(file=StringIO(), force_terminal=True, theme=ui.THEME)
        for largura, altura in ((20, 40), (100, 5), (1, 1)):
            with self.subTest(largura=largura, altura=altura):
                with patch.dict(os.environ, {"AGENTE_ANIMACAO": "1"}), \
                        patch.object(ui, "console", console), \
                        patch.object(Console, "size", new_callable=PropertyMock,
                                     return_value=ConsoleDimensions(largura, altura)):
                    self.assertFalse(ui._banner_fits())


class NarrowTerminalMechanismTests(unittest.TestCase):
    """Documenta por que a animacao exige tamanho minimo."""

    def test_narrow_terminal_emits_lines_wider_than_the_console(self):
        largura = 12
        saida = _render(ui._banner_frame(0.0, largura), largura, terminal=True, soft_wrap=True)
        linhas = [linha for linha in _limpo(saida).splitlines() if linha.strip()]

        self.assertTrue(
            any(len(linha) > largura for linha in linhas),
            "sem linha mais larga que o terminal o mecanismo nao se reproduz; "
            "se o rich passar a cortar, esta trava pode ser revista",
        )


class ThinkingResilienceTests(unittest.TestCase):
    def test_indicator_is_off_by_default(self):
        console = Console(file=StringIO(), width=140, height=40, force_terminal=True, theme=ui.THEME)
        with _sem_env(), patch.object(ui, "console", console):
            os.environ.pop("AGENTE_ANIMACAO", None)
            with patch.object(ui, "Live") as live_falso:
                with ui.thinking("teste"):
                    pass
        live_falso.assert_not_called()

    def test_indicator_disappears_instead_of_wrapping(self):
        for largura in (4, 8, 12, 16):
            with self.subTest(largura=largura):
                saida = _limpo(_render(ui.RainbowLine("● pensando..."), largura, soft_wrap=True))
                self.assertEqual([linha for linha in saida.splitlines() if linha.strip()], [])

    def test_indicator_appears_when_there_is_room(self):
        saida = _limpo(_render(ui.RainbowLine("● pensando..."), 80, soft_wrap=True))
        self.assertIn("pensando", saida)

    def test_thinking_survives_a_live_that_cannot_start(self):
        console = Console(file=StringIO(), width=80, height=40, force_terminal=True, theme=ui.THEME)

        class LiveQuebrado:
            def __init__(self, *args, **kwargs):
                raise ValueError("terminal sem suporte")

        with patch.dict(os.environ, {"AGENTE_ANIMACAO": "1"}), \
                patch.object(ui, "console", console), patch.object(ui, "Live", LiveQuebrado):
            with ui.thinking("teste"):
                pass


if __name__ == "__main__":
    unittest.main()
