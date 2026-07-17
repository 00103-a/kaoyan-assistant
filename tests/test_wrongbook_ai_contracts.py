from pathlib import Path
import unittest

from wrongbook_utils import (
    parse_wrongbook_ai_answer,
    parse_wrongbook_ai_question,
    split_wrongbook_answer_explanation,
)


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
TEMPLATE = ROOT / "preview_wrongbook.bak.html"


class WrongbookAiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = APP.read_text(encoding="utf-8")
        cls.html = TEMPLATE.read_text(encoding="utf-8")

    def test_question_parser_accepts_only_exact_tagged_question(self):
        self.assertEqual(
            parse_wrongbook_ai_question("  <question>求 $x^2=1$ 的解。</question>  "),
            "求 $x^2=1$ 的解。",
        )
        self.assertEqual(parse_wrongbook_ai_question("让我先识别。<question>题目</question>"), "")
        self.assertEqual(parse_wrongbook_ai_question("没有找到题干"), "")

    def test_answer_parser_requires_separate_answer_and_explanation(self):
        parsed = parse_wrongbook_ai_answer(
            "<answer>$x=1$</answer><explanation>代入原式验证成立。</explanation>"
        )
        self.assertEqual(parsed["answer"], "$x=1$")
        self.assertEqual(parsed["explanation"], "代入原式验证成立。")
        self.assertFalse(parse_wrongbook_ai_answer("先分析题目，再得到 x=1"))
        self.assertFalse(parse_wrongbook_ai_answer("<answer>x=1</answer>"))

    def test_answer_parser_accepts_optional_description_and_safe_markdown_wrapper(self):
        parsed = parse_wrongbook_ai_answer(
            "```xml\n<description>一元方程</description>\n"
            "<answer>$x=1$</answer><explanation>代入原式验证成立。</explanation>\n```"
        )
        self.assertEqual(parsed["answer"], "$x=1$")
        self.assertEqual(parsed["explanation"], "代入原式验证成立。")

    def test_answer_parser_rejects_hidden_reasoning_leaks(self):
        self.assertFalse(
            parse_wrongbook_ai_answer(
                "<answer>x=1</answer><explanation>用户要求我先分析，所以我需要计算。</explanation>"
            )
        )

    def test_combined_legacy_answer_is_split_for_all_add_entry_points(self):
        answer, explanation = split_wrongbook_answer_explanation(
            "B) submit\n\n解析：suggest 后使用虚拟语气。"
        )
        self.assertEqual(answer, "B) submit")
        self.assertEqual(explanation, "suggest 后使用虚拟语气。")
        self.assertIn('key="g_wb_ex"', self.app)
        self.assertIn("split_wrongbook_answer_explanation", self.app)

    def test_browser_ocr_ignores_stale_requests(self):
        self.assertIn("var ocrRequestSeq = 0;", self.html)
        self.assertIn("var requestSeq = ++ocrRequestSeq;", self.html)
        self.assertIn("if (requestSeq !== ocrRequestSeq) return;", self.html)

    def test_browser_answer_uses_a_safe_fallback_when_the_xml_envelope_is_missing(self):
        start = self.html.index("function aiGenerateAnswer()")
        end = self.html.index("function saveNewQuestion()", start)
        code = self.html[start:end]
        self.assertNotIn("reasoning_content", code)
        self.assertIn("parseStrictAiAnswer", code)
        self.assertIn("textContent = parsed.answer", code)
        self.assertNotIn("AI 返回格式不合规", code)
        parser_start = self.html.index("function parseStrictAiAnswer")
        parser_end = self.html.index("function aiGenerateAnswer()", parser_start)
        parser = self.html[parser_start:parser_end]
        self.assertIn("parseSafeAiAnswerFallback", parser)
        self.assertNotIn("^\\s*<answer>", parser)
        self.assertIn("max_tokens: 2800", code)

    def test_streamlit_extraction_updates_widget_state(self):
        pending_write = 'st.session_state["_wb_pending_question"] = extracted_q'
        pending_apply = 'st.session_state["g_wb_q"] = st.session_state.pop("_wb_pending_question")'
        self.assertIn(pending_write, self.app)
        self.assertIn(pending_apply, self.app)
        self.assertLess(self.app.index(pending_apply), self.app.index('_wb_q = st.text_area("题目"'))
        self.assertIn("parse_wrongbook_ai_question", self.app)

    def test_streamlit_question_editor_shows_a_multiline_extracted_question(self):
        editor = 'value=_wb_q_raw, height=180, key="g_wb_q"'
        self.assertIn(editor, self.app)

    def test_image_save_uses_post_before_streamlit_widget_bridge(self):
        start = self.html.index("function saveNewQuestion()")
        end = self.html.index("function _fallbackUrlSave", start)
        code = self.html[start:end]
        self.assertLess(code.index("if (WB_SAVE_PORT && WB_USER_ID)"), code.index("_saveTextViaBridge(payload"))
        self.assertIn("if (images.length > 0)", code)
        self.assertIn("图片不会通过文本桥接传输", code)
        bridge_start = self.html.index("function _saveTextViaBridge")
        bridge_end = self.html.index("function _fallbackUrlSave", bridge_start)
        self.assertIn("__wb_action_bridge__", self.html[bridge_start:bridge_end])

    def test_answer_attachment_uses_a_real_label_for_the_file_input(self):
        self.assertIn('<label class="add-img-note-btn" for="imgNoteInput"', self.html)
        self.assertIn('<input id="imgNoteInput" type="file"', self.html)
        self.assertNotIn('<span class="add-img-note-btn"', self.html)

    def test_card_renders_saved_answer_images_below_my_answer_text(self):
        start = self.html.index("function renderCards(date, grouped)")
        end = self.html.index("function deleteCard", start)
        code = self.html[start:end]
        self.assertIn("renderImages(q.images)", code)

    def test_answer_image_lightbox_has_a_real_click_target(self):
        self.assertIn('id="imgLightbox"', self.html)
        self.assertIn('id="lightboxImg"', self.html)
        self.assertIn("onclick=\"closeLightbox()\"", self.html)
        self.assertIn(".img-lightbox.show", self.html)


if __name__ == "__main__":
    unittest.main()
