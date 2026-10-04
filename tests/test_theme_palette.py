"""O tema da CLI e' convencional e organizado; o vermelho fica SO na coruja.

Cada papel tem a sua cor (azul para a interface, verde/ambar/vermelho para os
estados, violeta para o agente), e o gradiente vermelho e' exclusivo da coruja,
que e' a identidade visual do agente.
"""
import colorsys
import re
import unittest
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from ui import ui

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
RGB = re.compile(r"(\d+);(\d+);(\d+)")


def _hsv(hexadecimal: str) -> tuple[float, float, float]:
    r, g, b = (int(hexadecimal[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)


def _hue(hexadecimal: str) -> float:
    return _hsv(hexadecimal)[0] * 360


def _e_vermelho(hexadecimal: str) -> bool:
    matiz = _hue(hexadecimal)
    return matiz >= 335 or matiz <= 20


def _e_frio(hexadecimal: str) -> bool:
    return 165 <= _hue(hexadecimal) <= 300


def _cores_do_estilo(estilo: str) -> list[str]:
    return [f"#{valor}" for valor in re.findall(r"#([0-9A-Fa-f]{6})", estilo)]


def _primeira_cor(token: str) -> str:
    return _cores_do_estilo(str(ui.THEME.styles[token]))[0].lstrip("#")


def _render(renderable, largura: int = 100, terminal: bool = True) -> str:
    buffer = StringIO()
    console = Console(
        file=buffer, width=largura, force_terminal=terminal,
        color_system="truecolor", theme=ui.THEME, no_color=False,
    )
    console.print(renderable)
    return buffer.getvalue()


def _cores_da_saida(saida: str) -> set[str]:
    return {
        f"#{int(r):02X}{int(g):02X}{int(b):02X}"
        for r, g, b in re.findall(r"38;2;(\d+);(\d+);(\d+)", saida)
    }


def _fundos_da_saida(saida: str) -> set[str]:
    return {
        f"#{int(r):02X}{int(g):02X}{int(b):02X}"
        for r, g, b in re.findall(r"48;2;(\d+);(\d+);(\d+)", saida)
    }


class SemanticPaletteTests(unittest.TestCase):
    def test_every_role_has_an_explicit_colour(self):
        for token in ("brand", "muted", "ok", "warn", "error", "info", "user", "agent", "accent"):
            with self.subTest(token=token):
                self.assertIn(token, ui.THEME.styles)
                self.assertTrue(_cores_do_estilo(str(ui.THEME.styles[token])), token)

    def test_states_are_all_different_from_each_other(self):
        cores = {}
        for token in ("brand", "ok", "warn", "error", "info", "agent"):
            cores[token] = _primeira_cor(token).upper()
        self.assertEqual(
            len(set(cores.values())), len(cores),
            f"dois estados ficaram com a mesma cor: {cores}",
        )

    def test_states_use_the_conventional_hues(self):
        esperado = {
            "ok": (100, 165),      # verde
            "warn": (35, 65),      # ambar
            "error": (335, 20),    # vermelho (faixa que vira o circulo)
            "brand": (185, 235),   # azul
            "agent": (250, 295),   # violeta
        }
        for token, (minimo, maximo) in esperado.items():
            with self.subTest(token=token):
                matiz = _hue(_primeira_cor(token))
                dentro = (minimo <= matiz <= maximo) if minimo < maximo else (matiz >= minimo or matiz <= maximo)
                self.assertTrue(
                    dentro,
                    f"{token} = #{_primeira_cor(token)} tem matiz {matiz:.0f}, fora de {minimo}-{maximo}",
                )

    def test_only_failure_is_red(self):
        for token in ("ok", "warn", "brand", "info", "agent", "user"):
            with self.subTest(token=token):
                self.assertFalse(
                    _e_vermelho(_primeira_cor(token)),
                    f"{token} ficou vermelho; o vermelho e' do estado de falha e da coruja",
                )


class GradientTests(unittest.TestCase):
    def test_owl_gradient_is_red(self):
        for passo in range(100):
            cor = ui._red_hex(passo / 100.0).lstrip("#")
            with self.subTest(passo=passo):
                self.assertTrue(_e_vermelho(cor), f"{cor} saiu do vermelho ({_hue(cor):.0f})")

    def test_chrome_gradient_is_calm_blue(self):
        for passo in range(100):
            cor = ui._gradient_hex(passo / 100.0, "chrome").lstrip("#")
            with self.subTest(passo=passo):
                self.assertTrue(_e_frio(cor), f"{cor} nao e' azul calmo ({_hue(cor):.0f})")
                self.assertFalse(_e_vermelho(cor), f"{cor} deixaria a interface vermelha")

    def test_the_two_gradients_do_not_overlap(self):
        vermelho = {ui._gradient_hex(passo / 40.0, "owl") for passo in range(40)}
        azul = {ui._gradient_hex(passo / 40.0, "chrome") for passo in range(40)}
        self.assertFalse(vermelho & azul, "os gradientes da coruja e da interface nao podem se misturar")

    def test_rainbow_text_defaults_to_the_interface_gradient(self):
        saida = _render(ui.rainbow_text("AGENTE"))
        for cor in _cores_da_saida(saida):
            with self.subTest(cor=cor):
                self.assertTrue(_e_frio(cor.lstrip("#")), f"{cor} nao e' do gradiente da interface")

    def test_banner_keeps_red_only_on_the_owl(self):
        saida = _render(ui._banner_frame(0.0, 100))
        cores = _cores_da_saida(saida)
        vermelhas = [cor for cor in cores if _e_vermelho(cor.lstrip("#"))]
        azuis = [cor for cor in cores if _e_frio(cor.lstrip("#"))]
        self.assertTrue(vermelhas, "a coruja precisa manter o vermelho da identidade")
        self.assertTrue(azuis, "titulo e subtitulo precisam do azul da interface")


class BorderPaletteTests(unittest.TestCase):
    def test_borders_are_calm_and_distinct(self):
        distintas = {cor.upper() for cor in ui.BORDER_COLORS}
        self.assertGreaterEqual(len(distintas), 5, "as paletas precisam ser diferentes entre si")
        for cor in distintas:
            with self.subTest(cor=cor):
                self.assertTrue(_e_frio(cor.lstrip("#")), f"{cor} e' quente demais para a borda")
                self.assertFalse(_e_vermelho(cor.lstrip("#")), f"{cor} deixaria a borda vermelha")


class CodeHighlightTests(unittest.TestCase):
    """O realce de codigo e' multicolorido por natureza; o que nao pode e' ter
    fundo claro (o texto do tema ficaria ilegivel)."""

    CODIGO = (
        "import os\n"
        "\n"
        "def somar(a, b):\n"
        "    # comentario\n"
        "    return a + b\n"
        "\n"
        "texto = 'valor em string'\n"
        "print(somar(1, 2), texto)\n"
    )

    def _saida_do_cartao(self) -> str:
        buffer = StringIO()
        console = Console(
            file=buffer, width=70, force_terminal=True,
            color_system="truecolor", theme=ui.THEME, no_color=False,
        )
        with patch.object(ui, "console", console):
            ui.chat_tool_card(
                "write_file",
                arguments={"path": "exemplo.py", "content": self.CODIGO},
                result="Arquivo criado.",
            )
        return buffer.getvalue()

    def test_code_block_has_a_dark_background(self):
        fundos = _fundos_da_saida(self._saida_do_cartao())
        self.assertTrue(fundos, "o bloco de codigo precisa declarar fundo")
        for fundo in fundos:
            with self.subTest(fundo=fundo):
                brilho = max(int(fundo[i:i + 2], 16) for i in (1, 3, 5)) / 255
                self.assertLess(brilho, 0.35, f"fundo {fundo} claro demais para o tema escuro")

    def test_code_highlighting_still_emits_colours(self):
        self.assertTrue(_cores_da_saida(self._saida_do_cartao()), "o realce de codigo sumiu")


if __name__ == "__main__":
    unittest.main()
