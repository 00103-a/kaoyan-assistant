"""
Python bridge for kaoyan-skill-v2.5 prediction engine.
Calls Node.js exam-forecast-real.mjs as a subprocess.
"""
import subprocess
import json
import os
from pathlib import Path

PREDICT_DIR = Path(__file__).parent / "kaoyan_predict"
SCRIPT = PREDICT_DIR / "exam-forecast-real.mjs"


class KaoyanPredictError(Exception):
    pass


def check_node_available():
    try:
        subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return True
    except Exception:
        return False


def predict(school, major="", session="27届", timeout=90):
    if not SCRIPT.exists():
        raise KaoyanPredictError("预测引擎文件缺失")
    if not school.strip():
        raise KaoyanPredictError("请输入学校名称")

    args = [
        "node",
        str(SCRIPT),
        "-s", school.strip(),
        "-m", major.strip() if major else school.strip(),
        "-e", session,
        "-j",
    ]

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(PREDICT_DIR),
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except FileNotFoundError:
        raise KaoyanPredictError("未检测到 Node.js，请先安装 Node.js")
    except subprocess.TimeoutExpired:
        raise KaoyanPredictError(f"查询超时（>{timeout}秒），请稍后重试")

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise KaoyanPredictError(f"预测引擎错误{': ' + stderr if stderr else ''}")

    stdout = (result.stdout or "").strip()
    if not stdout:
        raise KaoyanPredictError("预测引擎返回为空")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise KaoyanPredictError(f"解析预测结果失败: {e}")

    if not isinstance(data, dict) or "compositeHeat" not in data:
        raise KaoyanPredictError("预测数据格式异常")

    return data


def normalize_for_ui(data):
    """返回一个经过校验和补默认值的展示用 dict"""
    d = dict(data)

    d.setdefault("compositeHeat", 0)
    d.setdefault("dataHeat", 0)
    d.setdefault("mediaHeat", 0)
    d.setdefault("heatLevel", {"label": "未知", "color": "⬜", "min": 0})
    d.setdefault("dataSource", "未知")
    d.setdefault("confidence", 0)
    d.setdefault("trend", "稳定")

    p = d.setdefault("prediction", {})
    p.setdefault("estimatedApplicants", 0)
    p.setdefault("estimatedRatio", 0)
    p.setdefault("estimatedCutScore", 0)
    d["prediction"] = p

    d.setdefault("admissionHistory", [])
    d.setdefault("examSubjects", [])
    d.setdefault("notes", [])
    d.setdefault("platforms", [])
    d.setdefault("failedPlatforms", [])

    si = d.setdefault("schoolInfo", {})
    si.setdefault("schoolLevel", "未知")
    si.setdefault("department", "未知")
    si.setdefault("pushRatioDesc", "")
    d["schoolInfo"] = si

    memory = d.setdefault("memory", {})
    memory.setdefault("summary", "")
    memory.setdefault("similarQueries", [])
    memory.setdefault("userProfile", {})
    d["memory"] = memory

    return d
