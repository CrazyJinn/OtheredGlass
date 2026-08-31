# 角色美术治理后台（55_dashboard）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建一个 Streamlit 后台，对 Neo4j 图数据库中的角色美术生产链节点进行浏览、属性编辑、审批、sync 级联，并提供 deeplink 一键唤起 char-design agent 推进生产。

**Architecture:** 三层单向依赖（ui → core → repo）。`repo` 封装 neo4j-driver 与 Cypher；`core` 含级联引擎、审批状态机、Schema 加载器（字段定义动态解析自 `Schema/*.md`，标签词表读 `标签库.json`，status/enum 规则显式定义）；`ui` 为 Streamlit 页面与组件。后台不直接出图，靠 status 与 Claude Skills 协作，并提供 `vscode://` deeplink 唤起 char-design。

**Tech Stack:** Python 3.14、Streamlit、neo4j driver 6.2.0、pydantic、pillow、pandas、pytest。

## Global Constraints

- 落位：`55_dashboard/`；标签库迁入 `55_dashboard/config/标签库.json`。
- Neo4j 连接从环境变量读：`NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD`，复用 Skills 连的同一实例。
- Neo4j 中 label = 节点类型（如 `Character`、`DesignSheet`）；节点 `id` 属性 = snowflake Base62 字符串。
- 边有 `sync` 布尔属性；级联仅沿 `sync=true` 出边传播。
- V1 范围：`Character` + 美术链 6 节点（`AppearanceStyle`/`LanguageStyle`/`CostumeStyle`/`DesignSheet`/`IllusDesign`/`StandingIllustration`）。叙事其他、剧情、场景美术仅预留禁用入口 + TODO。
- 所有面向用户的提示为中文。
- 编辑 `status=11` 节点 → 自身回退到 `0`。
- 依赖安装：`pip install streamlit neo4j pydantic pillow pandas pytest`（neo4j 已装）。

---

## File Structure

```
55_dashboard/
├── app.py                      # Streamlit 入口：侧边栏导航 + 页面路由
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py             # 路径与配置
│   └── 标签库.json              # 迁自 55_manage/
├── repo/
│   ├── __init__.py
│   ├── neo4j_conn.py           # driver 单例
│   └── graph_repo.py           # Cypher 读写
├── core/
│   ├── __init__.py
│   ├── status.py               # status 规则 + enum 词表
│   ├── schema_loader.py        # 解析 Schema/*.md + 标签库.json → SchemaDef
│   ├── cascade.py              # sync BFS 级联
│   └── approval.py             # 审批状态机
├── ui/
│   ├── __init__.py
│   ├── page_overview.py
│   ├── page_character.py
│   ├── page_node_editor.py
│   ├── page_approval.py
│   └── components/
│       ├── __init__.py
│       ├── status_badge.py
│       ├── image_viewer.py
│       ├── launch_button.py
│       ├── tag_picker.py
│       └── field_form.py
└── tests/
    ├── __init__.py
    ├── conftest.py             # MockRepo fixture、样例 .md 文本
    ├── test_status.py
    ├── test_schema_loader.py
    ├── test_cascade.py
    ├── test_approval.py
    ├── test_launch_button.py
    ├── test_status_badge.py
    ├── test_image_viewer.py
    └── test_tag_picker.py
```

每个文件单一职责：`core` 纯 Python 可单测；`repo` 唯一碰数据库；`ui` 组件拆出"纯函数（可测）+ 渲染（手动验证）"。

---

## Task 1: 项目脚手架与测试基础设施

**Files:**
- Create: `55_dashboard/requirements.txt`
- Create: `55_dashboard/.env.example`
- Create: `55_dashboard/config/settings.py`
- Create: `55_dashboard/repo/__init__.py`、`55_dashboard/core/__init__.py`、`55_dashboard/ui/__init__.py`、`55_dashboard/ui/components/__init__.py`、`55_dashboard/tests/__init__.py`（空文件）
- Create: `55_dashboard/tests/conftest.py`
- Test: `55_dashboard/tests/conftest.py`（含 MockRepo 自检）

**Interfaces:**
- Produces: `MockRepo`（内存图，实现 `get_sync_downstream`/`set_status_batch`/`update_node`/`set_status`/`get_node`），供 core 层测试用；`SAMPLE_MD`（样例 Schema markdown 片段）。

- [ ] **Step 1: 创建依赖与配置文件**

`55_dashboard/requirements.txt`:
```
streamlit>=1.40
neo4j>=6.2
pydantic>=2.0
pillow>=10.0
pandas>=2.0
pytest>=8.0
```

`55_dashboard/.env.example`:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change-me
```

`55_dashboard/config/settings.py`:
```python
"""后台配置：路径与环境。"""
import os
from pathlib import Path

# 项目根（55_dashboard 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ROOT = Path(__file__).resolve().parents[1]

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

SCHEMA_DIR = PROJECT_ROOT / "00_init" / "Schema"
TAG_LIB_PATH = DASHBOARD_ROOT / "config" / "标签库.json"
IMAGE_ROOT = PROJECT_ROOT  # image_path 相对项目根
```

- [ ] **Step 2: 写 MockRepo 与样例文本**

`55_dashboard/tests/conftest.py`:
```python
"""测试基础设施：内存 MockRepo + 样例 Schema markdown。"""
from dataclasses import dataclass, field


class MockRepo:
    """内存图，模拟 graph_repo 的接口，供 core 单测使用。"""

    def __init__(self):
        self.nodes = {}          # id -> {"label", "status", "props"}
        self.sync_edges = []     # [(from_id, to_id)] 仅 sync=true
        self.status_calls = []   # 记录 set_status_batch 调用 [(ids, status)]
        self.updates = []        # 记录 update_node 调用

    def add_node(self, node_id, label, status=0, props=None):
        self.nodes[node_id] = {"label": label, "status": status, "props": props or {}}

    def add_sync_edge(self, from_id, to_id):
        self.sync_edges.append((from_id, to_id))

    def get_sync_downstream(self, node_id):
        return [dict(id=to, **self.nodes[to])
                for (f, to) in self.sync_edges if f == node_id and to in self.nodes]

    def set_status_batch(self, ids, status):
        self.status_calls.append((list(ids), status))
        for i in ids:
            if i in self.nodes:
                self.nodes[i]["status"] = status

    def set_status(self, node_id, status):
        self.set_status_batch([node_id], status)

    def update_node(self, node_id, props):
        self.updates.append((node_id, dict(props)))
        if node_id in self.nodes:
            self.nodes[node_id]["props"].update(props)

    def get_node(self, node_id):
        return dict(id=node_id, **self.nodes.get(node_id, {"label": "", "status": 0, "props": {}}))


# 样例 Schema markdown（模拟 00_init/Schema/叙事基础.md 的节点表格格式）
SAMPLE_MD = """# 01 叙事基础

### 角色（Character）

最小粒度：每个有名字的真实人物。

| 字段 | 中文 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| id | 编号 | string | 是 | snowflake Base62 |
| name | 姓名 | string | 是 | 陆择 |
| gender | 性别 | enum | 否 | 男 |
| birth_year | 出生年份 | int | 否 | 2003 |

### 事件（Event）

| 字段 | 中文 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| id | 编号 | string | 是 | x |
| title | 标题 | string | 是 | 加入战队 |
"""
```

- [ ] **Step 3: 安装依赖并验证导入**

Run:
```bash
pip install -r 55_dashboard/requirements.txt
```
Expected: 成功安装。

Run:
```bash
cd 55_dashboard && python -c "from tests.conftest import MockRepo; r=MockRepo(); r.add_node('a','Character',11); r.set_status('a',0); assert r.nodes['a']['status']==0; print('ok')"
```
Expected: 输出 `ok`。

- [ ] **Step 4: Commit**

```bash
git add 55_dashboard
git commit -m "feat(dashboard): 脚手架、配置与测试基础设施"
```

---

## Task 2: 数据访问层（neo4j_conn + graph_repo）

**Files:**
- Create: `55_dashboard/repo/neo4j_conn.py`
- Create: `55_dashboard/repo/graph_repo.py`
- Test: `55_dashboard/tests/test_graph_repo.py`

**Interfaces:**
- Consumes: `config.settings`（连接信息）。
- Produces（`graph_repo` 方法签名，core/ui 全靠这些）:
  - `get_node(node_id: str) -> dict`（含 `id`/`label`/`status`/其余属性）
  - `get_nodes(label: str) -> list[dict]`
  - `get_character_graph(char_id: str) -> dict`（`{"nodes": [...], "edges": [...]}`）
  - `get_sync_downstream(node_id: str) -> list[dict]`（一跳 `sync=true` 出边下游）
  - `update_node(node_id: str, props: dict) -> None`
  - `set_status(node_id: str, status: int) -> None`
  - `set_status_batch(node_ids: list[str], status: int) -> None`
  - `get_pending_approvals() -> list[dict]`（`status=10` 的节点）
  - `get_upstream_character_id(node_id: str) -> str | None`（节点回溯到所属 Character）

- [ ] **Step 1: 写 driver 单例**

`55_dashboard/repo/neo4j_conn.py`:
```python
"""neo4j driver 单例。"""
from neo4j import GraphDatabase
from config import settings

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _driver


def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
```

- [ ] **Step 2: 写 graph_repo 方法契约测试（用 mock session）**

`55_dashboard/tests/test_graph_repo.py`:
```python
"""graph_repo 测试：用 mock session 验证 Cypher 与返回映射。"""
from unittest.mock import MagicMock
from repo import graph_repo


def _fake_session(records):
    """返回一个 mock session，run() 返回含 records 的 result；支持 `with sess as s`。"""
    sess = MagicMock()
    sess.__enter__.return_value = sess   # 让 `with sess as s` 中 s 就是 sess
    result = MagicMock()
    result.__iter__ = lambda self: iter(records)
    result.single.return_value = records[0] if records else None
    sess.run.return_value = result
    return sess


def test_get_node_maps_record(monkeypatch):
    rec = {"id": "N1", "label": "Character", "props": {"name": "陆择"}}
    sess = _fake_session([rec])
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    node = graph_repo.get_node("N1")
    assert node["id"] == "N1"
    assert node["label"] == "Character"
    assert node["name"] == "陆择"


def test_set_status_batch_uses_unwind(monkeypatch):
    sess = _fake_session([])
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    graph_repo.set_status_batch(["N1", "N2"], 0)
    cypher = sess.run.call_args[0][0]
    assert "UNWIND" in cypher and "$ids" in cypher
    assert sess.run.call_args[1]["ids"] == ["N1", "N2"]
    assert sess.run.call_args[1]["status"] == 0


def test_get_pending_approvals_filters_status_10(monkeypatch):
    recs = [{"id": "X", "label": "DesignSheet", "status": 10}]
    sess = _fake_session(recs)
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    out = graph_repo.get_pending_approvals()
    assert out == recs
    assert "n.status=10" in sess.run.call_args[0][0]


def test_get_sync_downstream_filters_sync_true(monkeypatch):
    recs = [{"id": "D1", "label": "DesignSheet", "status": 2}]
    sess = _fake_session(recs)
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    out = graph_repo.get_sync_downstream("A1")
    assert out == recs
    cypher = sess.run.call_args[0][0]
    assert "sync = true" in cypher or "sync=true" in cypher
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd 55_dashboard && python -m pytest tests/test_graph_repo.py -v`
Expected: FAIL（`graph_repo` 未定义）。

- [ ] **Step 4: 实现 graph_repo**

`55_dashboard/repo/graph_repo.py`:
```python
"""图数据库读写：唯一写 Cypher 的地方。所有方法接收/返回普通 dict。"""
from contextlib import contextmanager
from repo.neo4j_conn import get_driver


@contextmanager
def _session():
    with get_driver().session() as s:
        yield s


def _label_of(node_id):
    """查节点 label。"""
    with _session() as s:
        rec = s.run("MATCH (n) WHERE n.id=$id RETURN labels(n)[0] AS label", id=node_id).single()
        return rec["label"] if rec else None


def get_node(node_id):
    with _session() as s:
        rec = s.run(
            "MATCH (n) WHERE n.id=$id RETURN n.id AS id, labels(n)[0] AS label, properties(n) AS props",
            id=node_id,
        ).single()
    if not rec:
        return None
    props = dict(rec["props"])
    label = rec["label"]
    props.update(id=rec["id"], label=label)
    return props


def get_nodes(label):
    with _session() as s:
        rs = s.run(
            "MATCH (n:`%s`) RETURN n.id AS id, labels(n)[0] AS label, properties(n) AS props" % label
        )
    out = []
    for rec in rs:
        props = dict(rec["props"])
        props.update(id=rec["id"], label=rec["label"])
        out.append(props)
    return out


def get_character_graph(char_id):
    """取角色 + 美术链全部节点与边。"""
    with _session() as s:
        rs = s.run(
            """
            MATCH p=(c:Character)-[*0..5]-(n)
            WHERE c.id=$id
            WITH collect(DISTINCT n) AS ns, relationships(p) AS rs
            UNWIND rs AS r
            WITH ns, collect(DISTINCT r) AS allr
            RETURN ns, allr
            """,
            id=char_id,
        )
        rec = rs.single()
    if not rec:
        return {"nodes": [], "edges": []}
    nodes = [{"id": n.id, "label": list(n.labels)[0], "status": n.get("status"), "name": n.get("name")}
             for n in rec["ns"]]
    edges = [{"from": r.start_node.id, "to": r.end_node.id, "type": r.type, "sync": r.get("sync")}
             for r in rec["allr"]]
    return {"nodes": nodes, "edges": edges}


def get_sync_downstream(node_id):
    """一跳内 sync=true 出边指向的下游。"""
    with _session() as s:
        rs = s.run(
            """
            MATCH (a)-[r]->(b)
            WHERE a.id=$id AND r.sync=true
            RETURN b.id AS id, labels(b)[0] AS label, b.status AS status
            """,
            id=node_id,
        )
    return [{"id": r["id"], "label": r["label"], "status": r["status"]} for r in rs]


def update_node(node_id, props):
    clean = {k: v for k, v in props.items() if k not in ("id", "label")}
    with _session() as s:
        s.run(
            "MATCH (n) WHERE n.id=$id SET n += $props",
            id=node_id, props=clean,
        ).consume()


def set_status(node_id, status):
    set_status_batch([node_id], status)


def set_status_batch(node_ids, status):
    with _session() as s:
        s.run(
            "UNWIND $ids AS x MATCH (n) WHERE n.id=x SET n.status=$status",
            ids=node_ids, status=status,
        ).consume()


def get_pending_approvals():
    with _session() as s:
        rs = s.run(
            "MATCH (n) WHERE n.status=10 RETURN n.id AS id, labels(n)[0] AS label, n.status AS status"
        )
    return [{"id": r["id"], "label": r["label"], "status": r["status"]} for r in rs]


def get_upstream_character_id(node_id):
    """从节点回溯到所属 Character id。"""
    with _session() as s:
        rec = s.run(
            """
            MATCH (c:Character)-[*0..5]-(n)
            WHERE n.id=$id AND c.id<>$id
            RETURN c.id AS cid LIMIT 1
            """,
            id=node_id,
        ).single()
    return rec["cid"] if rec else None
```

> 注：`get_character_graph` / `get_upstream_character_id` 的多跳遍历 Cypher 在真实库上需手动校验（见各任务手动验证）；mock 测试只覆盖单跳方法。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd 55_dashboard && python -m pytest tests/test_graph_repo.py -v`
Expected: 4 passed。

- [ ] **Step 6: Commit**

```bash
git add 55_dashboard/repo 55_dashboard/tests/test_graph_repo.py
git commit -m "feat(dashboard): repo 层 neo4j 连接与 graph_repo Cypher"
```

---

## Task 3: core/status.py（status 规则与 enum 词表）

**Files:**
- Create: `55_dashboard/core/status.py`
- Test: `55_dashboard/tests/test_status.py`

**Interfaces:**
- Produces:
  - `NODE_STATUS: dict[str, dict]`（每 label：`legal`/`completion`/`has_approval`）
  - `ENUM_OPTIONS: dict[str, list[str]]`（gender/type/knowledge_level）
  - `STATUS_LABEL: dict[int, str]`
  - `completion_status(label) -> int`
  - `has_approval(label) -> bool`
  - `is_approved(status) -> bool`
  - `can_submit(label, status) -> bool`

- [ ] **Step 1: 写失败测试**

`55_dashboard/tests/test_status.py`:
```python
from core import status


def test_completion_status():
    assert status.completion_status("DesignSheet") == 2
    assert status.completion_status("CostumeStyle") == 1
    assert status.completion_status("AppearanceStyle") == 1


def test_has_approval():
    assert status.has_approval("DesignSheet") is True
    assert status.has_approval("AppearanceStyle") is False


def test_is_approved():
    assert status.is_approved(11) is True
    assert status.is_approved(2) is False


def test_can_submit_only_at_completion():
    assert status.can_submit("DesignSheet", 2) is True
    assert status.can_submit("DesignSheet", 0) is False
    assert status.can_submit("DesignSheet", 11) is False
    assert status.can_submit("AppearanceStyle", 1) is False  # 无审批


def test_enum_options_present():
    assert "男" in status.ENUM_OPTIONS["gender"]
    assert "行动" in status.ENUM_OPTIONS["type"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd 55_dashboard && python -m pytest tests/test_status.py -v`
Expected: FAIL（模块未定义）。

- [ ] **Step 3: 实现**

`55_dashboard/core/status.py`:
```python
"""显式定义 status 流转规则与 enum 词表（不解析 .md）。"""

# 生产态 0/1/2，审批专属 10 待审 / 11 批准。驳回归 0。
NODE_STATUS = {
    "AppearanceStyle":     {"legal": [0, 1],          "completion": 1, "has_approval": False},
    "LanguageStyle":       {"legal": [0, 1],          "completion": 1, "has_approval": False},
    "CostumeStyle":        {"legal": [0, 1],          "completion": 1, "has_approval": False},
    "DesignSheet":         {"legal": [0, 1, 2, 10, 11], "completion": 2, "has_approval": True},
    "IllusDesign":         {"legal": [0, 1, 2, 10, 11], "completion": 2, "has_approval": True},
    "StandingIllustration":{"legal": [0, 1, 2, 10, 11], "completion": 2, "has_approval": True},
}

ENUM_OPTIONS = {
    "gender": ["男", "女"],
    "type": ["行动", "交流", "转折", "状态变化"],
    "knowledge_level": ["1", "2", "3"],
}

STATUS_LABEL = {
    0: "待处理", 1: "已完成", 2: "图片完成", 10: "待审", 11: "批准",
}


def completion_status(label):
    return NODE_STATUS[label]["completion"]


def has_approval(label):
    return NODE_STATUS[label]["has_approval"]


def is_approved(status):
    return status == 11


def can_submit(label, status):
    """只有有审批的节点，在完成态时才能提交审批。"""
    return has_approval(label) and status == completion_status(label)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd 55_dashboard && python -m pytest tests/test_status.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add 55_dashboard/core/status.py 55_dashboard/tests/test_status.py
git commit -m "feat(dashboard): core/status status 规则与 enum 词表"
```

---

## Task 4: core/schema_loader.py（解析 .md + 标签库.json）

**Files:**
- Create: `55_dashboard/core/schema_loader.py`
- Test: `55_dashboard/tests/test_schema_loader.py`

**Interfaces:**
- Produces:
  - `FieldDef`（`name`/`label_cn`/`type`/`required`）
  - `NodeDef`（`label`/`fields`）
  - `SchemaDef`（`nodes: dict[str, NodeDef]`/`tag_fields: dict`）
  - `parse_md(md_text: str) -> dict[str, NodeDef]`
  - `load_schema(schema_dir, tag_lib_path) -> SchemaDef`

- [ ] **Step 1: 写失败测试**

`55_dashboard/tests/test_schema_loader.py`:
```python
from core import schema_loader
from tests.conftest import SAMPLE_MD


def test_parse_md_extracts_fields():
    nodes = schema_loader.parse_md(SAMPLE_MD)
    assert "Character" in nodes and "Event" in nodes
    char = nodes["Character"]
    names = [f.name for f in char.fields]
    assert "name" in names and "gender" in names and "birth_year" in names
    gender = next(f for f in char.fields if f.name == "gender")
    assert gender.type == "enum"
    by = next(f for f in char.fields if f.name == "birth_year")
    assert by.type == "int"


def test_parse_md_skips_header_and_separator_rows():
    nodes = schema_loader.parse_md(SAMPLE_MD)
    char = nodes["Character"]
    names = [f.name for f in char.fields]
    assert "字段" not in names  # 表头行被跳过


def test_load_schema_merges_tag_fields(tmp_path, monkeypatch):
    import json
    md = tmp_path / "t.md"
    md.write_text(SAMPLE_MD)
    tag = tmp_path / "tag.json"
    tag.write_text(json.dumps({"Character": {"gender": {"label": "性别", "multi": False, "options": ["男", "女"]}}}))
    sd = schema_loader.load_schema(str(tmp_path), str(tag))
    assert "Character" in sd.nodes
    assert "gender" in sd.tag_fields["Character"]


def test_load_schema_rejects_bad_table(tmp_path):
    bad = "# X\n### 坏（Bad）\n| 只有 | 一列 |\n"
    (tmp_path / "b.md").write_text(bad)
    try:
        schema_loader.load_schema(str(tmp_path), None)
    except schema_loader.SchemaError:
        return
    raise AssertionError("应抛 SchemaError")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd 55_dashboard && python -m pytest tests/test_schema_loader.py -v`
Expected: FAIL。

- [ ] **Step 3: 实现**

`55_dashboard/core/schema_loader.py`:
```python
"""动态加载 Schema：字段定义解析自 .md 表格，标签词表读 json。"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


class SchemaError(Exception):
    pass


@dataclass
class FieldDef:
    name: str
    label_cn: str
    type: str
    required: bool


@dataclass
class NodeDef:
    label: str
    fields: list = field(default_factory=list)


@dataclass
class SchemaDef:
    nodes: dict        # label -> NodeDef
    tag_fields: dict   # label -> {field_name: tagdef}


# ### 角色名称（Label）  或  ### 角色名称(Label)
NODE_HEADER_RE = re.compile(r"^###\s+.+?[（(]\s*(\w+)\s*[)）]")
_SEP_RE = re.compile(r"^\|[\s:|-]+\|?\s*$")


def _parse_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) < 4:
        return None
    return cells


def parse_md(md_text):
    nodes = {}
    current = None
    for line in md_text.splitlines():
        if line.startswith("### "):
            m = NODE_HEADER_RE.match(line)
            if m:
                current = NodeDef(label=m.group(1))
                nodes[current.label] = current
            else:
                current = None  # 边标题等非节点 H3：停止向当前节点 append
            continue
        if current is None or not line.startswith("|"):
            continue
        if _SEP_RE.match(line):
            continue
        cells = _parse_row(line)
        if cells is None:
            raise SchemaError(f"节点 {current.label} 的表格格式不合法：{line!r}")
        name, label_cn, ftype, required = cells[0], cells[1], cells[2], cells[3]
        if name == "字段":  # 表头
            continue
        current.fields.append(FieldDef(name=name, label_cn=label_cn, type=ftype, required=(required == "是")))
    return nodes


def load_schema(schema_dir, tag_lib_path):
    nodes = {}
    for md_file in sorted(Path(schema_dir).glob("*.md")):
        nodes.update(parse_md(md_file.read_text(encoding="utf-8")))
    tag_fields = {}
    if tag_lib_path and Path(tag_lib_path).exists():
        tag_fields = json.loads(Path(tag_lib_path).read_text(encoding="utf-8"))
    return SchemaDef(nodes=nodes, tag_fields=tag_fields)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd 55_dashboard && python -m pytest tests/test_schema_loader.py -v`
Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add 55_dashboard/core/schema_loader.py 55_dashboard/tests/test_schema_loader.py
git commit -m "feat(dashboard): core/schema_loader 动态解析 Schema 与标签库"
```

---

## Task 5: core/cascade.py（sync BFS 级联）

**Files:**
- Create: `55_dashboard/core/cascade.py`
- Test: `55_dashboard/tests/test_cascade.py`

**Interfaces:**
- Consumes: repo 接口 `get_sync_downstream(id) -> list[dict]`、`set_status_batch(ids, status)`。
- Produces:
  - `CascadedNode`（`id`/`label`/`level`）
  - `cascade_reset(changed_id, repo) -> list[CascadedNode]`

- [ ] **Step 1: 写失败测试**

`55_dashboard/tests/test_cascade.py`:
```python
from core import cascade
from tests.conftest import MockRepo


def _chain():
    """Character -> Appearance -> DesignSheet（全 sync=true），
    DesignSheet -> IllusDesign（sync=false，不在 sync_edges 里）。"""
    r = MockRepo()
    r.add_node("C", "Character", props={})
    r.add_node("A", "AppearanceStyle", status=1)
    r.add_node("D", "DesignSheet", status=11)
    r.add_node("I", "IllusDesign", status=11)
    r.add_sync_edge("C", "A")
    r.add_sync_edge("A", "D")
    return r


def test_cascade_resets_downstream_to_zero():
    r = _chain()
    out = cascade.cascade_reset("C", r)
    ids = {n.id for n in out}
    assert ids == {"A", "D"}
    assert r.nodes["A"]["status"] == 0
    assert r.nodes["D"]["status"] == 0


def test_cascade_does_not_touch_source():
    r = _chain()
    r.nodes["A"]["status"] = 1  # 源是 A 这次
    cascade.cascade_reset("A", r)
    assert r.nodes["A"]["status"] == 1  # 源自身不变
    assert r.nodes["D"]["status"] == 0


def test_cascade_records_levels():
    r = _chain()
    out = cascade.cascade_reset("C", r)
    by_id = {n.id: n.level for n in out}
    assert by_id["A"] == 1
    assert by_id["D"] == 2


def test_cascade_blocked_by_sync_false():
    # D->I 不在 sync_edges，所以 I 不受影响
    r = _chain()
    cascade.cascade_reset("C", r)
    assert r.nodes["I"]["status"] == 11


def test_cascade_empty_when_no_downstream():
    r = MockRepo()
    r.add_node("X", "StandingIllustration", status=2)
    out = cascade.cascade_reset("X", r)
    assert out == []
    assert r.status_calls == []
```

- [ ] **Step 2: 运行确认失败**

Run: `cd 55_dashboard && python -m pytest tests/test_cascade.py -v`
Expected: FAIL。

- [ ] **Step 3: 实现**

`55_dashboard/core/cascade.py`:
```python
"""sync 级联：沿 sync=true 出边 BFS，重置下游 status=0。"""
from dataclasses import dataclass


@dataclass
class CascadedNode:
    id: str
    label: str
    level: int


def cascade_reset(changed_id, repo):
    """BFS 重置 changed_id 的 sync=true 可达下游。源自身不改。"""
    queue = [(changed_id, 0)]
    visited = {changed_id}
    result = []
    while queue:
        cur, level = queue.pop(0)
        for d in repo.get_sync_downstream(cur):
            did = d["id"]
            if did not in visited:
                visited.add(did)
                result.append(CascadedNode(id=did, label=d.get("label", ""), level=level + 1))
                queue.append((did, level + 1))
    if result:
        repo.set_status_batch([n.id for n in result], 0)
    return result
```

- [ ] **Step 4: 运行确认通过**

Run: `cd 55_dashboard && python -m pytest tests/test_cascade.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add 55_dashboard/core/cascade.py 55_dashboard/tests/test_cascade.py
git commit -m "feat(dashboard): core/cascade sync BFS 级联"
```

---

## Task 6: core/approval.py（审批状态机）

**Files:**
- Create: `55_dashboard/core/approval.py`
- Test: `55_dashboard/tests/test_approval.py`

**Interfaces:**
- Consumes: `core.status`。
- Produces:
  - `IllegalTransition`（异常）
  - `submit(label, status) -> int`（返回目标 status=10）
  - `approve() -> int`（=11）
  - `reject() -> int`（=0）
  - `on_edit(status) -> int | None`（编辑时：若 status==11 回退 0，否则不变返回 None）

- [ ] **Step 1: 写失败测试**

`55_dashboard/tests/test_approval.py`:
```python
import pytest
from core import approval


def test_submit_at_completion_returns_10():
    assert approval.submit("DesignSheet", 2) == 10


def test_submit_rejects_wrong_status():
    with pytest.raises(approval.IllegalTransition):
        approval.submit("DesignSheet", 0)
    with pytest.raises(approval.IllegalTransition):
        approval.submit("DesignSheet", 11)


def test_submit_rejects_no_approval_label():
    with pytest.raises(approval.IllegalTransition):
        approval.submit("AppearanceStyle", 1)


def test_approve_and_reject():
    assert approval.approve() == 11
    assert approval.reject() == 0


def test_on_edit_reverts_approved():
    assert approval.on_edit(11) == 0


def test_on_edit_keeps_other():
    assert approval.on_edit(2) is None
    assert approval.on_edit(10) is None
    assert approval.on_edit(0) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd 55_dashboard && python -m pytest tests/test_approval.py -v`
Expected: FAIL。

- [ ] **Step 3: 实现**

`55_dashboard/core/approval.py`:
```python
"""审批状态机：submit/approve/reject + 编辑回退规则。"""
from core import status


class IllegalTransition(Exception):
    pass


def submit(label, current_status):
    if not status.can_submit(label, current_status):
        raise IllegalTransition(f"{label} status={current_status} 不可提交审批")
    return 10


def approve():
    return 11


def reject():
    return 0


def on_edit(current_status):
    """编辑节点时：已批准则回退到 0，否则不改（返回 None）。"""
    if status.is_approved(current_status):
        return 0
    return None
```

- [ ] **Step 4: 运行确认通过**

Run: `cd 55_dashboard && python -m pytest tests/test_approval.py -v`
Expected: 6 passed。

- [ ] **Step 5: Commit**

```bash
git add 55_dashboard/core/approval.py 55_dashboard/tests/test_approval.py
git commit -m "feat(dashboard): core/approval 审批状态机"
```

---

## Task 7: ui/components/launch_button.py（deeplink 按钮）

**Files:**
- Create: `55_dashboard/ui/components/launch_button.py`
- Test: `55_dashboard/tests/test_launch_button.py`

**Interfaces:**
- Produces:
  - `build_deeplink(char_id: str) -> str`
  - `render(char_id: str, label: str = "推进美术流程") -> None`（调 `st.link_button`）

- [ ] **Step 1: 写失败测试（纯函数）**

`55_dashboard/tests/test_launch_button.py`:
```python
import urllib.parse
from ui.components import launch_button


def test_deeplink_uses_vscode_handler():
    url = launch_button.build_deeplink("NvCkQmFPFu")
    assert url.startswith("vscode://anthropic.claude-code/open?prompt=")


def test_deeplink_embeds_char_id_and_agent():
    url = launch_button.build_deeplink("NvCkQmFPFu")
    prompt = urllib.parse.unquote(url.split("prompt=", 1)[1])
    assert "char-design" in prompt
    assert "NvCkQmFPFu" in prompt


def test_deeplink_is_url_encoded():
    url = launch_button.build_deeplink("NvCkQmFPFu")
    # 含中文时必须被 encode
    assert "%20" in url or urllib.parse.quote(" ") in url
```

- [ ] **Step 2: 运行确认失败**

Run: `cd 55_dashboard && python -m pytest tests/test_launch_button.py -v`
Expected: FAIL。

- [ ] **Step 3: 实现**

`55_dashboard/ui/components/launch_button.py`:
```python
"""「推进」按钮：生成 vscode:// deeplink 唤起 char-design agent。"""
import urllib.parse

VSCODE_HANDLER = "vscode://anthropic.claude-code/open"


def build_deeplink(char_id):
    prompt = f"使用 char-design agent 推进角色 {char_id} 的美术流程"
    return f"{VSCODE_HANDLER}?prompt={urllib.parse.quote(prompt)}"


def render(char_id, label="推进美术流程"):
    import streamlit as st
    st.link_button(label, build_deeplink(char_id))
```

- [ ] **Step 4: 运行确认通过**

Run: `cd 55_dashboard && python -m pytest tests/test_launch_button.py -v`
Expected: 3 passed。

- [ ] **Step 5: 手动验证渲染（可选）**

Run: `cd 55_dashboard && python -c "from ui.components import launch_button as l; print(l.build_deeplink('NvCkQmFPFu'))"`
Expected: 输出形如 `vscode://anthropic.claude-code/open?prompt=%E4%BD%BF%E7%94%A8...NvCkQmFPFu...`。

- [ ] **Step 6: Commit**

```bash
git add 55_dashboard/ui/components/launch_button.py 55_dashboard/tests/test_launch_button.py
git commit -m "feat(dashboard): launch_button deeplink 唤起 char-design"
```

---

## Task 8: ui/components/status_badge.py

**Files:**
- Create: `55_dashboard/ui/components/status_badge.py`
- Test: `55_dashboard/tests/test_status_badge.py`

**Interfaces:**
- Produces: `badge_text(status) -> str`、`badge_color(status) -> str`、`render(status)`。

- [ ] **Step 1: 写失败测试**

`55_dashboard/tests/test_status_badge.py`:
```python
from ui.components import status_badge


def test_badge_text():
    assert status_badge.badge_text(0) == "待处理"
    assert status_badge.badge_text(10) == "待审"
    assert status_badge.badge_text(11) == "批准"


def test_badge_color():
    assert status_badge.badge_color(0) == "gray"
    assert status_badge.badge_color(10) == "orange"
    assert status_badge.badge_color(11) == "green"
```

- [ ] **Step 2: 运行确认失败 → Step 3: 实现**

`55_dashboard/ui/components/status_badge.py`:
```python
"""status 徽章：文本与颜色映射 + 渲染。"""
from core.status import STATUS_LABEL

_COLOR = {0: "gray", 1: "blue", 2: "blue", 10: "orange", 11: "green"}


def badge_text(status):
    return STATUS_LABEL.get(status, str(status))


def badge_color(status):
    return _COLOR.get(status, "gray")


def render(status):
    import streamlit as st
    text = badge_text(status)
    st.markdown(f"**状态**：{text}")
```

- [ ] **Step 4: 运行确认通过**

Run: `cd 55_dashboard && python -m pytest tests/test_status_badge.py -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add 55_dashboard/ui/components/status_badge.py 55_dashboard/tests/test_status_badge.py
git commit -m "feat(dashboard): status_badge 组件"
```

---

## Task 9: ui/components/tag_picker.py（标签合成纯函数）

**Files:**
- Create: `55_dashboard/ui/components/tag_picker.py`
- Test: `55_dashboard/tests/test_tag_picker.py`

**Interfaces:**
- Produces:
  - `compose_value(tagdef: dict, selections: dict) -> str`（把选择合成分号分隔的值串）
  - `merge_options(tagdef: dict, gender: str | None) -> list/dict`（合并性别差异候选）
  - `render(field_name, tagdef, current_value, gender) -> str`（渲染并返回新值）

- [ ] **Step 1: 写失败测试**

`55_dashboard/tests/test_tag_picker.py`:
```python
from ui.components import tag_picker


def test_compose_simple_multi():
    tagdef = {"label": "特殊标记", "multi": True, "options": ["疤痕", "泪痣"]}
    out = tag_picker.compose_value(tagdef, {"__main__": ["疤痕", "泪痣"]})
    assert out == "疤痕;泪痣"


def test_compose_compound_hair():
    tagdef = {"label": "头发", "combine": "stack", "groups": [
        {"key": "color", "label": "发色", "suffix": "色", "multi": True, "options": ["深棕"]},
        {"key": "style", "label": "发型", "suffix": "", "multi": True, "options": ["大波浪"]},
        {"key": "length", "label": "发长", "suffix": "", "multi": False, "options": ["长发"]},
    ]}
    out = tag_picker.compose_value(tagdef, {"color": ["深棕"], "style": ["大波浪"], "length": ["长发"]})
    assert out == "深棕色大波浪长发"


def test_merge_options_appends_gender():
    tagdef = {"label": "体态", "multi": False, "options": ["修长", "匀称"], "female": ["曼妙", "娇小"]}
    merged = tag_picker.merge_options(tagdef, "女")
    assert "曼妙" in merged and "修长" in merged


def test_merge_options_no_gender():
    tagdef = {"label": "体态", "multi": False, "options": ["修长"]}
    assert tag_picker.merge_options(tagdef, None) == ["修长"]


def test_compose_empty():
    tagdef = {"label": "x", "multi": True, "options": ["a"]}
    assert tag_picker.compose_value(tagdef, {}) == ""
```

- [ ] **Step 2: 运行确认失败 → Step 3: 实现纯函数**

`55_dashboard/ui/components/tag_picker.py`:
```python
"""标签选择：受控词表合成（简单/复合/性别差异）。"""


def compose_value(tagdef, selections):
    """把选择合成「分号分隔」的值串。复合维度按 groups 顺序拼接。"""
    if "combine" in tagdef:
        parts = []
        for g in tagdef["groups"]:
            for v in selections.get(g["key"], []):
                parts.append(f"{v}{g.get('suffix', '')}")
        return "".join(parts)
    vals = selections.get("__main__", [])
    return ";".join(vals)


def merge_options(tagdef, gender):
    """合并公共 options 与对应性别的追加候选。"""
    opts = list(tagdef.get("options", []))
    key = "female" if gender == "女" else "male" if gender == "男" else None
    if key and key in tagdef:
        opts.extend(tagdef[key])
    return opts


def render(field_name, tagdef, current_value, gender):
    """渲染标签选择器，返回新值串。复合维度按 group 分组渲染。"""
    import streamlit as st
    if "combine" in tagdef:
        selections = {}
        for g in tagdef["groups"]:
            opts = list(g.get("options", []))
            gk = "female" if gender == "女" else "male" if gender == "男" else None
            if gk and gk in g:
                opts.extend(g[gk])
            widget = st.multiselect if g.get("multi") else st.selectbox
            selections[g["key"]] = widget(g["label"], options=opts, key=f"{field_name}_{g['key']}")
        return compose_value(tagdef, selections)
    opts = merge_options(tagdef, gender)
    if tagdef.get("multi"):
        chosen = st.multiselect(tagdef["label"], options=opts, default=current_value.split(";") if current_value else [])
        return compose_value(tagdef, {"__main__": chosen})
    chosen = st.selectbox(tagdef["label"], options=[""] + opts, index=0)
    return compose_value(tagdef, {"__main__": [chosen] if chosen else []})
```

- [ ] **Step 4: 运行确认通过**

Run: `cd 55_dashboard && python -m pytest tests/test_tag_picker.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add 55_dashboard/ui/components/tag_picker.py 55_dashboard/tests/test_tag_picker.py
git commit -m "feat(dashboard): tag_picker 标签合成与渲染"
```

---

## Task 10: ui/components/field_form.py（按字段类型动态渲染）

**Files:**
- Create: `55_dashboard/ui/components/field_form.py`
- Test: 手动验证为主（依赖 streamlit；纯分发逻辑可加薄测试）

**Interfaces:**
- Consumes: `SchemaDef`、`tag_picker`、`image_viewer`、`status.ENUM_OPTIONS`。
- Produces: `render(node_def, tag_fields, node_data, gender) -> dict`（返回编辑后的 props）。

- [ ] **Step 1: 实现**

`55_dashboard/ui/components/field_form.py`:
```python
"""按 FieldDef.type 动态渲染表单，标签字段交 tag_picker。"""
from core.schema_loader import FieldDef
from ui.components import tag_picker, image_viewer
from core import status


def _render_field(field: FieldDef, current, tag_fields, gender):
    import streamlit as st
    name, ftype = field.name, field.type
    cur = current if current is not None else ""

    # 标签字段优先（在标签库里）
    tagdef = tag_fields.get(name) if tag_fields else None
    if tagdef is not None:
        return tag_picker.render(name, tagdef, cur, gender)

    # 只读字段
    if name in ("id", "prompt_path"):
        st.text_input(field.label_cn, value=str(cur), disabled=True)
        return cur

    if name in ("image_path", "image"):
        image_viewer.render(cur)
        return cur

    # enum 词表
    if ftype == "enum" and name in status.ENUM_OPTIONS:
        return st.selectbox(field.label_cn, options=status.ENUM_OPTIONS[name], index=0)

    if ftype == "int":
        return st.number_input(field.label_cn, value=int(cur) if str(cur).strip() else 0, step=1)
    if ftype == "Date":
        return st.date_input(field.label_cn).isoformat()
    # 默认 string
    return st.text_area(field.label_cn, value=str(cur))


def render(node_def, tag_fields, node_data, gender=None):
    """渲染节点全部字段，返回 props dict。"""
    import streamlit as st
    props = {}
    for f in node_def.fields:
        props[f.name] = _render_field(f, node_data.get(f.name), tag_fields, gender)
    return props
```

- [ ] **Step 2: 手动验证（smoke）**

Run: `cd 55_dashboard && python -c "from ui.components import field_form; print(field_form.render)"`
Expected: 无导入错误。

- [ ] **Step 3: Commit**

```bash
git add 55_dashboard/ui/components/field_form.py
git commit -m "feat(dashboard): field_form 动态表单渲染"
```

---

## Task 11: ui/components/image_viewer.py

**Files:**
- Create: `55_dashboard/ui/components/image_viewer.py`
- Test: `55_dashboard/tests/test_image_viewer.py`

**Interfaces:**
- Produces: `resolve_path(image_path) -> Path`、`render(image_path)`。

- [ ] **Step 1: 写失败测试（纯函数 resolve_path）**

`55_dashboard/tests/test_image_viewer.py`:
```python
from ui.components import image_viewer


def test_resolve_path_none_when_missing():
    assert image_viewer.resolve_path("nonexistent.png") is None


def test_resolve_path_none_when_empty():
    assert image_viewer.resolve_path("") is None
    assert image_viewer.resolve_path(None) is None


def test_resolve_path_existing(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    assert image_viewer.resolve_path(str(f)) == f
```

- [ ] **Step 2: 运行确认失败**

Run: `cd 55_dashboard && python -m pytest tests/test_image_viewer.py -v`
Expected: FAIL（模块未定义）。

- [ ] **Step 3: 实现**

`55_dashboard/ui/components/image_viewer.py`:
```python
"""图片预览：读 image_path（相对项目根），缺失则提示。"""
from pathlib import Path
from config import settings


def resolve_path(image_path):
    if not image_path:
        return None
    p = Path(image_path)
    if not p.is_absolute():
        p = settings.IMAGE_ROOT / p
    return p if p.exists() else None


def render(image_path):
    import streamlit as st
    p = resolve_path(image_path)
    if p is None:
        st.info("图片未生成" if image_path else "无图片")
        return
    st.image(str(p))
```

- [ ] **Step 4: 运行确认通过**

Run: `cd 55_dashboard && python -m pytest tests/test_image_viewer.py -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add 55_dashboard/ui/components/image_viewer.py 55_dashboard/tests/test_image_viewer.py
git commit -m "feat(dashboard): image_viewer 图片预览"
```

---

## Task 12: ui/page_node_editor.py（核心操作页）

**Files:**
- Create: `55_dashboard/ui/page_node_editor.py`

**Interfaces:**
- Consumes: `graph_repo`、`schema_loader.SchemaDef`、`field_form`、`image_viewer`、`status_badge`、`launch_button`、`approval`、`cascade`。
- Produces: `render(schema, node_id)`。

- [ ] **Step 1: 实现**

`55_dashboard/ui/page_node_editor.py`:
```python
"""节点编辑器：改属性 + 保存（级联）+ 提交审批。"""
import streamlit as st

from repo import graph_repo
from core import approval, cascade, status as status_mod
from ui.components import field_form, status_badge, image_viewer, launch_button


def render(schema, node_id):
    node = graph_repo.get_node(node_id)
    if not node:
        st.error("节点不存在")
        return
    label = node["label"]
    st.subheader(f"{label} · {node.get('name', node_id)}")
    status_badge.render(node.get("status"))

    # 图片预览
    if "image_path" in node:
        image_viewer.render(node["image_path"])

    node_def = schema.nodes.get(label)
    if node_def is None:
        st.warning(f"Schema 未定义 {label}（可能是预留节点）")
        return
    tag_fields = schema.tag_fields.get(label, {})
    gender = _lookup_gender(node_id)
    props = field_form.render(node_def, tag_fields, node, gender)

    # 所属角色的「推进」按钮
    char_id = graph_repo.get_upstream_character_id(node_id)
    if char_id:
        launch_button.render(char_id, "推进此角色流程")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("保存", type="primary"):
            graph_repo.update_node(node_id, props)
            revert = approval.on_edit(node.get("status", 0))
            if revert is not None:
                graph_repo.set_status(node_id, revert)
                st.info(f"该节点原为已批准，已回退到 {revert}（待重做）")
            affected = cascade.cascade_reset(node_id, graph_repo)
            if affected:
                names = "、".join(f"{n.label}({n.id})" for n in affected)
                st.success(f"已保存。级联重置 {len(affected)} 个下游：{names}")
            else:
                st.success("已保存（无 sync 下游受影响）")
            st.rerun()
    with col2:
        if status_mod.can_submit(label, node.get("status", 0)):
            if st.button("提交审批"):
                new = approval.submit(label, node["status"])
                graph_repo.set_status(node_id, new)
                st.success("已提交审批（status=10）")
                st.rerun()


def _lookup_gender(node_id):
    char_id = graph_repo.get_upstream_character_id(node_id)
    if not char_id:
        return None
    c = graph_repo.get_node(char_id)
    return c.get("gender") if c else None
```

- [ ] **Step 2: 手动验证（在 app.py 集成后）+ Commit**

```bash
git add 55_dashboard/ui/page_node_editor.py
git commit -m "feat(dashboard): 节点编辑器（保存级联 + 提交审批）"
```

---

## Task 13: ui/page_approval.py（审批中心）

**Files:**
- Create: `55_dashboard/ui/page_approval.py`

**Interfaces:**
- Produces: `render()`。

- [ ] **Step 1: 实现**

`55_dashboard/ui/page_approval.py`:
```python
"""审批中心：列出 status=10，通过/驳回。"""
import streamlit as st

from repo import graph_repo
from core import approval
from ui.components import image_viewer, status_badge


def render():
    st.header("审批中心")
    pendings = graph_repo.get_pending_approvals()
    if not pendings:
        st.success("暂无待审节点")
        return
    labels = sorted({n["label"] for n in pendings})
    sel = st.selectbox("按类型筛选", ["全部"] + labels)
    items = [n for n in pendings if sel == "全部" or n["label"] == sel]
    for n in items:
        full = graph_repo.get_node(n["id"]) or {}
        with st.container(border=True):
            st.write(f"**{n['label']}** · {full.get('name', n['id'])}")
            status_badge.render(n["status"])
            if full.get("image_path"):
                image_viewer.render(full["image_path"])
            c1, c2 = st.columns(2)
            with c1:
                if st.button("通过", key=f"ok_{n['id']}"):
                    graph_repo.set_status(n["id"], approval.approve())
                    st.success("已批准（status=11）")
                    st.rerun()
            with c2:
                reason = st.text_input("驳回理由", key=f"r_{n['id']}")
                if st.button("驳回", key=f"no_{n['id']}"):
                    graph_repo.set_status(n["id"], approval.reject())
                    st.warning("已驳回（status=0）" + (f"：{reason}" if reason else ""))
                    st.rerun()
```

- [ ] **Step 2: Commit**

```bash
git add 55_dashboard/ui/page_approval.py
git commit -m "feat(dashboard): 审批中心"
```

---

## Task 14: ui/page_character.py（角色详情 + DAG）

**Files:**
- Create: `55_dashboard/ui/page_character.py`

**Interfaces:**
- Produces: `render(schema, char_id)`。

- [ ] **Step 1: 实现**

`55_dashboard/ui/page_character.py`:
```python
"""角色详情：美术链 DAG + 进「推进」按钮 + 点节点进编辑器。"""
import streamlit as st

from repo import graph_repo
from ui.components import status_badge, launch_button


def render(schema, char_id):
    char = graph_repo.get_node(char_id)
    if not char:
        st.error("角色不存在")
        return
    st.header(f"角色：{char.get('name', char_id)}")
    launch_button.render(char_id)

    g = graph_repo.get_character_graph(char_id)
    _draw_dag(g)
    st.divider()
    st.subheader("节点列表")
    for n in g["nodes"]:
        if n["label"] == "Character":
            continue
        c1, c2, c3 = st.columns([4, 2, 1])
        c1.write(f"{n['label']} · {n.get('name', n['id'])}")
        status_badge.render(n["status"])
        if c3.button("编辑", key=f"ed_{n['id']}"):
            st.session_state["edit_node"] = n["id"]
            st.session_state["page"] = "节点编辑器"
            st.rerun()


def _draw_dag(g):
    """生成 dot 字符串交 st.graphviz_chart（前端 viz.js 渲染，无需 graphviz 包）；失败回退树形。"""
    lines = ["digraph G {"]
    for n in g["nodes"]:
        lines.append(f'  "{n["id"]}" [label="{n["label"]}\\n{status_badge.badge_text(n["status"])}"];')
    for e in g["edges"]:
        lines.append(f'  "{e["from"]}" -> "{e["to"]}" [label="{e["type"]}"];')
    lines.append("}")
    try:
        st.graphviz_chart("\n".join(lines))
    except Exception:
        st.warning("DAG 图渲染失败，回退树形列表")
        for n in g["nodes"]:
            st.write(f"- {n['label']}（{status_badge.badge_text(n['status'])}）")
```

- [ ] **Step 2: Commit**

```bash
git add 55_dashboard/ui/page_character.py
git commit -m "feat(dashboard): 角色详情 DAG"
```

---

## Task 15: ui/page_overview.py（进度看板）

**Files:**
- Create: `55_dashboard/ui/page_overview.py`

**Interfaces:**
- Produces: `render()`。

- [ ] **Step 1: 实现**

`55_dashboard/ui/page_overview.py`:
```python
"""进度看板：统计 + 角色列表（含「推进」按钮）。"""
import streamlit as st

from repo import graph_repo
from ui.components import launch_button, status_badge


def render():
    st.header("美术进度看板")
    chars = graph_repo.get_nodes("Character")
    pendings = graph_repo.get_pending_approvals()
    c1, c2, c3 = st.columns(3)
    c1.metric("角色数", len(chars))
    c2.metric("待审节点", len(pendings))
    redo = sum(1 for ch in chars for _ in _redo_count(ch["id"]))
    c3.metric("需重做节点", redo)

    st.divider()
    for ch in chars:
        with st.container(border=True):
            col1, col2 = st.columns([6, 2])
            col1.write(f"**{ch.get('name', ch['id'])}**")
            launch_button.render(ch["id"])
            _char_status_line(col2, ch["id"])


def _redo_count(char_id):
    g = graph_repo.get_character_graph(char_id)
    return [n for n in g["nodes"] if n["label"] != "Character" and n["status"] == 0]


def _char_status_line(col, char_id):
    g = graph_repo.get_character_graph(char_id)
    parts = [f"{n['label']}:{status_badge.badge_text(n['status'])}"
             for n in g["nodes"] if n["label"] != "Character"]
    col.caption(" ｜ ".join(parts) if parts else "无美术节点")
```

- [ ] **Step 2: Commit**

```bash
git add 55_dashboard/ui/page_overview.py
git commit -m "feat(dashboard): 进度看板"
```

---

## Task 16: app.py（入口与路由）

**Files:**
- Create: `55_dashboard/app.py`

- [ ] **Step 1: 实现**

`55_dashboard/app.py`:
```python
"""55_dashboard 入口：侧边栏导航 + 页面路由。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 让 `config`/`repo`/... 可导入

import streamlit as st

from config import settings
from core.schema_loader import load_schema
from repo import graph_repo
from ui import page_overview, page_character, page_node_editor, page_approval

st.set_page_config(page_title="代恋 · 美术治理后台", layout="wide")

# 启动加载 Schema（带启动校验）
try:
    SCHEMA = load_schema(settings.SCHEMA_DIR, settings.TAG_LIB_PATH)
except Exception as e:
    st.error(f"Schema 加载失败：{e}")
    st.stop()

st.sidebar.title("导航")
if "page" not in st.session_state:
    st.session_state["page"] = "进度看板"
page = st.sidebar.radio(
    "页面",
    ["进度看板", "角色详情", "节点编辑器", "审批中心", "剧情（TODO）", "场景美术（TODO）"],
    key="page",
)

if page in ("剧情（TODO）", "场景美术（TODO）"):
    st.info(f"{page}：Schema 待定义，V1 暂未实现。")

if page == "进度看板":
    page_overview.render()
elif page == "角色详情":
    chars = graph_repo.get_nodes("Character")
    names = [c.get("name", c["id"]) for c in chars]
    sel = st.selectbox("选择角色", names) if names else None
    if sel:
        ch = next(c for c in chars if c.get("name", c["id"]) == sel)
        page_character.render(SCHEMA, ch["id"])
elif page == "节点编辑器":
    default_id = st.session_state.get("edit_node", "")
    nid = st.text_input("节点 ID", value=default_id)
    if nid:
        page_node_editor.render(SCHEMA, nid.strip())
elif page == "审批中心":
    page_approval.render()
```

- [ ] **Step 2: 手动启动验证**

Run（需要 Neo4j 在线且 `.env` 配好）:
```bash
cd 55_dashboard && streamlit run app.py
```
Expected: 浏览器打开，侧边栏 6 项可点；「剧情」「场景美术」显示 TODO 提示；其余页面不报导入错误。

- [ ] **Step 3: Commit**

```bash
git add 55_dashboard/app.py
git commit -m "feat(dashboard): app 入口与页面路由"
```

---

## Task 17: 标签库迁移与文档引用更新

**Files:**
- Move: `55_manage/标签库.json` → `55_dashboard/config/标签库.json`
- Modify: `00_init/Schema/角色美术.md`（更新两处引用链接）

- [ ] **Step 1: 迁移标签库**

Run:
```bash
git mv 55_manage/标签库.json 55_dashboard/config/标签库.json
```
若 55_manage 目录变空，可保留或删除（按需）。

- [ ] **Step 2: 更新 Schema 文档引用**

在 `00_init/Schema/角色美术.md` 中，把指向 `55_manage/标签库.json` 的链接改为 `55_dashboard/config/标签库.json`。共两处（角色美术.md 顶部说明 + 任意正文引用）。搜索确认：
```bash
grep -rn "55_manage/标签库.json" 00_init/
```
逐处替换为 `55_dashboard/config/标签库.json`。

- [ ] **Step 3: 验证后台仍能加载标签库**

Run:
```bash
cd 55_dashboard && python -c "from core.schema_loader import load_schema; from config import settings; sd=load_schema(settings.SCHEMA_DIR, settings.TAG_LIB_PATH); assert 'AppearanceStyle' in sd.tag_fields; print('标签库加载 OK')"
```
Expected: 输出 `标签库加载 OK`。

- [ ] **Step 4: Commit**

```bash
git add 55_dashboard/config/标签库.json 00_init/Schema/角色美术.md
git rm 55_manage/标签库.json 2>/dev/null; true
git commit -m "chore(dashboard): 标签库迁入 55_dashboard/config 并更新引用"
```

---

## 验收对照（对应设计文档第 8 节）

1. 启动后台看到角色及美术链进度 → Task 15 + 16。
2. 节点编辑器改属性保存 → 写库 + 11→0 回退 + 级联 → Task 12 + 6 + 5。
3. 审批中心通过/驳回 → Task 13 + 6。
4. 编辑器提交审批 → Task 12（submit）。
5. 图片预览 → Task 11。
6. 剧情/场景美术禁用 + TODO → Task 16。
7. 「推进」按钮打开预填 char-design 标签页 → Task 7 + 12/14/15。

## 全量测试

Run:
```bash
cd 55_dashboard && python -m pytest -v
```
Expected: 所有 core/ui 纯函数测试通过（约 25 项）；repo 集成方法在真实库上手动验证。
