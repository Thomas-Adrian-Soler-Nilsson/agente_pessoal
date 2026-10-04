"""Confirmação de ações arriscadas: desligada por padrão.

O usuário pediu para não precisar mais confirmar envios/compras/exclusões. A
confirmação continua existindo, mas virou opt-in por AGENTE_CONFIRMAR_ACOES=1, e
o guard de submit do Enter acompanha essa escolha (senão o Enter seria barrado
mesmo com a confirmação desligada).
"""
import os
import unittest
from unittest.mock import patch

from tools.browser import BrowserTools, confirmar_acoes_arriscadas


class FakeBridge:
    def __init__(self):
        self.chamadas = []

    def execute(self, operation, arguments, timeout=30):
        self.chamadas.append((operation, arguments))
        return {"status": "success", "operation": operation, "data": {}}


class ConfirmationSwitchTests(unittest.TestCase):
    def test_off_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENTE_CONFIRMAR_ACOES", None)
            self.assertFalse(
                confirmar_acoes_arriscadas(),
                "pedir [s/N] nao pode ser o padrao",
            )

    def test_turned_on_by_the_env_var(self):
        for valor in ("1", "true", "sim", "yes", "ON"):
            with self.subTest(valor=valor), patch.dict(os.environ, {"AGENTE_CONFIRMAR_ACOES": valor}):
                self.assertTrue(confirmar_acoes_arriscadas())

    def test_other_values_keep_it_off(self):
        for valor in ("0", "nao", "false", ""):
            with self.subTest(valor=valor), patch.dict(os.environ, {"AGENTE_CONFIRMAR_ACOES": valor}):
                self.assertFalse(confirmar_acoes_arriscadas())


class PressPayloadTests(unittest.TestCase):
    def _browser(self):
        ponte = FakeBridge()
        return ponte, BrowserTools(bridge=ponte)

    def test_press_releases_the_submit_guard_by_default(self):
        ponte, browser = self._browser()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENTE_CONFIRMAR_ACOES", None)
            browser.press(7, "Enter")

        operacao, argumentos = ponte.chamadas[-1]
        self.assertEqual(operacao, "press")
        self.assertEqual(argumentos["key"], "Enter")
        self.assertEqual(argumentos["tab_id"], 7)
        self.assertTrue(
            argumentos["allow_submit"],
            "sem confirmacao configurada o Enter nao pode ser barrado pelo guard de submit",
        )

    def test_press_keeps_the_guard_when_confirmation_is_back_on(self):
        ponte, browser = self._browser()
        with patch.dict(os.environ, {"AGENTE_CONFIRMAR_ACOES": "1"}):
            browser.press(7, "Enter")

        self.assertFalse(ponte.chamadas[-1][1]["allow_submit"])


if __name__ == "__main__":
    unittest.main()
