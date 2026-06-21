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
