from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
TEMPLATE = ROOT / "preview_wrongbook.bak.html"


class WrongbookFullQuestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = APP.read_text(encoding="utf-8")
        cls.html = TEMPLATE.read_text(encoding="utf-8")

    def test_database_query_loads_every_wrong_question(self):
        query_start = self.app.index(
            "SELECT id, subject, question, user_answer, correct_answer, explanation,"
        )
        query_end = self.app.index('""", (uid,))', query_start)
        self.assertNotIn("LIMIT", self.app[query_start:query_end])

    def test_home_cards_do_not_clamp_question_text_to_an_excerpt(self):
        rule_start = self.html.index(".home-card .hc-question {")
        rule_end = self.html.index("}", rule_start)
        rule = self.html[rule_start:rule_end]

        self.assertNotIn("line-clamp", rule)
        self.assertNotIn("overflow: hidden", rule)
        self.assertIn("white-space: pre-wrap", rule)
        self.assertIn("word-break: break-word", rule)

        self.assertIn("wrongbook-full-question-fix", self.app)
        self.assertIn(".home-card .hc-question", self.app)
        self.assertIn("-webkit-line-clamp: unset", self.app)

    def test_home_cards_render_the_complete_question_value(self):
        self.assertIn("${q.question.replace(/</g,'&lt;').replace(/>/g,'&gt;')}", self.html)
        self.assertNotIn("q.question.slice(", self.html)
        self.assertNotIn("q.question.substring(", self.html)


if __name__ == "__main__":
    unittest.main()
