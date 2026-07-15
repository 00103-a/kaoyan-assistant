import io
import sys
import unittest
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from services.chat_answer_pdf_service import (
    build_chat_answer_pdf,
    chat_answer_pdf_filename,
    clean_chat_answer_for_export,
    derive_chat_pdf_title,
)


SAMPLE_ANSWER = """根据您提供的408考研大纲资料，完整的知识框架由**数据结构、计算机组成原理、操作系统、计算机网络**四个相互关联的部分构成，共同构成计算机科学与技术的核心基础。

**结论：** 408知识体系以“硬件-系统-应用”为主线，各科目既独立成章又紧密衔接。[来源1]

## 一、数据结构（45分）[来源2,3,4]

1. **线性结构：** 线性表、栈、队列和数组。
2. **树与图：** 二叉树、图的遍历、最短路径。

## 二、计算机组成原理（45分）[来源5,6]

- 存储系统与处理器协同工作。

如需进一步展开每个章节，我可以继续为您整理。"""


class ChatAnswerPdfServiceTests(unittest.TestCase):
    def test_cleaner_removes_chat_filler_but_keeps_study_content(self):
        cleaned = clean_chat_answer_for_export(SAMPLE_ANSWER)

        self.assertNotIn("根据您提供的", cleaned)
        self.assertNotIn("如需进一步", cleaned)
        self.assertIn("结论", cleaned)
        self.assertIn("数据结构", cleaned)
        self.assertIn("[来源2,3,4]", cleaned)

    def test_builds_searchable_chinese_pdf_without_question_or_filler(self):
        prompt = "请根据已选资料梳理完整的知识框架，并标出各部分之间的关系。"
        pdf_bytes = build_chat_answer_pdf(
            SAMPLE_ANSWER,
            subject="408综合",
            prompt=prompt,
            generated_at=datetime(2026, 7, 14, 22, 30),
        )

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("408综合知识框架", extracted)
        self.assertIn("数据结构", extracted)
        self.assertIn("计算机组成原理", extracted)
        self.assertNotIn("请根据已选资料", extracted)
        self.assertNotIn("根据您提供的", extracted)
        self.assertNotIn("如需进一步", extracted)

    def test_title_and_filename_follow_prompt_type(self):
        self.assertEqual(derive_chat_pdf_title("408综合", "总结高频考点"), "408综合高频考点")
        self.assertEqual(chat_answer_pdf_filename("408综合", "生成复习清单"), "408综合复习清单.pdf")


if __name__ == "__main__":
    unittest.main()
