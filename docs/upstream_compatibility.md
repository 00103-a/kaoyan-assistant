# 上游兼容与嵌入约定

## 当前基线

- 上游仓库：`k12335656565656565656/kaoyan-assistant`
- 默认分支：`master`
- 本次兼容基线：`4db887c`（2026-07-14，错题本与 AI 追问）
- 集成分支：`codex/upstream-master-compat-20260714`

远端 `main` 目前与默认 `master` 分叉，包含深色模式、数学流式渲染和多图上传等尚未合入默认分支的提交。除非上游切换默认分支，否则日常兼容基线仍以 `upstream/master` 为准；评估 `main` 时应另建工作树，不在本分支直接混合两条上游历史。

## 所有权边界

上游继续拥有主应用和通用体验：

- `app.py`
- `wrongbook_utils.py`
- `pack.py`
- 登录、数学、英语、打卡、学习资料和通用错题本

专业课扩展拥有自己的业务实现：

- `professional_knowledge/`
- `repositories/`
- `schemas/`
- `services/`
- `knowledge_base.py`
- `app_kb.py`
- `requirements_kb.txt`

`app.py` 只保留薄挂载层：导入入口函数、导航项和 `professional_kb` 路由。同步上游时，不把专业课业务逻辑继续写回巨型主文件。

## 共享契约

- 用户隔离统一使用 `user_id`。
- 默认数据库统一使用 `data/memory.db`，可由专业课模块通过 `MEMORY_DB` 环境变量覆盖。
- `user_wrong_questions` 是共享表。上游字段与专业课来源追踪字段均采用增量迁移，只允许增加可空列，不允许删列、改名或重建表。
- 专业课原始资料、草稿、人工确认文本和知识点仍由扩展自己的 repository 管理。
- 主应用依赖保持不变；PDF/OCR 扩展依赖放在 `requirements_kb.txt`，只有启用专业课资料识别时才安装。

共享错题表的兼容性由 `tests/test_wrong_question_schema_compatibility.py` 覆盖。

## 后续同步流程

```powershell
git fetch upstream --prune
git worktree add -b codex/upstream-master-compat-YYYYMMDD ..\integration\upstream-master-compat upstream/master
```

然后按顺序执行：

1. 移植专业课模块提交，不携带 `data/tasks/`、`data/test_materials/`、基准报告、日志或 `dist/`。
2. 在 `app.py` 中只恢复薄挂载层；若与上游页面块冲突，保留双方块并按“全局表单 → 专业课路由 → 其他页面”的顺序排列。
3. 确认 `pack.py` 仍会在扩展目录存在时复制专业课模块；目录不存在时应保持上游原行为。
4. 运行 `python -m py_compile ...`、`python -m pytest -q tests` 和打包内容检查。
5. 验证后再决定是否将集成分支合并到自己的长期分支；不要直接向上游默认分支开发。

## 本次上游冲突结论

从旧共同基线 `e90da83` 到上游 `4db887c`，上游主要修改 `app.py` 并新增错题本资源。专业课扩展的目录级模块可直接移植，唯一内容冲突出现在 `app.py` 页面入口附近，属于两段相邻的新增代码，不是业务语义冲突。
