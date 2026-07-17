from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
TEMPLATE = ROOT / "preview_wrongbook.bak.html"


class WrongbookRestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = APP.read_text(encoding="utf-8")
        cls.html = TEMPLATE.read_text(encoding="utf-8")

    def test_app_restores_unified_save_and_bridge(self):
        self.assertIn("from wrongbook_utils import (", self.app)
        self.assertIn("detect_subject,", self.app)
        self.assertIn("save_wrongbook_payload,", self.app)
        self.assertIn("__wb_action_bridge__", self.app)
        self.assertIn("save_wrongbook_payload(_conn, uid, _payload)", self.app)

    def test_template_submits_save_through_parent_bridge(self):
        self.assertIn("window.parent.document.querySelector('.st-key-__wb_action_bridge__ textarea')", self.html)
        self.assertIn("action: 'save'", self.html)

    def test_template_receives_runtime_api_configuration(self):
        self.assertIn("WB_API_BASE", self.app)
        self.assertIn("WB_API_KEY", self.app)

    def test_template_contains_working_detail_page_path(self):
        self.assertIn('id="detailPage"', self.html)
        self.assertIn('onclick="showDetail()"', self.html)
        self.assertIn("function showDetail()", self.html)
        self.assertIn("function initDetailPage()", self.html)
        self.assertIn("function renderCards(", self.html)


if __name__ == "__main__":
    unittest.main()
