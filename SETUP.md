# 部署指南

## 环境要求

- Python 3.10+
- pip

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

项目依赖统一维护在 `requirements.txt` 中。

## 2. 配置环境变量

复制 `.env.example` 为 `.env`，至少填写 `AI_API_KEY`。`.env` 只保存在本机，不要提交到 Git。

也可以临时设置环境变量：

**Windows (CMD)**:
```cmd
set AI_API_KEY=sk-your-key-here
```

**Windows (PowerShell)**:
```powershell
$env:AI_API_KEY="sk-your-key-here"
```

**Linux / Mac**:
```bash
export AI_API_KEY="sk-your-key-here"
```

可选配置：
```bash
export AI_API_BASE="https://api.xiaomimimo.com/v1"
export AI_MODEL="mimo-v2.5"
```

## 3. 启动

**Windows**: 双击 `启动.bat`

**Linux/Mac**:
```bash
streamlit run app.py --server.port 8501
```

浏览器打开 `http://localhost:8501`。Windows 启动脚本默认使用 `http://localhost:8505`。

## 4. 目录结构

```
├── app.py              # 主程序
├── requirements.txt    # 依赖
├── 启动.bat            # Windows启动脚本
├── data/
│   ├── corpus/         # 110个考研数学知识点 (md)
│   └── memory.db       # SQLite用户数据库 (自动创建)
├── skills/             # 6个Skill定义
└── templates/          # Prompt模板
```

## 5. 常见问题

**Q: `ModuleNotFoundError: No module named 'streamlit'`**
A: 执行 `pip install -r requirements.txt`

**Q: API Key 未设置**
A: 首页会显示提示，按第2步设置环境变量

**Q: 知识库显示0个文档**
A: 点击侧边栏「刷新知识库」按钮

**Q: 数据库报错**
A: 删除 `data/memory.db`，重启后自动重建
