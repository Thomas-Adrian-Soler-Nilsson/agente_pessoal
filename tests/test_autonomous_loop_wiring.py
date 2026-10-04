"""Prova de ponta a ponta do modo autonomo: roda o laco real do run_text_provider
com um agente falso e uma sequencia roteirizada de mensagens do usuario.
"""
import unittest
from io import StringIO
from unittest.mock import Mock, patch

from rich.console import Console

from app import GOAL_DEFAULT_ROUNDS, run_text_provider
from ui import ui


class FakeAgent:
    def __init__(self, answers=None):
        self.received = []
        self.answers = list(answers or [])

    def set_personality(self, personality):
        return None

    def ask_stream(self, text, cancel_event=None):
        self.received.append(text)
        yield self.answers.pop(0) if self.answers else "Continuando o trabalho."


def _prompts(*messages):
    """Devolve um _chat_prompt roteirizado; a ultima mensagem deve encerrar."""
    remaining = list(messages)

    def fake_prompt(default=""):
        if not remaining:
            return "sair"
        return remaining.pop(0)

    return fake_prompt


class AutonomousLoopWiringTests(unittest.TestCase):
    def _run(self, agent, *messages, interrupt_first=False):
        output = StringIO()
        state = {"interrupted": False}

        def wait(response_thread, cancel_event, stop_speech, read_key=None):
            # Como no caminho POSIX real: espera a thread da resposta terminar.
            response_thread.join(timeout=10)
            if interrupt_first and not state["interrupted"]:
                state["interrupted"] = True
                return "", True
            return "", False

        with patch.object(ui, "console", Console(file=output, width=100, force_terminal=False, theme=ui.THEME)), \
                patch("app._chat_prompt", side_effect=_prompts(*messages)), \
                patch("app._wait_for_response_or_escape", side_effect=wait), \
                patch("audio.text_to_speech.TextToSpeech", Mock()):
            run_text_provider("Teste", agent, "groq", "edge")

        return output.getvalue()

    def test_goal_starts_immediately_and_keeps_going_alone(self):
        agent = FakeAgent()

        output = self._run(agent, "/goal debater IA com o deepseek")

        self.assertEqual(agent.received[0], "debater IA com o deepseek",
                         "o /goal precisa começar a trabalhar sem pedir outra mensagem")
        self.assertEqual(len(agent.received), 1 + GOAL_DEFAULT_ROUNDS,
                         "o agente deve rodar sozinho pelo numero de rodadas prometido")
        for extra in agent.received[1:]:
            self.assertIn("rodada automatica", extra)
            self.assertIn("debater IA com o deepseek", extra)
        self.assertIn("Rodada automática 1/", output)
        self.assertIn("limite de", output)

    def test_completion_marker_stops_the_loop_early(self):
        agent = FakeAgent(["OBJETIVO CONCLUÍDO: conversei com o DeepSeek e resumi a resposta."])

        output = self._run(agent, "/goal conversar com o deepseek")

        self.assertEqual(len(agent.received), 1, "o marcador de conclusão deve encerrar o laço")
        self.assertIn("declarou a tarefa concluída", output)

    def test_loop_rounds_apply_after_the_user_task(self):
        agent = FakeAgent()

        self._run(agent, "/loop 2", "resuma as noticias de hoje")

        self.assertEqual(agent.received[0], "resuma as noticias de hoje")
        self.assertEqual(len(agent.received), 1 + 2)
        for extra in agent.received[1:]:
            self.assertIn("rodada automatica", extra)
            self.assertNotIn("Objetivo:", extra)

    def test_loop_off_does_not_start_any_automatic_round(self):
        agent = FakeAgent()

        self._run(agent, "/loop off", "faca apenas isso", "/loop off")

        self.assertEqual(len(agent.received), 1, "sem /loop armado nao pode haver rodada automatica")

    def test_escape_disarms_the_autonomous_mode(self):
        agent = FakeAgent()

        output = self._run(agent, "/goal algo demorado", interrupt_first=True)

        self.assertEqual(len(agent.received), 1, "Esc precisa encerrar o modo autonomo")
        self.assertIn("Modo autônomo encerrado", output)

    def test_plain_message_without_commands_is_untouched(self):
        agent = FakeAgent()

        self._run(agent, "oi, tudo bem?")

        self.assertEqual(agent.received, ["oi, tudo bem?"])

    def test_help_and_verbose_do_not_reach_the_agent(self):
        agent = FakeAgent()

        output = self._run(agent, "/ajuda", "/verboso", "/verboso", "faca algo")

        self.assertEqual(agent.received, ["faca algo"])
        self.assertIn("/loop", output)
        self.assertIn("Modo verboso LIGADO", output)
        self.assertIn("Modo verboso DESLIGADO", output)


if __name__ == "__main__":
    unittest.main()
