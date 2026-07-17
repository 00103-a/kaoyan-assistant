from pathlib import Path
import unittest


class AppSyntaxTests(unittest.TestCase):
    def test_app_compiles(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        compile(app_path.read_text(encoding="utf-8-sig"), str(app_path), "exec")


if __name__ == "__main__":
    unittest.main()
