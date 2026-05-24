"""
考研RAG智能助手 - 完整恢复版
运行: streamlit run app.py
"""
import streamlit as st
import os
import json
import sqlite3
import math
import base64
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.error

# ==================== 配置 ====================
st.set_page_config(page_title="考研RAG智能助手", page_icon="📚", layout="wide", initial_sidebar_state="expanded")

# API配置
API_KEY = os.environ.get("AI_API_KEY", "sk-Sav7yLJqAZ6FxCiXy2kCOOSelXOiDceY1YzhtCNsJArcu1dx")
API_BASE = os.environ.get("AI_API_BASE", "https://aiberm.com/v1")
MODEL_NAME = os.environ.get("AI_MODEL", "gpt-4o")

DATA_DIR = Path("data/corpus")
DEMO_DATA_DIR = Path("data/corpus_demo")
MEMORY_DB = "data/memory.db"
EXPERIENCE_FILE = "agent_experience.md"

# ==================== CSS样式 ====================
st.markdown("""
<style>
    .main-title { background: linear-gradient(135deg, #d77757 0%, #e8926a 100%); padding: 1.5rem; border-radius: 1rem; color: white; text-align: center; margin-bottom: 1rem; }
    .main-title h1 { font-size: 2rem; font-weight: 700; margin: 0; }
    .main-title p { opacity: 0.9; margin-top: 0.5rem; }

    .card { background: white; border-radius: 10px; padding: 15px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); margin-bottom: 15px; }

    .memory-card { padding: 12px; margin: 8px 0; background: #f8f9fa; border-radius: 10px; border-left: 4px solid #d77757; cursor: pointer; transition: all 0.3s; }
    .memory-card:hover { transform: translateX(5px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); background: #fff; }

    .answer-box { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); min-height: 150px; }

    .source-item { padding: 10px; margin: 8px 0; background: #f8f9fa; border-left: 4px solid #d77757; border-radius: 5px; }

    .metric-box { text-align: center; padding: 15px; background: #f8f9fa; border-radius: 10px; }
    .metric-value { font-size: 28px; font-weight: bold; color: #d77757; }
    .metric-label { font-size: 12px; color: #666; margin-top: 5px; }

    .stat-item { text-align: center; padding: 10px; background: #f8f9fa; border-radius: 8px; }
    .stat-value { font-size: 24px; font-weight: bold; color: #d77757; }
    .stat-label { font-size: 12px; color: #666; }

    .upload-area { border: 2px dashed #ddd; padding: 20px; text-align: center; border-radius: 8px; margin-bottom: 15px; cursor: pointer; }
    .upload-area:hover { border-color: #d77757; }

    .doc-item { padding: 8px; margin: 5px 0; background: #f8f9fa; border-radius: 5px; font-size: 13px; }

    .learning-card { padding: 8px; margin: 3px 0; background: #fff8f0; border-radius: 6px; border-left: 3px solid #e8926a; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .mastered-card { padding: 8px; margin: 3px 0; background: #f0faf4; border-radius: 6px; border-left: 3px solid #7cb896; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    .qa-card { background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(215,119,87,0.06); margin-bottom: 16px; }
    .ref-tag { display: inline-block; background: #fef5f0; color: #8b5a3c; padding: 3px 10px; border-radius: 20px; margin: 2px 4px; font-size: 12px; border: 1px solid #f0ddd0; }
    .user-pill { display: inline-block; background: #d77757; color: #fff; padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ==================== 核心功能 ====================

def read_file(p):
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except:
        try:
            return p.read_text(encoding="gbk", errors="ignore")
        except:
            return ""

@st.cache_data
def load_corpus():
    docs = []
    if DATA_DIR.exists():
        for f in sorted(DATA_DIR.iterdir()):
            if f.is_file() and f.suffix.lower() in [".txt", ".md"]:
                t = read_file(f)
                if t and len(t) > 50:
                    docs.append({"id": f.name, "text": t})
    return docs

@st.cache_data
def load_demo_corpus():
    docs = []
    if DEMO_DATA_DIR.exists():
        for f in sorted(DEMO_DATA_DIR.iterdir()):
            if f.is_file() and f.suffix.lower() in [".txt", ".md"]:
                t = read_file(f)
                if t and len(t) > 50:
                    docs.append({"id": f.name, "text": t})
    return docs

def save_document(filename, content):
    file_path = DATA_DIR / filename
    try:
        file_path.write_text(content, encoding="utf-8")
        return True
    except:
        return False

def search_corpus(query, corpus, top_k=3):
    if not corpus or not query:
        return []
    query_lower = query.lower()
    results = []
    for doc in corpus:
        text = doc["text"].lower()
        score = sum(text.count(w) for w in query_lower.split() if w)
        if score > 0:
            results.append({"id": doc["id"], "score": score, "text": doc["text"][:500]})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

def get_knowledge_text(kid, corpus):
    for doc in corpus:
        if kid in doc["id"]:
            return doc["text"]
    return ""

import hashlib

# ==================== 用户管理 ====================

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def register_user(username, password):
    """注册新用户，返回 user_id 或 None"""
    conn = sqlite3.connect(MEMORY_DB)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    if c.fetchone():
        conn.close()
        return None  # 用户名已存在
    pw_hash = hash_password(password)
    c.execute("INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
              (username, pw_hash, username))
    conn.commit()
    user_id = c.lastrowid
    conn.close()
    return user_id

def login_user(username, password):
    """登录，返回 user_id 或 None"""
    conn = sqlite3.connect(MEMORY_DB)
    c = conn.cursor()
    pw_hash = hash_password(password)
    c.execute("SELECT id FROM users WHERE username=? AND password_hash=?", (username, pw_hash))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_experience_file():
    uid = st.session_state.get("user_id", 1)
    return Path(f"agent_experience_{uid}.md")

def load_agent_experience():
    exp_file = get_experience_file()
    if exp_file.exists():
        try:
            return exp_file.read_text(encoding="utf-8").strip()
        except:
            return ""
    return ""

def save_agent_experience(text):
    exp_file = get_experience_file()
    try:
        exp_file.write_text(text, encoding="utf-8")
        return True
    except:
        return False

def get_recent_experiences(count=5):
    exp = load_agent_experience()
    if not exp:
        return []
    parts = exp.split("---")
    return parts[-count:] if len(parts) >= count else parts

# ==================== 记忆系统 ====================

def init_memory_db():
    Path(MEMORY_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB)
    c = conn.cursor()

    # 确保 users 表
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, display_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    try: c.execute("SELECT password_hash FROM users LIMIT 1")
    except: c.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    try: c.execute("SELECT display_name FROM users LIMIT 1")
    except: c.execute("ALTER TABLE users ADD COLUMN display_name TEXT")

    c.execute("""CREATE TABLE IF NOT EXISTS knowledge_mastery (
        id INTEGER PRIMARY KEY, knowledge_id TEXT, user_id INTEGER DEFAULT 1,
        mastery_level REAL DEFAULT 0, status TEXT DEFAULT '陌生',
        times_correct INTEGER DEFAULT 0, times_wrong INTEGER DEFAULT 0,
        stability REAL DEFAULT 1.0, last_review TIMESTAMP,
        error_type TEXT DEFAULT '', wrong_reason TEXT DEFAULT '')""")

    try:
        c.execute("SELECT error_type FROM knowledge_mastery LIMIT 1")
    except:
        c.execute("ALTER TABLE knowledge_mastery ADD COLUMN error_type TEXT DEFAULT ''")

    try:
        c.execute("SELECT wrong_reason FROM knowledge_mastery LIMIT 1")
    except:
        c.execute("ALTER TABLE knowledge_mastery ADD COLUMN wrong_reason TEXT DEFAULT ''")

    try:
        c.execute("SELECT stability FROM knowledge_mastery LIMIT 1")
    except:
        c.execute("ALTER TABLE knowledge_mastery ADD COLUMN stability REAL DEFAULT 1.0")

    c.execute("""CREATE TABLE IF NOT EXISTS user_performance (
        id INTEGER PRIMARY KEY, user_id INTEGER DEFAULT 1,
        knowledge_id TEXT, is_correct INTEGER, error_type TEXT,
        mastery_score REAL, created_at TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS review_challenges (
        id INTEGER PRIMARY KEY, knowledge_id TEXT, user_id INTEGER DEFAULT 1,
        challenge_type TEXT, completed INTEGER DEFAULT 0,
        created_at TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS visit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        username TEXT, action TEXT, detail TEXT)""")

    conn.commit()
    conn.close()

def log_visit(action, detail=""):
    try:
        conn = sqlite3.connect(MEMORY_DB)
        c = conn.cursor()
        username = st.session_state.get("username", "anon")
        c.execute("INSERT INTO visit_log (username, action, detail) VALUES (?, ?, ?)",
                  (username, action, detail[:200]))
        conn.commit()
        conn.close()
    except:
        pass

def calc_recall(stability, days):
    if days <= 0:
        return 1.0
    return max(0, min(1, math.exp(-days / (stability + 0.1))))

def needs_review(recall_prob, threshold=0.3):
    return recall_prob < threshold

def update_memory(kid, is_mastered, error_type="", mastery_score=0):
    init_memory_db()
    uid = st.session_state.get("user_id", 1)
    conn = sqlite3.connect(MEMORY_DB)
    c = conn.cursor()
    c.execute("SELECT times_correct, times_wrong, stability FROM knowledge_mastery WHERE knowledge_id=? AND user_id=?", (kid, uid))
    row = c.fetchone()

    if row:
        old_correct, old_wrong, old_stability = row
        times_correct = old_correct + (1 if is_mastered else 0)
        times_wrong = old_wrong + (0 if is_mastered else 1)
        stability = old_stability * 1.1 if is_mastered else max(0.5, old_stability * 0.9)
    else:
        times_correct = 1 if is_mastered else 0
        times_wrong = 0 if is_mastered else 1
        stability = 1.0

    status = "掌握" if is_mastered else "学习中"

    c.execute("""INSERT OR REPLACE INTO knowledge_mastery
        (knowledge_id, user_id, status, times_correct, times_wrong, stability, last_review, error_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (kid, uid, status, times_correct, times_wrong, stability, datetime.now(), error_type))

    c.execute("""INSERT INTO user_performance
        (user_id, knowledge_id, is_correct, error_type, mastery_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (uid, kid, 1 if is_mastered else 0, error_type, mastery_score, datetime.now()))

    conn.commit()
    conn.close()

def get_memory_stats():
    init_memory_db()
    uid = st.session_state.get("user_id", 1)
    conn = sqlite3.connect(MEMORY_DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM knowledge_mastery WHERE status='掌握' AND user_id=?", (uid,))
    mastered = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM knowledge_mastery WHERE status='学习中' AND user_id=?", (uid,))
    learning = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM knowledge_mastery WHERE user_id=?", (uid,))
    total = c.fetchone()[0] or 0
    conn.close()
    return {"mastered": mastered, "learning": learning, "total": total}

def get_weak_points():
    init_memory_db()
    uid = st.session_state.get("user_id", 1)
    conn = sqlite3.connect(MEMORY_DB)
    c = conn.cursor()
    c.execute("""SELECT knowledge_id, times_wrong, times_correct, status, stability, error_type
        FROM knowledge_mastery WHERE times_wrong > 0 AND user_id=? ORDER BY times_wrong DESC LIMIT 10""", (uid,))
    results = c.fetchall()
    conn.close()
    weak_points = []
    for r in results:
        recall = calc_recall(r[4] or 1.0, 3)
        weak_points.append({"knowledge_id": r[0], "times_wrong": r[1], "times_correct": r[2], "status": r[3] or "学习中", "recall": recall, "error_type": r[5] or "理解不清"})
    return weak_points

def get_review_candidates():
    init_memory_db()
    uid = st.session_state.get("user_id", 1)
    conn = sqlite3.connect(MEMORY_DB)
    c = conn.cursor()
    c.execute("""SELECT knowledge_id, mastery_level, status, stability, last_review
        FROM knowledge_mastery WHERE user_id=? ORDER BY mastery_level ASC""", (uid,))
    results = c.fetchall()
    conn.close()

    candidates = []
    for r in results:
        kid, mastery, status, stability, last_review = r
        if last_review:
            days = (datetime.now() - datetime.fromisoformat(str(last_review))).days
        else:
            days = 30

        recall = calc_recall(stability or 1.0, days)

        if needs_review(recall) or status != "掌握":
            candidates.append({
                "knowledge_id": kid,
                "mastery_level": mastery or 0,
                "status": status or "陌生",
                "recall": recall,
                "urgency": 1 - recall
            })

    candidates.sort(key=lambda x: x["urgency"], reverse=True)
    return candidates[:10]

def create_review_challenge(kid):
    init_memory_db()
    conn = sqlite3.connect(MEMORY_DB)
    c = conn.cursor()
    c.execute("""INSERT INTO review_challenges (knowledge_id, challenge_type, created_at)
        VALUES (?, '自动复习', ?)""", (kid, datetime.now()))
    conn.commit()
    conn.close()

# ==================== 复习题目生成 ====================

def render_qa_cards(raw_text):
    """渲染练习题：按 --- 拆题，每道题一个 expander"""
    if not raw_text:
        return
    blocks = raw_text.split("---")
    cols = st.columns(2)
    qi = 0
    for block in blocks:
        block = block.strip()
        if not block or "Q:" not in block:
            continue
        # 提取题目首行
        lines = block.split("\n")
        title = lines[0].strip()[:40] if lines else f"第{qi+1}题"
        with cols[qi % 2]:
            with st.expander(title, expanded=False):
                st.markdown(block)
        qi += 1
        if qi >= 2:
            break

def generate_review_questions(knowledge_points):
    if not knowledge_points:
        return {"error": "无复习知识点", "questions": ""}

    try:
        kb_list = "\n".join([f"{i+1}. {kp['knowledge_id']}" for i, kp in enumerate(knowledge_points[:3])])

        system_prompt = """你是考研数学辅导专家。根据知识点出3道复习练习题。

要求：
1. 题目覆盖给出的知识点
2. 包含选择题或计算题
3. 所有数学公式使用 LaTeX：$...$ 行内，$$...$$ 独立
4. 题目后附正确答案和解题步骤"""

        user_prompt = f"""请为以下知识点生成复习题目：

{kb_list}

请按以下格式输出：

## 题目1：[知识点1相关]
A. 选项1
B. 选项2
C. 选项3
D. 选项4

答案：[正确答案]

解答：[详细步骤]

## 题目2：[知识点2相关]
...

## 题目3：[知识点3相关]
..."""

        request_data = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 2000,
            "temperature": 0.7
        }

        req = urllib.request.Request(
            API_BASE + "/chat/completions",
            data=json.dumps(request_data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}'
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {
                "success": True,
                "questions": result['choices'][0]['message']['content'],
                "knowledge_points": [kp['knowledge_id'] for kp in knowledge_points[:3]]
            }

    except Exception as e:
        print(f"生成题目失败: {e}")
        return generate_local_questions(knowledge_points)

def generate_local_questions(knowledge_points):
    if not knowledge_points:
        return {"error": "无复习知识点", "questions": ""}

    questions = "## 🎯 今日复习挑战\n\n"

    for i, kp in enumerate(knowledge_points[:3], 1):
        kid = kp.get("knowledge_id", f"知识点{i}")
        level = kp.get("mastery_level", 50)
        status = kp.get("status", "学习中")

        if level < 30:
            difficulty = "基础题"
            question = f"请回忆 {kid} 的定义和基本概念"
        elif level < 60:
            difficulty = "中等题"
            question = f"请解释 {kid} 的原理，并举例说明"
        else:
            difficulty = "提高题"
            question = f"运用 {kid} 解决以下问题：..."

        questions += f"""### 题目 {i}（{difficulty}）
📚 知识点：{kid}
📊 掌握程度：{level}% | 状态：{status}

❓ {question}

<details>
<summary>点击查看答案</summary>

答案：{kid} 的核心要点如下...
</details>

---
"""

    return {
        "success": True,
        "questions": questions,
        "knowledge_points": [kp['knowledge_id'] for kp in knowledge_points[:3]]
    }

# ==================== 多Agent管线 ====================

def extract_json(text):
    text = text.strip()
    if "```json" in text:
        text = text.split("```json",1)[1].split("```",1)[0].strip()
    elif text.startswith("```"):
        text = text.split("```",2)[1].strip()
    return text

ROUTER_PROMPT = """判断以下考研问题的学科类型，只输出JSON：
- english: 英语作文、翻译、阅读、完形、词汇、语法
- politics: 政治理论、马原、毛中特、近代史、思修、时政
- math: 数学计算、求导、积分、证明、公式、矩阵、概率

输出 {"type":"english"|"politics"|"math"}"""

ENGLISH_PROMPT = """你是考研英语辅导专家。专精：作文模板、长难句分析、翻译技巧、阅读策略。
回答简洁实用，给出可操作的建议。不编造具体分数线或统计数据。"""

POLITICS_PROMPT = """你是考研政治辅导专家。专精：马原原理、毛中特体系、近代史脉络、思修要点、时政热点。
回答结构清晰，先给出核心结论再展开。不编造具体分值或命题预测。"""

def classify_query(query):
    """Router: 判断问题属于 english/politics/math"""
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": query}
        ],
        "max_tokens": 30, "temperature": 0
    }
    req = urllib.request.Request(API_BASE + "/chat/completions",
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = json.loads(resp.read().decode('utf-8'))['choices'][0]['message']['content']
            return json.loads(extract_json(raw)).get("type", "math")
    except:
        return "math"

def parse_multi_output(raw_text):
    """解析 LLM 一次输出的 [ANSWER]/[KNOWLEDGE]/[QUIZ]"""
    def extract(begin, end):
        if begin in raw_text and end in raw_text:
            return raw_text.split(begin, 1)[1].split(end, 1)[0].strip()
        return ""
    return {
        "answer": extract("[ANSWER]", "[KNOWLEDGE]") or extract("[ANSWER]", "[QUIZ]") or raw_text[:1500],
        "knowledge": [k.strip() for k in extract("[KNOWLEDGE]", "[QUIZ]").split(",") if k.strip()],
        "quiz": extract("[QUIZ]", "[END]")
    }

def run_pipeline(query, results, model_name, img_data=None):
    """多Agent管线: Math 合并一次调用 / English&Politics 原逻辑"""
    pipeline_log = []
    
    # ① Router 分类
    qtype = classify_query(query)
    pipeline_log.append(f"🧭 Router → {qtype}")
    
    # ② English / Politics: 保持原快速路径
    if qtype in ("english", "politics"):
        system_override = ENGLISH_PROMPT if qtype == "english" else POLITICS_PROMPT
        skill_prompt = build_system_prompt_with_skills(st.session_state.get("active_skills", []))
        system_prompt = system_override
        system_prompt = (skill_prompt + "\n\n---\n\n" + system_prompt) if skill_prompt else system_prompt
        user_prompt = f"【问题】\n{query}\n\n请直接回答："
        data = {"model": model_name, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "max_tokens": 1200, "temperature": 0.3}
        req = urllib.request.Request(API_BASE + "/chat/completions", data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                answer = json.loads(resp.read().decode('utf-8'))['choices'][0]['message']['content']
        except:
            answer = query
        return {"answer": answer, "knowledge": [], "quiz": "", "qtype": qtype, "pipeline_log": pipeline_log}
    
    # ③ Math: 一次调用出全部
    skill_prompt = build_system_prompt_with_skills(st.session_state.get("active_skills", []))
    context = "\n\n".join([f"【{d['id']}】\n{d['text'][:800]}" for d in results[:3]]) if results else ""

    system_prompt = f"""你是考研数学辅导专家。一次性完成以下任务，严格按标签输出：

[ANSWER]
根据参考资料回答问题。{"按 Skill 要求格式输出。" if skill_prompt else "用LaTeX写公式，回答简洁准确。"}

[KNOWLEDGE]
输出问题涉及的知识点文档名（多个用逗号分隔，如 004-导数的定义与几何意义.md, 012-定积分的定义与性质.md）。直接写文件名。

[QUIZ]
生成2道选择题，每题用 --- 分隔，格式：
Q: 题目
A) 选项
B) 选项
C) 选项
D) 选项
ANSWER: 正确选项字母
EXPLAIN: 详细解析（含步骤和公式）
---
[END]

{skill_prompt if skill_prompt else ""}

参考资料：
{context}"""

    user_content = [{"type": "text", "text": f"问题：{query}"}] if not img_data else [
        {"type": "text", "text": f"问题：{query}"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_data}"}}
    ]
    data = {"model": model_name, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}], "max_tokens": 2500, "temperature": 0.3}
    req = urllib.request.Request(API_BASE + "/chat/completions", data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = json.loads(resp.read().decode('utf-8'))['choices'][0]['message']['content']
            result = parse_multi_output(raw)
            result["qtype"] = qtype
            result["pipeline_log"] = pipeline_log
            return result
    except:
        return {"answer": f"【问题】\n{query}\n\n请直接回答：", "knowledge": [], "quiz": "", "qtype": qtype, "pipeline_log": pipeline_log}

# ==================== LLM调用 ====================

def call_llm(query, context_docs, model_name=None):
    """调用LLM API - 支持RAG和纯LLM两种模式"""
    if model_name is None:
        model_name = MODEL_NAME

    try:
        experience = load_agent_experience()

        # 模式判断：有检索结果用RAG，无检索结果用纯LLM
        has_context = context_docs and len(context_docs) > 0

        # 加载动态经验库
        experience = load_agent_experience()

        if has_context:
            # RAG模式：结合知识库
            context = "\n\n".join([f"【{d['id']}】\n{d['text'][:800]}" for d in context_docs[:3]])

            # 不可变约束 + 动态经验库
            static_rules = """## 铁律：不可变约束 (绝对不可修改)
1. **信息溯源**：回答必须严格基于提供的参考资料。资料中信息不足时，请如实说明。
2. **禁止编造数据**：不编造具体数字、百分比、机构名、人名，除非资料中明确出现。
3. **禁止无关延伸**：不补充资料未提及的内容。

## 动态经验与偏好库 (自学习记录)
"""
            system_prompt = static_rules + (experience if experience else "暂无追加规则")
            system_prompt += "\n\n请直接回答，不要多余的开场或结尾闲聊。"

            user_prompt = f"""【用户问题】
{query}

【参考资料】
{context}

请根据以上参考资料回答："""
        else:
            # 纯LLM模式
            static_rules = """## 铁律：不可变约束
1. 如果无法确定答案，请诚实说明。
2. 不编造具体数字、研究来源、统计报告。
3. 回答简洁、有据可查。

## 动态经验与偏好库
"""
            system_prompt = static_rules + (experience if experience else "暂无追加规则")
            system_prompt += "\n\n请直接回答，不要多余闲聊。"

            user_prompt = f"""【用户问题】
{query}

请回答："""

        # 注入激活的 Skill
        skill_prompt = build_system_prompt_with_skills(st.session_state.get("active_skills", []))
        if skill_prompt:
            system_prompt = skill_prompt + "\n\n---\n\n" + system_prompt

        # 不同的max_tokens
        max_tokens = 800 if has_context else 1200

        request_data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3
        }

        req = urllib.request.Request(
            API_BASE + "/chat/completions",
            data=json.dumps(request_data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}'
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content']

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ""
        st.error(f"API错误 {e.code}: {error_body}")
        return fallback_answer(query, context_docs)
    except Exception as e:
        st.error(f"API调用失败: {e}")
        return fallback_answer(query, context_docs)

def fallback_answer(query, docs):
    if not docs:
        return "未找到相关资料"
    best = docs[0]
    text = best["text"]
    return f"""📚 根据检索到的资料回答【{query}】：

{text[:600]}...

---
📖 参考来源：{best['id']} (相关性: {best['score']})"""

# ==================== 幻觉检测 ====================

MATH_EVAL_PROMPT = """你是考研数学事实核查员。评估回答是否在上下文中存在有害幻觉。

## 三类声明
1. **严格支持**: 回答直接来源于Context
2. **专业常识拓展**: Context未提及，但属于大学数学公认定理/定义（如子数列收敛性、零点定理、极限四则运算）- 宽容通过
3. **有害幻觉**: 捏造考情/分值/频率/历史/应用领域

## 输出JSON
{"is_hallucinating": true/false, "hallucinated_claims": [...], "common_sense_claims": [...]}"""

def evaluate_hallucination(user_query: str, context: str, agent_response: str, model_name=None):
    """调用LLM评估回答是否存在有害幻觉"""
    if model_name is None:
        model_name = MODEL_NAME
    try:
        prompt = f"""[User Query]: {user_query}

[Context]:
{context}

[Agent Response]:
{agent_response}"""

        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": MATH_EVAL_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 600,
            "temperature": 0.1
        }
        req = urllib.request.Request(
            API_BASE + "/chat/completions",
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = json.loads(resp.read().decode('utf-8'))['choices'][0]['message']['content']
            return json.loads(content)
    except Exception as e:
        return {"is_hallucinating": False, "error": str(e), "hallucinated_claims": [], "common_sense_claims": []}

# ==================== Agent自我反思 ====================

def trigger_self_learning(rule_text: str) -> str:
    """将新规则追加到动态经验库，并返回确认信息"""
    existing = load_agent_experience()
    # 找到最后一条编号
    lines = existing.split("\n")
    last_num = 1
    for line in lines:
        if line.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            try:
                num = int(line.split(".")[0])
                last_num = max(last_num, num)
            except:
                pass

    next_num = last_num + 1
    today = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"{next_num}. [{today}] {rule_text}"

    # 追加到"结束记录"之前
    if "--- 结束记录 ---" in existing:
        updated = existing.replace("--- 结束记录 ---", f"{new_entry}\n--- 结束记录 ---")
    else:
        updated = f"{existing}\n{new_entry}\n--- 结束记录 ---"

    save_agent_experience(updated)
    return f"\n🔄 **自学习已触发** — **已将以下规则追加至经验库**：{rule_text}\n**当前状态**：底层逻辑未受影响，增量规则已生效。"

def agent_reflect(question, answer, feedback):
    try:
        prompt = f"""你是一个Agent，正在进行自我反思。用户对你的回答提供了反馈：

问题: {question}
你的回答: {answer}
用户反馈: {feedback}

请从反馈中提炼出1条可以在后续任务中复用的具体规则（一句话即可，不要编号）。

直接输出规则文字，不要多余内容。"""

        request_data = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.3
        }

        req = urllib.request.Request(
            API_BASE + "/chat/completions",
            data=json.dumps(request_data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}'
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode('utf-8'))
            rule = result['choices'][0]['message']['content'].strip()

            # 追加到动态经验库
            confirm = trigger_self_learning(rule)
            return {"success": True, "reflection": rule, "confirm": confirm}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==================== 会话状态 ====================
if "thinking_log" not in st.session_state:
    st.session_state.thinking_log = []
if "current_knowledge_ids" not in st.session_state:
    st.session_state.current_knowledge_ids = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "gpt-4o"

def add_thinking(msg):
    """添加思考日志"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.thinking_log.append(f"[{timestamp}] {msg}")

# ==================== Skill 技能系统 ====================

SKILLS_DIR = Path("skills")

def load_all_skills():
    """自动扫描 skills/ 目录，加载所有 SKILL.md"""
    skills = {}
    if not SKILLS_DIR.exists():
        return skills
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        try:
            content = skill_file.read_text(encoding="utf-8")
            meta, body = parse_skill_frontmatter(content)
            meta["_dir"] = str(skill_dir)
            meta["_body"] = body.strip()
            skills[meta.get("name", skill_dir.name)] = meta
        except:
            pass
    return skills

def parse_skill_frontmatter(content):
    """解析 YAML frontmatter，返回 (meta_dict, body)"""
    lines = content.strip().split("\n")
    meta = {}
    body_start = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines):
            line = lines[i]
            if line.strip() == "---":
                body_start = i + 1
                break
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val.startswith("[") and val.endswith("]"):
                    val = [x.strip().strip('"') for x in val[1:-1].split(",")]
                meta[key] = val
            i += 1
    body = "\n".join(lines[body_start:]).strip() if body_start > 0 else content.strip()
    return meta, body

def build_system_prompt_with_skills(active_skills):
    """将激活的 Skill prompts 注入 system_prompt"""
    skill_prompts = []
    for name in active_skills:
        skills = load_all_skills()
        if name in skills:
            body = skills[name].get("_body", "")
            if body:
                skill_prompts.append(f"## Skill: {skills[name].get('description', name)}\n\n{body}")
    return "\n\n---\n\n".join(skill_prompts) if skill_prompts else ""

# ==================== 智能知识点匹配 ====================

def smart_match_knowledge(query):
    """模糊问题 → LLM提取概念 → 匹配corpus（文件名优先 + 内容回退）"""
    from difflib import get_close_matches
    # ① 用 LLM 从问题中提取 1-3 个核心数学概念
    try:
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "从以下考研数学问题中提取1-3个核心知识点名称（每行一个，不要编号）。"},
                {"role": "user", "content": query}
            ],
            "max_tokens": 80, "temperature": 0
        }
        req = urllib.request.Request(API_BASE + "/chat/completions",
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'},
            method='POST')
        with urllib.request.urlopen(req, timeout=8) as resp:
            concepts = json.loads(resp.read().decode('utf-8'))['choices'][0]['message']['content']
            concepts = [c.strip().strip("-•*") for c in concepts.split("\n") if c.strip()]
    except:
        return []
    
    # 概念归一化：去掉常见后缀提高匹配率
    def normalize(c):
        for suffix in ["的定义", "的计算", "的性质", "的概念", "的方法", "的应用",
                       "及其", "与", "的", "法", "性", "论"]:
            if suffix in c:
                c = c.split(suffix)[0]
        return c.strip()
    
    corpus = load_corpus()
    doc_names = [d["id"] for d in corpus]
    matched = []
    
    for concept_raw in concepts:
        # 先精确匹配文档名
        concept = normalize(concept_raw)
        close = get_close_matches(concept, doc_names, n=2, cutoff=0.1)
        if close:
            matched.extend(close)
            continue
        
        # 回退：搜索文档内容中的关键词
        for doc in corpus:
            if concept in doc["text"][:500]:
                matched.append(doc["id"])
                break
    
    return list(dict.fromkeys(matched))  # 去重保序

# ==================== UI界面 ====================

# 登录状态
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# 确保数据库表存在（登录前就必须建好）
init_memory_db()

if not st.session_state.logged_in:
    # ─── 登录/注册页 ───
    if not API_KEY:
        st.warning("⚠️ 未设置 API Key。请设置环境变量 `AI_API_KEY` 后重启。")
        st.code("export AI_API_KEY='sk-xxx'  # Linux/Mac\nset AI_API_KEY=sk-xxx  # Windows", language="bash")
        st.stop()
    st.markdown("""
    <div class="main-title">
        <h1>📚 考研RAG智能助手</h1>
        <p>多用户知识问答系统</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["登录", "注册"])
    
    with tab_login:
        with st.form("login_form"):
            username = st.text_input("用户名")
            password = st.text_input("密码", type="password")
            submitted = st.form_submit_button("登录", use_container_width=True, type="primary")
            if submitted and username and password:
                uid = login_user(username, password)
                if uid:
                    st.session_state.logged_in = True
                    st.session_state.user_id = uid
                    st.session_state.username = username
                    st.success("登录成功！")
                    st.rerun()
                else:
                    st.error("用户名或密码错误")

    with tab_register:
        with st.form("register_form"):
            new_user = st.text_input("新用户名")
            new_pass = st.text_input("新密码", type="password")
            new_pass2 = st.text_input("确认密码", type="password")
            reg_submitted = st.form_submit_button("注册", use_container_width=True)
            if reg_submitted and new_user and new_pass:
                if new_pass != new_pass2:
                    st.error("两次密码不一致")
                elif len(new_pass) < 3:
                    st.error("密码至少3位")
                else:
                    uid = register_user(new_user, new_pass)
                    if uid:
                        st.session_state.logged_in = True
                        st.session_state.user_id = uid
                        st.session_state.username = new_user
                        st.success(f"注册成功！欢迎 {new_user}")
                        st.rerun()
                    else:
                        st.error("用户名已存在")

    st.stop()  # 未登录时不继续渲染

# 初始化（已登录）
corpus = load_corpus()
experience = load_agent_experience()
stats = get_memory_stats()
add_thinking(f"用户 {st.session_state.get('username','?')} 登录")

# 顶部标题
st.markdown("""
<div class="main-title">
    <h1>📚 考研RAG智能助手</h1>
    <p>基于本地知识库的智能问答系统 | 支持自学习、遗忘曲线、经验积累</p>
</div>
""", unsafe_allow_html=True)

# 使用columns实现三栏布局
left_col, mid_col = st.columns([1, 2])

# ==================== 左侧面板 ====================
with left_col:
    st.markdown("### 👤 当前用户")
    st.markdown(f"**{st.session_state.get('username','?')}**")
    if st.button("🚪 退出登录", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.rerun()

    st.markdown("---")

    # 模型选择
    model_options = [
        "gpt-4o (最强)",
        "gpt-4o-mini (最便宜)",
    ]

    # 映射到实际模型名
    model_map = {
        "gpt-4o (最强)": "gpt-4o",
        "gpt-4o-mini (最便宜)": "gpt-4o-mini",
    }

    selected_idx = st.selectbox(
        "选择模型",
        range(len(model_options)),
        index=0,
        format_func=lambda x: model_options[x]
    )
    st.session_state.selected_model = model_map[model_options[selected_idx]]

    # 价格说明
    st.markdown("""
    <div style="font-size:12px;color:#666;margin-top:5px;">
        💰 价格: gpt-4o-mini < gpt-4o < claude-3-haiku < claude-3-5-sonnet < gpt-4o
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="current-model">
        ✅ 当前模型: {st.session_state.selected_model}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="model-info">
        <span>速度: 快</span>
        <span>质量: 最优</span>
        <span>上下文: 200K</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Skill 技能切换
    st.markdown("### 🎯 回答方式")
    all_skills = load_all_skills()
    if "active_skills" not in st.session_state:
        st.session_state.active_skills = list(all_skills.keys())
    
    if all_skills:
        for skill_name, skill_meta in all_skills.items():
            is_active = skill_name in st.session_state.active_skills
            if st.toggle(f"**{skill_meta.get('label', skill_name)}**  ", value=is_active, key=f"skill_{skill_name}", help=skill_meta.get("description", "")):
                if skill_name not in st.session_state.active_skills:
                    st.session_state.active_skills.append(skill_name)
            else:
                if skill_name in st.session_state.active_skills:
                    st.session_state.active_skills.remove(skill_name)
        st.caption(f"已激活: {len(st.session_state.active_skills)}/{len(all_skills)}")
    else:
        st.caption("`skills/` 目录下暂无 Skill")
    st.markdown("---")

    # 系统状态
    st.markdown("### ⚙️ 系统状态")
    st.markdown(f"📁 {len(corpus)} 个文档 · 🧠 {stats['total']} 知识点")
    col_r1, col_r2 = st.columns([1, 1])
    with col_r1:
        if st.button("🔄 刷新知识库", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col_r2:
        if st.button("🔌 重连API", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

# ==================== 中间面板 ====================
with mid_col:
    with st.expander("💡 新手指南", expanded=False):
        st.markdown("本系统内置 **110 个考研数学核心知识点**，覆盖高等数学、线性代数、概率论三大模块，内容对齐 2025 年考试大纲。")
        st.markdown("**🧭 智能路由** — 数学问题检索知识库，英语/政治问题由 AI 直接回答。")
        st.markdown("**🎯 回答方式** — 侧边栏可选择 AI 的输出风格：分步解题、概念讲解、错题分析，以及纯要点、问答、纯公式等格式。")
        st.markdown("**📊 记忆系统** — 自动追踪每个知识点的掌握程度，根据遗忘曲线推送复习内容。")

    st.markdown("### 💬 智能问答")
    query = st.text_input("🔍 输入你的考研问题", placeholder="例如：什么是导数？", key="query_input")

    if query:
        with st.spinner("🤖 AI 思考中..."):
            add_thinking(f"查询: {query[:30]}...")
            results = search_corpus(query, corpus, top_k=3)
            output = run_pipeline(query, results, st.session_state.selected_model)

        # AI回答
        st.markdown('<div class="qa-card">', unsafe_allow_html=True)
        st.markdown("### 💡 回答")
        st.markdown(output.get("answer", ""))
        st.markdown('</div>', unsafe_allow_html=True)
        add_thinking(f"回答完成")
        log_visit("提问", f"{query[:50]}")

        # 知识点归纳（从 LLM 输出中直接提取）
        if output.get("knowledge"):
            for kid in output["knowledge"]:
                update_memory(kid, False, error_type="自动归纳")
            add_thinking(f"自动归纳知识点: {output['knowledge']}")
            st.session_state._matched_knowledge = output["knowledge"]

        # 参考来源
        if results:
            st.markdown("### 📋 使用的参考资料")
            ref_html = ""
            for r in results:
                ref_html += f"<span class='ref-tag'>📄 {r['id']} ×{r['score']}</span>"
            st.markdown(ref_html, unsafe_allow_html=True)
        else:
            st.caption("📡 回答来自LLM自身知识")

        # 练习题
        if output.get("quiz"):
            st.markdown("#### 📝 配套练习题")
            render_qa_cards(output["quiz"])

            # 评价按钮
            st.markdown("### 这个回答对你有帮助吗？")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 掌握了", use_container_width=True):
                    if results:
                        for r in results:
                            update_memory(r['id'], True)
                    else:
                        matched = smart_match_knowledge(query)
                        if matched:
                            for kid in matched:
                                update_memory(kid, True)
                            add_thinking(f"智能匹配知识点: {matched}")
                    add_thinking("用户点击: 掌握了")
                    st.success("已记录为掌握！")
            with col2:
                if st.button("📚 加入复习库", use_container_width=True):
                    matched = st.session_state.get("_matched_knowledge") or smart_match_knowledge(query)
                    if matched:
                        for kid in matched:
                            update_memory(kid, False, error_type="用户标记")
                        st.success(f"已加入复习库 ({len(matched)}个知识点)")
                    else:
                        st.info("未匹配到具体知识点")
                    log_visit("加入复习库", query[:50])
                    st.rerun()

# ==================== 底部Tab ====================
st.markdown("---")
tab1, tab2, tab3 = st.tabs(["📖 知识库", "📚 复习挑战", "🧠 记忆系统"])

with tab1:
    st.subheader(f"知识库 ({len(corpus)} 个文档)")
    search_kw = st.text_input("🔍 搜索知识库", label_visibility="collapsed", placeholder="搜索...")
    if search_kw:
        results = search_corpus(search_kw, corpus, top_k=20)
        for r in results:
            with st.expander(f"📄 {r['id']} ({r['score']})"):
                st.markdown(r['text'][:1500])
    else:
        for doc in corpus:
            with st.expander(f"📄 {doc['id']}"):
                st.markdown(doc['text'][:1500])

with tab2:
    st.subheader("🎯 复习挑战")
    candidates = get_review_candidates()
    if candidates:
        for i, c in enumerate(candidates[:5], 1):
            recall_pct = int(c['recall'] * 100)
            with st.expander(f"第{i}题: {c['knowledge_id'][:35]} (记忆: {recall_pct}%)"):
                knowledge_text = get_knowledge_text(c['knowledge_id'], corpus)
                st.markdown(knowledge_text[:1500])
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button(f"✅ 掌握", key=f"rev_m_{i}"):
                        update_memory(c['knowledge_id'], True)
                        st.rerun()
                with c2:
                    if st.button(f"❌ 再练", key=f"rev_w_{i}"):
                        update_memory(c['knowledge_id'], False, error_type="遗忘")
                        st.rerun()
                with c3:
                    gen_key = f"rev_gen_{i}"
                    if st.button(f"🎲 出题", key=gen_key):
                        gen_r = generate_review_questions([{"knowledge_id": c['knowledge_id']}])
                        if gen_r.get("success"):
                            st.markdown(f"#### 📝 {c['knowledge_id'][:30]} 练习题")
                            st.markdown(gen_r['questions'])

        if not candidates:
            st.success("🎉 暂无待复习知识点。使用问答后自动添加。")

with tab3:
    st.subheader("🧠 知识点掌握情况")
    progress = stats['mastered'] / max(stats['total'], 1)
    st.progress(progress)
    st.markdown(f"**掌握进度**: {stats['mastered']}/{stats['total']} ({progress*100:.1f}%)")

    conn = sqlite3.connect(MEMORY_DB)
    c = conn.cursor()
    c.execute("SELECT knowledge_id, status, times_correct, times_wrong, stability FROM knowledge_mastery WHERE user_id=? ORDER BY last_review DESC", (st.session_state.get("user_id", 1),))
    rows = c.fetchall()
    conn.close()

    for r in rows:
        name = r[0]
        if len(name) > 30:
            name = name[:27] + "..."
        if r[1] == "掌握":
            st.markdown(f"<div class='mastered-card'>✅ {name} | ✓{r[2]} ✗{r[3]}</div>", unsafe_allow_html=True)
        elif r[1] == "学习中":
            st.markdown(f"<div class='learning-card'>🔥 {name} | ✓{r[2]} ✗{r[3]}</div>", unsafe_allow_html=True)


with tab5:
    st.subheader("🔍 AI幻觉检测演示")
    st.caption("完整管线：检索 → Agent回答 → 幻觉检测")

    # 加载演示数据
    demo_corpus = load_demo_corpus()
    test_path = Path("test_data/hallucination_tests_demo.json")
    if test_path.exists():
        with open(test_path, 'r', encoding='utf-8') as f:
            demo_cases = json.load(f)
    else:
        demo_cases = []

    if not demo_cases:
        st.info("📦 幻觉检测演示数据未安装。下载 test_data/ 文件夹后刷新。")
        st.stop()

    # 选择一个测试用例
    case_labels = [f"{c['id']}: {(c.get('query') or c.get('user_query',''))[:35]}..." for c in demo_cases]
    selected_idx = st.selectbox("选择一个演示用例", range(len(case_labels)), format_func=lambda x: case_labels[x])
    case = demo_cases[selected_idx]

    # ─── 管线可视化 ───
    st.markdown("#### 📋 处理管线")
    pipe_cols = st.columns(4)
    with pipe_cols[0]:
        st.markdown("**① 用户提问**")
        st.markdown(f"<div style='background:#f3f4f6;padding:10px;border-radius:6px;font-size:13px;'>{case.get('query') or case.get('user_query','')}</div>", unsafe_allow_html=True)
    with pipe_cols[1]:
        st.markdown("**② 知识库检索**")
        query_text = case.get("query") or case.get("user_query", "")
        retrieved = search_corpus(query_text, demo_corpus, top_k=2)
        if retrieved:
            st.markdown(f"<div style='background:#eff6ff;padding:10px;border-radius:6px;font-size:11px;'>📄 {retrieved[0]['id']}<br>相关度: {retrieved[0]['score']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='background:#eff6ff;padding:10px;border-radius:6px;font-size:11px;'>未匹配到文档</div>", unsafe_allow_html=True)
    with pipe_cols[2]:
        st.markdown("**③ Agent回答**")
        resp_short = (case.get("response") or case.get("agent_response", ""))[:100] + "..."
        is_harmful = len(case.get("expected_hallucination_claims", [])) > 0
        border = "#ef4444" if is_harmful else "#10b981"
        st.markdown(f"<div style='background:#fef2f2 if is_harmful else #f0fdf4;padding:10px;border-radius:6px;font-size:12px;border-left:3px solid {border};'>{resp_short}</div>", unsafe_allow_html=True if is_harmful else True)
    with pipe_cols[3]:
        st.markdown("**④ 幻觉检测**")
        if is_harmful:
            st.markdown(f"<div style='background:#fef2f2;padding:10px;border-radius:6px;font-size:14px;text-align:center;'>❌ 存在幻觉</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='background:#f0fdf4;padding:10px;border-radius:6px;font-size:14px;text-align:center;'>✅ 无幻觉</div>", unsafe_allow_html=True)

    st.markdown("---")

    # ─── 详细信息 ───
    colL, colR = st.columns([3, 2])
    with colL:
        st.markdown(f"<div style='padding:12px;border-radius:8px;background:#f9fafb;'><small><b>📄 Context（检索到的资料）</b></small><br>{case.get('context','')}</div>", unsafe_allow_html=True)
    with colR:
        st.markdown(f"<div style='padding:12px;border-radius:8px;background:#fefce8;'><small><b>🤖 Agent Response</b></small><br>{case.get('response','') or case.get('agent_response','')}</div>", unsafe_allow_html=True)

    # 预期幻觉标注
    expected = case.get("expected_hallucination_claims", [])
    if expected:
        st.markdown("**🔴 标注的幻觉内容：**")
        for claim in expected:
            st.markdown(f"- <span style='color:#ef4444;'>{claim}</span>", unsafe_allow_html=True)
    else:
        st.markdown("**✅ 预期：无有害幻觉**")

    # ─── 一键运行 Critic ───
    st.markdown("---")
    if st.button("🧪 Critic 实时判定", type="primary", use_container_width=True):
        with st.spinner(f"gpt-4o Critics 正在逐条分析..."):
            result = evaluate_hallucination(
                case.get("query") or case.get("user_query", ""),
                case.get("context", ""),
                case.get("response") or case.get("agent_response", ""),
                model_name=st.session_state.get("selected_model", "gpt-4o")
            )
            is_h = result.get("is_hallucinating", False)
            detected = result.get("hallucinated_claims", [])
            common_ok = result.get("common_sense_claims") or result.get("unsupported_but_true_math_claims", [])

            if is_h:
                st.error(f"❌ 判定为存在有害幻觉")
                if detected:
                    for c in detected:
                        st.markdown(f"- 🔴 {c}")
            else:
                st.success(f"✅ 判定为无有害幻觉")

            if common_ok:
                st.info(f"⚠️ 专业常识拓展（宽容通过）:")
                for c in common_ok:
                    st.markdown(f"- {c}")

            with st.expander("📋 Critic 原始输出 (JSON)"):
                st.json({k: v for k, v in result.items() if k != "input"})

    # ─── 全部样例一览 ───
    st.markdown("---")
    st.caption("**📚 全部演示用例一览**")
    cols = st.columns(3)
    type_map = {"Clean": ("✅ 无幻觉", "#10b981", "#f0fdf4"), "Harmful": ("❌ 有害幻觉", "#ef4444", "#fef2f2"), "Boundary": ("⚠️ 专业常识", "#f59e0b", "#fffbeb")}
    for i, c in enumerate(demo_cases):
        t = c.get("type", "")
        badge, bcol, bg = type_map.get(t, ("", "#ccc", "#f9fafb"))
        with cols[i % 3]:
            st.markdown(f"<div style='background:{bg};padding:10px;border-radius:8px;border-left:3px solid {bcol};margin-bottom:8px;font-size:12px;'><b>{badge}</b><br>{c.get('id','')}: {c.get('query','')[:28]}...</div>", unsafe_allow_html=True)

    # ─── 处理逻辑说明 ───
    st.caption("""
    **处理逻辑**: 检索知识库 → Agent生成回答 → Critic逐条比对Context → 分类判定  
    • 直接来自Context → ✅ 通过  
    • 标准通用常识 → ✅ 宽容通过  
    • 捏造数据/历史/来源 → ❌ 判定为有害幻觉
    """)

with tab6:
    st.subheader("⚙️ 系统信息")
    st.markdown(f"""
    | 项目 | 数值 |
    |------|------|
    | 知识库文档 | {len(corpus)} |
    | 经验本字符 | {len(experience)} |
    | 掌握知识点 | {stats['mastered']} |
    | 学习中知识点 | {stats['learning']} |
    | 总知识点 | {stats['total']} |
    """, unsafe_allow_html=True)

    if st.button("测试API连接"):
        try:
            test_data = {"model": MODEL_NAME, "messages": [{"role": "user", "content": "你好"}], "max_tokens": 10}
            req = urllib.request.Request(API_BASE + "/chat/completions", data=json.dumps(test_data).encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                st.success(f"API正常！响应: {result['choices'][0]['message']['content'][:50]}")
        except Exception as e:
            st.error(f"API失败: {e}")

    if st.button("清除记忆数据"):
        conn = sqlite3.connect(MEMORY_DB)
        c = conn.cursor()
        c.execute("DELETE FROM knowledge_mastery")
        c.execute("DELETE FROM user_performance")
        conn.commit()
        conn.close()
        add_thinking("清除记忆数据")
        st.success("已清除")
        st.rerun()

