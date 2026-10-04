import threading
import unittest
from unittest.mock import Mock, patch

from app import _wait_for_response_or_escape, run


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


if __name__ == "__main__":
    unittest.main()