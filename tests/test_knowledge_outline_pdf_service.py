import io
import sys
import unittest
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from services.knowledge_outline_pdf_service import build_knowledge_outline_pdf


class KnowledgeOutlinePdfServiceTests(unittest.TestCase):
    def test_builds_searchable_chinese_a4_outline(self):
        points = [
            {
                "knowledge_name": "页式虚拟存储器基本原理",
                "knowledge_type": "原理",
                "chapter_name": "计算机组成原理",
                "core_definition": "通过页表完成虚拟地址到物理地址的转换，TLB用于加速查询。",
                "keywords_json": '["页表", "地址转换", "TLB"]',
                "exam_question_styles_json": '["地址转换计算", "缺页判断"]',
                "pitfalls_json": '["混淆页号与页内偏移"]',
                "source_page": "第7页",
                "source_location": "题2",
                "material_filename": "408大纲.pdf",
                "source_text": "计算机组成原理题2：页式虚拟存储器包括页表和TLB机制。",
            },
            {
                "knowledge_name": "考场时间分配与跳题策略",
                "knowledge_type": "备考经验",
                "chapter_name": "冲刺阶段经验",
                "core_definition": "最后十五分钟集中检查，遇到异常题先跳过。",
                "keywords_json": '["考场时间", "更多计算机考研资料，请扫码咨询>>>", "候选知识点1"]',
                "source_page": "第12页",
                "material_filename": "经验帖.pdf",
                "source_text": "考场上预留十五分钟检查，卡题时及时跳过。",
            },
        ]

        pdf_bytes = build_knowledge_outline_pdf(
            points,
            subject="408综合",
            source_count=2,
            generated_at=datetime(2026, 7, 14, 10, 30),
        )

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        self.assertGreaterEqual(len(reader.pages), 2)
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("408综合", extracted)
        self.assertIn("页式虚拟存储器基本原理", extracted)
        self.assertIn("备考经验", extracted)
        self.assertIn("背诵状态", extracted)
        self.assertNotIn("扫码咨询", extracted)
        self.assertNotIn("候选知识点1", extracted)

    def test_rejects_empty_outline(self):
        with self.assertRaisesRegex(ValueError, "没有可导出"):
            build_knowledge_outline_pdf([], subject="408综合")


if __name__ == "__main__":
    unittest.main()
