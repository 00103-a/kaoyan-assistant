from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "preview_wrongbook.bak.html"
APP = ROOT / "app.py"


class WrongbookLatexPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = TEMPLATE.read_text(encoding="utf-8")
        cls.app = APP.read_text(encoding="utf-8")

    def test_question_field_has_live_preview_region(self):
        self.assertIn('id="addQuestionPreview"', self.html)
        self.assertIn('id="addQuestionPreviewContent"', self.html)
        self.assertIn('aria-live="polite"', self.html)

    def test_preview_uses_safe_text_and_katex(self):
        self.assertIn("function updateQuestionPreview()", self.html)
        self.assertIn("previewContent.textContent = question;", self.html)
        self.assertIn("renderMathInElement(previewContent", self.html)
        self.assertNotIn("previewContent.innerHTML = question", self.html)

    def test_preview_updates_for_manual_and_programmatic_input(self):
        self.assertIn("questionInput.addEventListener('input', updateQuestionPreview);", self.html)
        self.assertGreaterEqual(self.html.count("updateQuestionPreview();"), 4)

    def test_ocr_never_falls_back_to_model_reasoning(self):
        ocr_start = self.html.index("function aiExtractQuestion()")
        ocr_end = self.html.index("function _cleanAIOutput", ocr_start)
        ocr_code = self.html[ocr_start:ocr_end]
        self.assertIn("function extractOcrQuestion(message)", ocr_code)
        self.assertIn("message.content", ocr_code)
        self.assertNotIn("reasoning_content", ocr_code)
        self.assertIn("qEl.placeholder =", ocr_code)

    def test_all_katex_display_math_is_inline(self):
        self.assertIn(".question-preview .katex-display {\n    display: inline", self.html)
        self.assertIn(".katex-display { display: inline !important;", self.app)

    def test_correct_answer_and_explanation_normalize_bare_latex_before_katex_rendering(self):
        start = self.html.index("function normalizeLatexSegment")
        end = self.html.index("function renderCards", start)
        latex_helper = self.html[start:end]
        self.assertIn("function normalizeLatexSegment", latex_helper)
        self.assertIn("\\begin", latex_helper)
        self.assertIn("\\frac", latex_helper)
        self.assertIn("fixLatex(q.correctAnswer)", self.html)
        self.assertIn("fixLatex(q.explanation)", self.html)


if __name__ == "__main__":
    unittest.main()
