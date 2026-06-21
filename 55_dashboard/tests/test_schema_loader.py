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


def test_load_schema_merges_tag_fields(tmp_path):
    import json
    md = tmp_path / "t.md"
    md.write_text(SAMPLE_MD)
    tag = tmp_path / "tag.json"
    tag.write_text(json.dumps({"Character": {"gender": {"label": "性别", "multi": False, "options": ["男", "女"]}}}))
    sd = schema_loader.load_schema(str(tmp_path), str(tag))
    assert "Character" in sd.nodes
    assert "gender" in sd.tag_fields["Character"]


def test_parse_md_ignores_edge_header_tables():
    """边标题（### relation — ... `N:N`）不匹配 NODE_HEADER_RE，
    其后的边属性表（type/detail/sync/...）不应污染前一个节点的 fields。"""
    md = """### 角色（Character）

| 字段 | 中文 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| name | 姓名 | string | 是 | 陆择 |
| gender | 性别 | enum | 否 | 男 |

### relation — 人物关系 `N:N`

| 字段 | 中文 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| type | 关系类型 | string | 是 | 朋友 |
| detail | 关系描述 | string | 否 | 发小 |
| sync | 同步 | bool | 是 | true |
"""
    nodes = schema_loader.parse_md(md)
    char = nodes["Character"]
    names = [f.name for f in char.fields]
    assert names == ["name", "gender"]
    assert "type" not in names
    assert "detail" not in names
    assert "sync" not in names


def test_load_schema_rejects_bad_table(tmp_path):
    bad = "# X\n### 坏（Bad）\n| 只有 | 一列 |\n"
    (tmp_path / "b.md").write_text(bad)
    try:
        schema_loader.load_schema(str(tmp_path), None)
    except schema_loader.SchemaError:
        return
    raise AssertionError("应抛 SchemaError")
