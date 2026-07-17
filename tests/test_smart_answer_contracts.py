from pathlib import Path
import unittest

from wrongbook_utils import extract_final_message_content, parse_smart_answer_output


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


class SmartAnswerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = APP.read_text(encoding="utf-8")

    def test_final_message_content_never_falls_back_to_reasoning(self):
        self.assertEqual(
            extract_final_message_content(
                {"content": "[ANSWER]\n$x=1$\n[KNOWLEDGE]\nEquation", "reasoning_content": "internal analysis"}
            ),
            "[ANSWER]\n$x=1$\n[KNOWLEDGE]\nEquation",
        )
        self.assertEqual(extract_final_message_content({"content": "", "reasoning_content": "internal analysis"}), "")

    def test_smart_answer_requires_a_complete_structured_final_response(self):
        parsed = parse_smart_answer_output("[ANSWER]\n$x=1$\n[KNOWLEDGE]\nEquation, Algebra")
        self.assertEqual(parsed["answer"], "$x=1$")
        self.assertEqual(parsed["knowledge"], ["Equation", "Algebra"])
        self.assertEqual(parse_smart_answer_output("First I need to analyse the question")["answer"], "")
        self.assertEqual(parse_smart_answer_output("[ANSWER]\n$x=1$")["answer"], "")

    def test_smart_answer_accepts_a_safe_unstructured_final_answer_as_fallback(self):
        raw = "答案：$x=1$\n\n解析：代入原式即可验证。"
        parsed = parse_smart_answer_output(raw)
        self.assertEqual(parsed["answer"], raw)
        self.assertEqual(parsed["knowledge"], [])
        self.assertEqual(parsed["description"], "")

    def test_smart_answer_view_prepares_math_for_the_question_preview(self):
        self.assertIn("_prepare_math_for_display(_wb_q_raw)", self.app)
        self.assertIn("_prepare_math_for_display(_wb_ca_raw)", self.app)
        self.assertIn("_prepare_math_for_display(_wb_ex_raw)", self.app)

    def test_smart_answer_pipeline_and_views_do_not_display_reasoning_or_raw_fallbacks(self):
        pipeline_start = self.app.index("def run_pipeline(")
        pipeline_end = self.app.index("# ==================== LLM", pipeline_start)
        pipeline = self.app[pipeline_start:pipeline_end]
        self.assertNotIn('delta = delta_obj.get("reasoning_content")', pipeline)
        self.assertNotIn('raw_full = msg.get(\'reasoning_content\')', pipeline)
        self.assertIn("extract_final_message_content", pipeline)

        smart_start = self.app.index('st.markdown("### 智能回答")')
        smart_end = self.app.index("# ====================", smart_start + 1)
        smart_view = self.app[smart_start:smart_end]
        self.assertIn("parse_smart_answer_output", smart_view)
        self.assertNotIn("answer_text = raw_full", smart_view)
        self.assertNotIn("answer = _extract_content(mm_msg)", smart_view)

    def test_home_smart_answer_keeps_uploaded_image_and_description_for_wrongbook_extraction(self):
        self.assertIn("st.session_state._last_question_image = img_data or \"\"", self.app)
        self.assertIn("description_text = output.get(\"description\", \"\")", self.app)
        self.assertIn("st.session_state._wb_question_image = st.session_state.get(\"_last_question_image\", \"\")", self.app)
        self.assertIn('st.session_state.get("_wb_question_image", "")', self.app)


if __name__ == "__main__":
    unittest.main()
