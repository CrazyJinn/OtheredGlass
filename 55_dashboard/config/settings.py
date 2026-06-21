"""后台配置：路径与环境。

Neo4j 凭证优先级：环境变量 NEO4J_PASSWORD > 项目根 settings.json 的 neo4j_password
（与 ${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py 的凭证来源一致）。
"""
import json
import os
from pathlib import Path

# 项目根（55_dashboard 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ROOT = Path(__file__).resolve().parents[1]

# 加载项目根 settings.json（凭证来源，与项目其他工具一致）
_project_settings = {}
_settings_json = PROJECT_ROOT / "settings.json"
if _settings_json.exists():
    _project_settings = json.loads(_settings_json.read_text(encoding="utf-8"))

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = (
    os.environ.get("NEO4J_PASSWORD")
    or _project_settings.get("neo4j_password")
    or ""
)

SCHEMA_DIR = PROJECT_ROOT / "00_init" / "Schema"
TAG_LIB_PATH = DASHBOARD_ROOT / "config" / "标签库.json"
IMAGE_ROOT = PROJECT_ROOT  # image_path 相对项目根
