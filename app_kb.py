"""
专业知识库 — 独立运行入口
直接启动即可使用，无需登录。
"""
import streamlit as st
from knowledge_base import ensure_db, render_knowledge_page
from professional_knowledge.ui import inject_professional_knowledge_styles

# 页面配置
st.set_page_config(page_title="专业知识库", page_icon="📚", layout="wide")

# 与主应用共用同一套专业课工作台视觉规范。
inject_professional_knowledge_styles()

# 初始化数据库
ensure_db()

# 直接渲染知识库页面
render_knowledge_page()
