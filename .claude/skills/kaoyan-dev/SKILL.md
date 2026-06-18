# 考研助手开发 Skill

## 触发条件

当用户提到以下任一关键词时使用本 skill：
- "改"、"修"、"加"、"优化" + 页面名称或功能名
- "app.py"、"kaoyan"、"考研"
- 任何对项目的修改请求

## 强制规则

### 1. 锁定修改范围（防漂移）
在动手改代码之前，**必须先声明**：
- 涉及哪个页面（`st.session_state.page == "xxx"`）
- 涉及哪些函数/行号
- 改动类型（修Bug / 加功能 / 改样式 / 重构）
- 不改什么（明确排除范围）

### 2. 参考稳定模式
- **卡片式布局** → 参考 `app.py` 数学问答页知识点展示（~3950行）：渐变蓝卡片 + 真 `st.button` + 展开区
- **页面模板** → 参考 Hub 或数学页：`main-title` 渐变标题 + 返回按钮 + `st.stop()`
- **API 调用** → 统一用 `call_llm_api()` 或 `_extract_content()` + `urllib.request`
- **数据库** → 所有表带 `user_id`，操作前调 `init_memory_db()`
- **样式** → 用 Indigo 主题 Design Tokens：主色 `#4f46e5`，背景 `#f1f5f9`，卡片 `#e0f2fe`

### 3. 防御性编码
- 所有 `.strip()` 前检查 `or ""`
- API 返回值用 `_extract_content()` 而非直接 `msg.get("content")`
- 避免只用 HTML `<button>` 标签（Streamlit 不认），用真 `st.button()`
- 数据处理后必须显示（不藏在 `if data.get()` 后面导致空白）

### 4. 改动后必须做的事
- 重启 Streamlit 验证无报错
- 如果有新依赖或架构变化，更新 `CLAUDE.md`

## 项目上下文

完整架构文档在 `C:\Users\zy\kaoyan-assistant\CLAUDE.md`。
Memory 记忆在 `C:\Users\zy\.claude\projects\C--Users-zy\memory\`。
