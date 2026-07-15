import sqlite3
import tempfile
import unittest
from pathlib import Path

from repositories import wrong_question_repo


class WrongQuestionSchemaCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "memory.db")
        self.original_memory_db = wrong_question_repo.MEMORY_DB
        wrong_question_repo.MEMORY_DB = self.db_path

    def tearDown(self):
        wrong_question_repo.MEMORY_DB = self.original_memory_db
        self.temp_dir.cleanup()

    def _create_upstream_schema(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """CREATE TABLE user_wrong_questions (
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                images TEXT,
                my_understanding TEXT DEFAULT ''
            )"""
        )
        conn.execute(
            """INSERT INTO user_wrong_questions
               (user_id, subject, question, correct_answer, images, my_understanding)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (7, "数学", "upstream row", "42", "[]", "review note"),
        )
        conn.commit()
        conn.close()

    def test_professional_migration_preserves_upstream_columns_and_rows(self):
        self._create_upstream_schema()

        rows = wrong_question_repo.list_user_wrong_questions(7)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["question"], "upstream row")
        self.assertEqual(rows[0]["images"], "[]")
        self.assertEqual(rows[0]["my_understanding"], "review note")

        conn = sqlite3.connect(self.db_path)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(user_wrong_questions)")}
        conn.close()
        self.assertTrue(set(wrong_question_repo.STRUCTURED_COLUMNS).issubset(columns))
        self.assertIn("images", columns)
        self.assertIn("my_understanding", columns)

    def test_professional_insert_works_after_upstream_schema_creation(self):
        self._create_upstream_schema()

        saved = wrong_question_repo.bulk_create_wrong_questions(
            7,
            [{
                "subject": "专业课",
                "question": "embedded row",
                "correct_answer": "answer",
                "source_filename": "sample.pdf",
                "source_file_type": "pdf",
                "tags": ["重点"],
            }],
        )

        self.assertEqual(saved, 1)
        rows = wrong_question_repo.list_user_wrong_questions(7, subject="专业课")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_filename"], "sample.pdf")
        self.assertEqual(rows[0]["tags"], ["重点"])


if __name__ == "__main__":
    unittest.main()
