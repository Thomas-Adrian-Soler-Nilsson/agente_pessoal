import os
import threading
import time
import unittest
from unittest.mock import Mock, patch

from app import INPUT_PAUSE, LocalToolExecutor, _wait_for_response_or_escape, run


class ResponseInterruptTests(unittest.TestCase):
    def test_run_starts_browser_bridge_before_menu_and_closes_it(self):
        calls = []
        browser_tools = Mock()

        def create_browser_tools():
            calls.append("browser")
            return browser_tools

        def show_menu():
            calls.append("menu")
            raise RuntimeError("stop startup test")

        with (
            patch("app.BrowserTools", side_effect=create_browser_tools),
            patch("app.Screen"),
            patch("app.Webcam"),
            patch("app.menu", side_effect=show_menu),
            patch("app.ui.error"),
        ):
            run()

        self.assertEqual(calls, ["browser", "menu"])
        browser_tools.close.assert_called_once_with()

    def test_escape_cancels_response_and_stops_speech(self):
        cancel_event = threading.Event()
        response = threading.Thread(target=cancel_event.wait)
        response.start()
        stop_speech = Mock()
        keys = iter(["\x1b"])

        queued, interrupted = _wait_for_response_or_escape(
            response,
            cancel_event,
            stop_speech,
            lambda: next(keys, None),
        )
        response.join(timeout=1)

        self.assertTrue(interrupted)
        self.assertTrue(cancel_event.is_set())
        stop_speech.assert_called_once_with()
        self.assertEqual(queued, "")
        self.assertFalse(response.is_alive())

    def test_escape_preserves_text_typed_during_response(self):
        cancel_event = threading.Event()
        response = threading.Thread(target=cancel_event.wait)
        response.start()
        keys = iter(["a", "b", "c", "\b", "d", "\x1b"])

        queued, interrupted = _wait_for_response_or_escape(
            response,
            cancel_event,
            Mock(),
            lambda: next(keys, None),
        )
        response.join(timeout=1)

        self.assertTrue(interrupted)
        self.assertEqual(queued, "abd")

    def test_typed_message_is_queued_when_response_finishes(self):
        cancel_event = threading.Event()
        response_done = threading.Event()
        response = threading.Thread(target=response_done.wait)
        response.start()
        keys = iter(list("próxima") + ["\r"])

        def read_key():
            try:
                return next(keys)
            except StopIteration:
                response_done.set()
                return None

        queued, interrupted = _wait_for_response_or_escape(
            response,
            cancel_event,
            Mock(),
            read_key,
        )
        response.join(timeout=1)

        self.assertFalse(interrupted)
        self.assertFalse(cancel_event.is_set())
        self.assertEqual(queued, "próxima")
        self.assertFalse(response.is_alive())

    def test_ctrl_c_keeps_keyboard_interrupt_behavior(self):
        cancel_event = threading.Event()
        response = threading.Thread(target=cancel_event.wait)
        response.start()
        keys = iter(["\x03"])

        with self.assertRaises(KeyboardInterrupt):
            _wait_for_response_or_escape(
                response,
                cancel_event,
                Mock(),
                lambda: next(keys, None),
            )
        cancel_event.set()
        response.join(timeout=1)


class InputPauseTests(unittest.TestCase):
    """A pergunta [s/N] roda na thread da resposta; a thread principal não pode
    consumir teclas ao mesmo tempo, senão a resposta do usuário se perde."""

    def tearDown(self):
        INPUT_PAUSE.clear()

    def test_keyboard_is_not_consumed_while_input_pause_is_set(self):
        cancel_event = threading.Event()
        response_done = threading.Event()
        response = threading.Thread(target=response_done.wait)
        response.start()

        first_read = []
        start = time.monotonic()

        def read_key():
            first_read.append(time.monotonic() - start)
            response_done.set()
            return None

        INPUT_PAUSE.set()
        threading.Timer(0.3, INPUT_PAUSE.clear).start()

        _wait_for_response_or_escape(response, cancel_event, Mock(), read_key)
        response.join(timeout=1)

        self.assertTrue(first_read, "read_key precisa voltar a ser chamado após a pausa")
        self.assertGreaterEqual(
            first_read[0],
            0.25,
            "read_key foi chamado durante a pausa: a tecla do usuário seria roubada",
        )

    def _executor(self):
        with (
            patch("app.ComputerTools"),
            patch("app.FileTools"),
            patch("app.DeveloperTools"),
            patch("app.ImageGenerator"),
        ):
            return LocalToolExecutor(Mock(), Mock(), browser_tools=Mock())

    def _pendente(self, label="Enviar", token="tok-1"):
        return {
            "status": "confirmation_required",
            "data": {"label": label, "confirmation_token": token},
        }

    def test_without_the_setting_the_action_runs_without_asking(self):
        """Padrão: nada de [s/N] — a extensão devolve o token e o app segue."""
        executor = self._executor()
        with patch.dict(os.environ, {}, clear=False), patch("app.ui.prompt") as prompt_falso:
            os.environ.pop("AGENTE_CONFIRMAR_ACOES", None)
            result = executor._confirm_browser_outcome(
                self._pendente(), lambda token: {"status": "success", "token": token}
            )

        prompt_falso.assert_not_called()
        self.assertEqual(result, {"status": "success", "token": "tok-1"})

    def test_rejected_automatic_authorisation_fails_with_a_clear_code(self):
        """Defensivo: se o token não for aceito, não devolve 'aguarda confirmação'."""
        executor = self._executor()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENTE_CONFIRMAR_ACOES", None)
            result = executor._confirm_browser_outcome(
                self._pendente(),
                lambda token: {"status": "confirmation_required", "data": {"confirmation_token": "outro"}},
            )

        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["error_code"], "confirmation_not_accepted")

    def test_ordinary_outcome_passes_through_untouched(self):
        executor = self._executor()
        self.assertEqual(executor._confirm_browser_outcome({"status": "success"}, lambda token: {}), {"status": "success"})

    def test_confirmation_prompt_runs_with_pause_on_and_releases_it(self):
        executor = self._executor()
        seen = []

        def prompt(_message):
            seen.append(INPUT_PAUSE.is_set())
            return "s"

        with patch.dict(os.environ, {"AGENTE_CONFIRMAR_ACOES": "1"}), patch("app.ui.prompt", side_effect=prompt):
            result = executor._confirm_browser_outcome(
                self._pendente(), lambda token: {"status": "success", "token": token}
            )

        self.assertEqual(seen, [True], "o prompt precisa rodar com INPUT_PAUSE ligado")
        self.assertFalse(INPUT_PAUSE.is_set(), "INPUT_PAUSE precisa ser liberado no finally")
        self.assertEqual(result, {"status": "success", "token": "tok-1"})

    def test_pause_is_released_even_when_the_prompt_fails(self):
        executor = self._executor()

        with patch.dict(os.environ, {"AGENTE_CONFIRMAR_ACOES": "1"}), \
                patch("app.ui.prompt", side_effect=EOFError("sem teclado")):
            with self.assertRaises(EOFError):
                executor._confirm_browser_outcome(self._pendente(), lambda token: {})

        self.assertFalse(INPUT_PAUSE.is_set(), "um prompt que falha não pode travar o teclado")

    def test_denied_confirmation_keeps_user_denied_outcome(self):
        executor = self._executor()
        with patch.dict(os.environ, {"AGENTE_CONFIRMAR_ACOES": "1"}), patch("app.ui.prompt", return_value="n"):
            result = executor._confirm_browser_outcome(self._pendente("Comprar", "tok-2"), lambda token: {"status": "success"})

        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["error_code"], "user_denied")

    def test_visual_click_is_declared_as_handled_by_the_agent(self):
        """O ramo antigo era código morto e lia analysis no nível errado."""
        executor = self._executor()
        result = executor.execute(
            "browser_visual_click", {"tab_id": 1, "goal": "enviar"}
        )

        self.assertEqual(result["error_code"], "handled_by_agent")
        executor.browser.screenshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()