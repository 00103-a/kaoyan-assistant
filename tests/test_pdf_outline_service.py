import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from services.pdf_outline_service import (
    extract_outline_candidates,
    extract_syllabus_outline,
    looks_like_exam_syllabus,
    select_outline_page_indices,
)


class PdfOutlineServiceTests(unittest.TestCase):
    def test_page_selection_prefers_front_and_covers_end(self):
        selected = select_outline_page_indices(100, max_pages=10)
        self.assertEqual(len(selected), 10)
        self.assertEqual(selected[:6], [0, 1, 2, 3, 4, 5])
        self.assertEqual(selected[-1], 99)

    def test_outline_candidates_keep_headings_and_remove_noise(self):
        candidates = extract_outline_candidates(
            """
            目录
            第一章 计算机系统概述
            1.2 数据的表示和运算
            （一）操作系统基本概念
            扫描二维码关注微信公众号
            这是一段很长的正文说明。它不应被当作目录标题。
            """
        )
        self.assertIn("第一章 计算机系统概述", candidates)
        self.assertIn("1.2 数据的表示和运算", candidates)
        self.assertFalse(any("二维码" in item for item in candidates))
        self.assertFalse(any("正文说明" in item for item in candidates))

    def test_text_syllabus_keeps_original_hierarchy_and_all_408_sections(self):
        syllabus = """=== 第1页 ===
2026考研408考试大纲
Ⅳ考察内容
数据结构
[考察目标]
1.掌握数据结构基本概念。
一、基本概念
（一）数据结构的基本概念
1.逻辑结构
计算机组成原理
[考察目标]
一、计算机系统概述
（一）计算机系统层次结构
操作系统
一、操作系统基础
（一）操作系统的基本概念
计算机网络
一、计算机网络概述
（一）计算机网络基本概念
"""

        self.assertTrue(looks_like_exam_syllabus(syllabus, "普通资料.pdf"))
        outline, report = extract_syllabus_outline(syllabus)

        self.assertEqual(report["mode"], "syllabus_outline")
        self.assertEqual(
            report["subjects"],
            ["数据结构", "计算机组成原理", "操作系统", "计算机网络"],
        )
        self.assertIn("[一级] 一、基本概念", outline)
        self.assertIn("[二级] （一）数据结构的基本概念", outline)
        self.assertIn("[三级] 1.逻辑结构", outline)
        self.assertNotIn("掌握数据结构基本概念", outline)

    def test_filename_cannot_turn_ordinary_content_into_syllabus(self):
        ordinary_material = """第一章 学习说明
一、复习时间安排
（一）每天学习两小时
1.上午完成练习
二、资料准备
（一）准备教材
1.整理笔记
"""
        self.assertFalse(looks_like_exam_syllabus(ordinary_material, "408考试大纲.pdf"))

    def test_generic_subject_is_discovered_from_body_structure(self):
        syllabus = """2026年招生考试大纲
Ⅳ 考查内容
管理学原理
【考查目标】
掌握管理学的基本概念和方法。
一、管理与管理学
（一）管理的概念
1.管理的基本职能
二、计划职能
（一）计划的类型
1.计划编制方法
"""

        self.assertTrue(looks_like_exam_syllabus(syllabus, "随手记录.txt"))
        outline, report = extract_syllabus_outline(syllabus)

        self.assertEqual(report["subjects"], ["管理学原理"])
        self.assertIn("[科目] 管理学原理", outline)
        self.assertIn("[一级] 一、管理与管理学", outline)
        self.assertIn("[二级] （一）计划的类型", outline)


if __name__ == "__main__":
    unittest.main()
