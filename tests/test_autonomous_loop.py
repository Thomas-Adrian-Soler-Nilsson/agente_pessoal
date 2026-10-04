"""Testes dos comandos /loop e /goal (modo autonomo) e do /verboso."""
import unittest

from app import (
    GOAL_DEFAULT_ROUNDS,
    LOOP_DEFAULT_ROUNDS,
    LOOP_MAX_ROUNDS,
    _autonomous_command,
    _command_help,
    _loop_continuation,
    _loop_finished,
    _loop_rounds,
    _normalize_slash_command,
)


class SlashCommandTests(unittest.TestCase):
    def test_plain_text_is_not_a_command(self):
        self.assertEqual(_normalize_slash_command("converse com o deepseek"), ("", ""))
        self.assertEqual(_normalize_slash_command(""), ("", ""))
        self.assertEqual(_normalize_slash_command(None), ("", ""))

    def test_command_and_parameter_are_split(self):
        self.assertEqual(_normalize_slash_command("/goal  debater IA  "), ("/goal", "debater IA"))
        self.assertEqual(_normalize_slash_command("/voz"), ("/voz", ""))


class LoopRoundsTests(unittest.TestCase):
    def test_default_and_explicit_rounds(self):
        self.assertEqual(_loop_rounds("", LOOP_DEFAULT_ROUNDS), LOOP_DEFAULT_ROUNDS)
        self.assertEqual(_loop_rounds("7", LOOP_DEFAULT_ROUNDS), 7)

    def test_off_words_disable(self):
        for word in ("off", "parar", "0", "desligar", "limpar"):
            with self.subTest(word=word):
                self.assertEqual(_loop_rounds(word, LOOP_DEFAULT_ROUNDS), 0)

    def test_invalid_value_is_reported(self):
        self.assertIsNone(_loop_rounds("abc", LOOP_DEFAULT_ROUNDS))

    def test_out_of_range_is_clamped(self):
        self.assertEqual(_loop_rounds("9999", LOOP_DEFAULT_ROUNDS), LOOP_MAX_ROUNDS)
        self.assertEqual(_loop_rounds("-3", LOOP_DEFAULT_ROUNDS), 1)


class AutonomousCommandTests(unittest.TestCase):
    def test_plain_text_is_not_an_autonomous_command(self):
        self.assertIsNone(_autonomous_command("oi, tudo bem?"))

    def test_loop_arms_without_clearing_an_existing_goal(self):
        state = _autonomous_command("/loop 3")
        self.assertEqual(state["rounds"], 3)
        self.assertIsNone(state["goal"], "/loop nao pode apagar o objetivo em andamento")
        self.assertIn("3 rodada", state["message"])

    def test_loop_off_disables(self):
        state = _autonomous_command("/loop off")
        self.assertEqual(state["rounds"], 0)
        self.assertEqual(state["goal"], "")

    def test_goal_sets_the_objective_and_the_rounds(self):
        state = _autonomous_command("/goal debater regulacao de IA com o deepseek")
        self.assertEqual(state["goal"], "debater regulacao de IA com o deepseek")
        self.assertEqual(state["rounds"], GOAL_DEFAULT_ROUNDS)
        self.assertIn("debater regulacao de IA", state["message"])

    def test_goal_off_clears(self):
        state = _autonomous_command("/goal off")
        self.assertEqual(state["goal"], "")
        self.assertEqual(state["rounds"], 0)

    def test_goal_without_text_shows_usage(self):
        state = _autonomous_command("/goal")
        self.assertIsNone(state["goal"], "sem texto nao deve limpar nem definir")
        self.assertIsNone(state["rounds"])
        self.assertIn("/goal", state["message"])

    def test_invalid_loop_keeps_the_current_state(self):
        state = _autonomous_command("/loop abc")
        self.assertIsNone(state["rounds"])
        self.assertIsNone(state["goal"])
        self.assertIn(f"1-{LOOP_MAX_ROUNDS}", state["message"])


class LoopContinuationTests(unittest.TestCase):
    def test_goal_continuation_quotes_the_goal_and_asks_for_a_marker(self):
        text = _loop_continuation("debater IA", 2, 10)
        self.assertIn("debater IA", text)
        self.assertIn("rodada automatica 2 de 10", text)
        self.assertIn("OBJETIVO CONCLUÍDO", text)

    def test_free_continuation_has_no_goal_block(self):
        text = _loop_continuation("", 1, 5)
        self.assertIn("TAREFA CONCLUÍDA", text)
        self.assertNotIn("Objetivo:", text)


class LoopFinishedTests(unittest.TestCase):
    def test_detects_completion_markers(self):
        self.assertTrue(_loop_finished("OBJETIVO CONCLUÍDO: conversei com o DeepSeek."))
        self.assertTrue(_loop_finished("tarefa concluida"))
        self.assertTrue(_loop_finished("Nada mais a fazer por aqui."))

    def test_ordinary_answer_is_not_completion(self):
        self.assertFalse(_loop_finished("Vou mandar a próxima pergunta agora."))
        self.assertFalse(_loop_finished(""))
        self.assertFalse(_loop_finished(None))


class CommandHelpTests(unittest.TestCase):
    def test_help_lists_every_autonomous_command(self):
        text = _command_help()
        for token in ("/voz", "/loop", "/goal", "/verboso", "Esc"):
            with self.subTest(token=token):
                self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
