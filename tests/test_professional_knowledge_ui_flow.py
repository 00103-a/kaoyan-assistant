import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_DIR = Path(__file__).resolve().parents[1]


def _find_by_label(elements, label, occurrence=0):
    matches = [element for element in elements if element.label == label]
    if len(matches) <= occurrence:
        raise AssertionError(f"未找到控件：{label}（序号 {occurrence}）")
    return matches[occurrence]


class ProfessionalKnowledgeUiFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "memory.db"
        self.original_memory_db_env = os.environ.get("MEMORY_DB")
        self.original_api_key_env = os.environ.get("AI_API_KEY")
        os.environ["MEMORY_DB"] = str(self.db_path)
        os.environ["AI_API_KEY"] = ""

        import knowledge_base
        import professional_knowledge.catalog as catalog
        import repositories.knowledge_repo as knowledge_repo
        import repositories.wrong_question_repo as wrong_question_repo
        import services.professional_knowledge_task_service as task_service

        self.knowledge_base = knowledge_base
        self.catalog = catalog
        self.knowledge_repo = knowledge_repo
        self.wrong_question_repo = wrong_question_repo
        self.task_service = task_service
        self.original_memory_db = knowledge_base.MEMORY_DB
        self.original_wrong_question_db = wrong_question_repo.MEMORY_DB
        self.original_custom_config = catalog.CUSTOM_SUBJECTS_CONFIG_PATH
        self.original_tasks_dir = task_service.TASKS_DIR
        self.original_llm_call = knowledge_base._call_llm_api

        knowledge_base.MEMORY_DB = str(self.db_path)
        wrong_question_repo.MEMORY_DB = str(self.db_path)
        catalog.CUSTOM_SUBJECTS_CONFIG_PATH = self.temp_dir / "custom_subjects.json"
        task_service.TASKS_DIR = self.temp_dir / "tasks"

    def tearDown(self):
        self.knowledge_base.MEMORY_DB = self.original_memory_db
        self.wrong_question_repo.MEMORY_DB = self.original_wrong_question_db
        self.catalog.CUSTOM_SUBJECTS_CONFIG_PATH = self.original_custom_config
        self.task_service.TASKS_DIR = self.original_tasks_dir
        self.knowledge_base._call_llm_api = self.original_llm_call
        if self.original_memory_db_env is None:
            os.environ.pop("MEMORY_DB", None)
        else:
            os.environ["MEMORY_DB"] = self.original_memory_db_env
        if self.original_api_key_env is None:
            os.environ.pop("AI_API_KEY", None)
        else:
            os.environ["AI_API_KEY"] = self.original_api_key_env
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_app(self):
        app = AppTest.from_file(str(PROJECT_DIR / "app_kb.py"), default_timeout=30).run()
        if app.exception:
            raise AssertionError(app.exception)
        return app

    def _seed_knowledge(self, subject, name):
        with sqlite3.connect(self.db_path) as conn:
            self.knowledge_repo.ensure_knowledge_schema(conn)
            self.knowledge_repo.save_confirmed_knowledge_points(
                conn,
                user_id=1,
                points=[
                    {
                        "knowledge_name": name,
                        "core_definition": f"{name}的核心定义。",
                        "source_text": f"原文依据：{name}",
                    }
                ],
                material_meta={"subject": subject},
                strict=False,
            )
            conn.commit()

    @staticmethod
    def _markdown_contains(app, text):
        return any(text in str(element.value) for element in app.markdown)

    def test_formal_page_keeps_knowledge_base_and_removes_legacy_tools(self):
        self._seed_knowledge("408综合", "栈")
        app = self._run_app()

        self.assertTrue(self._markdown_contains(app, "专业课学习"))
        self.assertTrue(self._markdown_contains(app, "拖放文件到这里"))
        self.assertTrue(self._markdown_contains(app, "单个文件最大 200MB"))
        self.assertTrue(self._markdown_contains(app, "选择文件"))
        self.assertTrue(self._markdown_contains(app, "408综合知识库"))
        self.assertTrue(self._markdown_contains(app, "栈"))
        self.assertFalse(any(item.label == "粘贴文本" for item in app.text_area))
        self.assertFalse(any(item.label == "确认文本并开始识别" for item in app.button))
        self.assertFalse(any(item.label == "继续处理这份资料" for item in app.button))
        self.assertFalse(self._markdown_contains(app, "高级校对与知识库工具"))
        self.assertFalse(self._markdown_contains(app, "默认全部参与回答"))
        self.assertFalse(self._markdown_contains(app, "左侧负责筛选"))
        self.assertFalse(self._markdown_contains(app, "广告与个人履历不会入库"))

    def test_assistant_answer_offers_trimmed_pdf_download(self):
        app = AppTest.from_file(str(PROJECT_DIR / "app_kb.py"), default_timeout=30)
        app.session_state["pk_chat_history_1_408综合"] = [
            {
                "role": "user",
                "content": "请根据已选资料梳理完整的知识框架，并标出各部分之间的关系。",
            },
            {
                "role": "assistant",
                "content": (
                    "根据您提供的资料，下面给出完整框架。\n\n"
                    "## 数据结构\n\n1. 线性表、栈和队列。"
                ),
            },
        ]
        app.run()
        if app.exception:
            raise AssertionError(app.exception)

        self.assertTrue(
            any(item.label == "导出本回答精简版 PDF" for item in app.get("download_button"))
        )

    def test_formal_knowledge_base_follows_selected_subject(self):
        self._seed_knowledge("408综合", "栈")
        self._seed_knowledge("医学考研", "肺炎")
        app = self._run_app()
        self.assertTrue(self._markdown_contains(app, "408综合知识库"))
        self.assertTrue(self._markdown_contains(app, "栈"))
        self.assertFalse(self._markdown_contains(app, "肺炎的核心定义"))

        _find_by_label(app.selectbox, "专业课").set_value("医学考研").run()
        if app.exception:
            raise AssertionError(app.exception)
        self.assertTrue(self._markdown_contains(app, "医学考研知识库"))
        self.assertTrue(self._markdown_contains(app, "肺炎"))
        self.assertFalse(self._markdown_contains(app, "栈的核心定义"))

    def test_selected_knowledge_and_detail_stay_in_sync(self):
        self._seed_knowledge("408综合", "栈")
        self._seed_knowledge("408综合", "队列")
        app = self._run_app()
        selector = _find_by_label(app.radio, "知识条目列表")

        self.assertTrue(self._markdown_contains(app, "队列的核心定义"))
        with sqlite3.connect(self.db_path) as conn:
            target_id = str(
                conn.execute(
                    """SELECT id FROM user_knowledge
                       WHERE subject='408综合' AND knowledge_name='栈'"""
                ).fetchone()[0]
            )
        selector.set_value(target_id).run()
        if app.exception:
            raise AssertionError(app.exception)

        self.assertTrue(self._markdown_contains(app, "栈的核心定义"))
        self.assertFalse(self._markdown_contains(app, "队列的核心定义"))

    def test_repository_option_only_shows_knowledge_name(self):
        label = self.knowledge_base._format_repo_option(
            {
                "knowledge_name": "页式虚拟存储器",
                "is_ai_expansion": True,
                "subject": "408",
                "mastery_state": "待复习",
            }
        )
        self.assertEqual(label, "页式虚拟存储器")

    def test_current_knowledge_card_hides_source_badges(self):
        self._seed_knowledge("408综合", "页式虚拟存储器")
        app = self._run_app()
        self.assertFalse(self._markdown_contains(app, "原文整理"))
        self.assertFalse(self._markdown_contains(app, "AI扩展 · 需核对教材"))

    def test_current_knowledge_can_preview_and_save_ai_expansion(self):
        self._seed_knowledge("408综合", "页式虚拟存储器")
        self.knowledge_base._call_llm_api = lambda *args, **kwargs: (
            "## 关联知识点及关系\n\n- TLB：用于加速地址转换。"
        )
        app = self._run_app()

        _find_by_label(app.button, "AI 发散当前条目").click().run()
        if app.exception:
            raise AssertionError(app.exception)
        self.assertTrue(self._markdown_contains(app, "AI 发散预览"))
        self.assertTrue(self._markdown_contains(app, "TLB：用于加速地址转换"))

        _find_by_label(app.button, "保存发散内容").click().run()
        if app.exception:
            raise AssertionError(app.exception)
        with sqlite3.connect(self.db_path) as conn:
            saved = conn.execute(
                "SELECT review_content FROM user_knowledge WHERE knowledge_name=?",
                ("页式虚拟存储器",),
            ).fetchone()[0]
        self.assertIn("TLB：用于加速地址转换", saved)
        self.assertTrue(self._markdown_contains(app, "已保存的 AI 发散内容"))

    def test_custom_subject_wizard_selects_new_subject(self):
        app = self._run_app()
        _find_by_label(app.text_input, "专业课名称 *").set_value("管理学原理")
        _find_by_label(app.text_input, "考试代码（可选）").set_value("803")
        _find_by_label(app.text_area, "希望系统重点识别什么（可选）").set_value(
            "优先识别理论流派、代表人物和易混点。"
        )
        _find_by_label(app.button, "创建并开始导入资料").click().run()
        if app.exception:
            raise AssertionError(app.exception)

        subject_selector = _find_by_label(app.selectbox, "专业课", occurrence=0)
        self.assertIn("管理学原理", subject_selector.options)
        self.assertEqual(subject_selector.value, "管理学原理")
        self.assertTrue(self.catalog.CUSTOM_SUBJECTS_CONFIG_PATH.exists())

    def test_configured_subject_can_be_removed_after_confirmation(self):
        app = self._run_app()
        subject_selector = _find_by_label(app.selectbox, "专业课")
        self.assertIn("408综合", subject_selector.options)
        self.assertIn("医学考研", subject_selector.options)

        _find_by_label(app.button, "删除专业课").click().run()
        if app.exception:
            raise AssertionError(app.exception)
        _find_by_label(app.checkbox, "我确认移除“408综合”").set_value(True)
        _find_by_label(app.button, "确认删除专业课").click().run()
        if app.exception:
            raise AssertionError(app.exception)

        self.assertNotIn("408综合", _find_by_label(app.selectbox, "专业课").options)
        disabled_profile = self.catalog.get_rag_knowledge_base_by_subject("408综合")
        self.assertIsNotNone(disabled_profile)
        self.assertFalse(disabled_profile.enabled)

if __name__ == "__main__":
    unittest.main()
