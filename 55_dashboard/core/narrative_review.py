"""叙事建议读取 + 审批留痕持久化。

建议来源：02_剧情数据/<日期>_建议.json（nrt-narrative-grower 产出），每个文件是
{check,priority,reason,content,cypher} 的数组。

留痕：_reviewed.json 记录每条建议（键=文件名#index）的审批结果，跨会话保留，
避免重复执行 cypher 与重复显示。
"""
import json
from datetime import datetime
from pathlib import Path

from config import settings

REVIEWED_PATH: Path = settings.NARRATIVE_DATA_DIR / "_reviewed.json"


def make_key(source_file, index):
    """条目稳定键：文件名 + 数组下标。"""
    return f"{source_file}#{index}"


def load_suggestions():
    """扫描 02_剧情数据 下 *.json（排除 _reviewed.json），展平为条目列表。

    每条附加 source_file、index、key。损坏/非数组文件整体跳过。
    """
    out = []
    data_dir = settings.NARRATIVE_DATA_DIR
    if not data_dir.exists():
        return out
    for path in sorted(data_dir.glob("*.json")):
        if path.name == REVIEWED_PATH.name:
            continue
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(items, list):
            continue
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row["source_file"] = path.name
            row["index"] = idx
            row["key"] = make_key(path.name, idx)
            out.append(row)
    return out


def load_reviewed():
    """读 _reviewed.json；缺失/损坏返回 {}。"""
    if not REVIEWED_PATH.exists():
        return {}
    try:
        data = json.loads(REVIEWED_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def mark_reviewed(key, status):
    """记录单条审批结果（approved/rejected）并原子写回（临时文件 + replace）。"""
    reviewed = load_reviewed()
    reviewed[key] = {"status": status, "ts": datetime.now().isoformat()}
    REVIEWED_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REVIEWED_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(reviewed, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(REVIEWED_PATH)
