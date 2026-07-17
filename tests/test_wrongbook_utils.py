import sqlite3
import json
import unittest

from wrongbook_utils import save_wrongbook_payload


SCHEMA = """
CREATE TABLE user_wrong_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    knowledge_id INTEGER,
    subject TEXT,
    chapter_name TEXT,
    question TEXT,
    user_answer TEXT,
    correct_answer TEXT,
    explanation TEXT,
    error_count INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active',
    last_reviewed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


class WrongbookPayloadTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def test_saves_trimmed_payload_with_defaults(self):
        result = save_wrongbook_payload(
            self.conn,
            7,
            {"question": "  求极限  ", "correctAnswer": " -4 ", "errorCount": "8"},
        )

        self.assertTrue(result["ok"])
        row = self.conn.execute(
            "SELECT user_id, subject, question, correct_answer, error_count, status FROM user_wrong_questions"
        ).fetchone()
        self.assertEqual(row, (7, "数学", "求极限", "-4", 5, "active"))

    def test_duplicate_question_updates_existing_row(self):
        first = save_wrongbook_payload(
            self.conn,
            7,
            {"subject": "高数", "question": "计算积分", "myAnswer": "1", "errorCount": 1},
        )
        second = save_wrongbook_payload(
            self.conn,
            7,
            {
                "subject": "数学",
                "question": "  计算积分  ",
                "myAnswer": "2",
                "correctAnswer": "3",
                "explanation": "重新整理",
                "errorCount": 4,
            },
        )

        self.assertTrue(first["inserted"])
        self.assertTrue(second["updated"])
        rows = self.conn.execute(
            "SELECT subject, question, user_answer, correct_answer, explanation, error_count FROM user_wrong_questions"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], ("数学", "计算积分", "2", "3", "重新整理", 4))

    def test_preserves_question_line_breaks_when_saving(self):
        question = "Question stem\nA) First option\nB) Second option"
        self.conn.execute(
            "INSERT INTO user_wrong_questions (user_id, question) VALUES (?, ?)",
            (7, "Question stem A) First option B) Second option"),
        )

        result = save_wrongbook_payload(self.conn, 7, {"question": question})

        self.assertTrue(result["updated"])
        stored = self.conn.execute("SELECT question FROM user_wrong_questions").fetchone()[0]
        self.assertEqual(stored, question)

    def test_rejects_blank_question(self):
        result = save_wrongbook_payload(self.conn, 7, {"question": "   "})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "请先填写题目")
        count = self.conn.execute("SELECT COUNT(*) FROM user_wrong_questions").fetchone()[0]
        self.assertEqual(count, 0)

    def test_stores_images_as_json_when_schema_supports_them(self):
        self.conn.execute("ALTER TABLE user_wrong_questions ADD COLUMN images TEXT")
        images = ["data:image/jpeg;base64,AAAA", "data:image/png;base64,BBBB"]

        result = save_wrongbook_payload(
            self.conn,
            7,
            {"question": "图片题", "images": images},
        )

        self.assertTrue(result["ok"])
        stored = self.conn.execute("SELECT images FROM user_wrong_questions").fetchone()[0]
        self.assertEqual(json.loads(stored), images)


if __name__ == "__main__":
    unittest.main()
