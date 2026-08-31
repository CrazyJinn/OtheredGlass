"""YAML↔JSON 转换与 YAML 校验的 round-trip 测试。

覆盖：
- YAML 章节能通过 schema 校验（验证 validate_chapter 后缀分流）
- yaml_to_chapter_json 转换无损（深比较）
- YAML 1.1 bool 陷阱防护（双引号 string 不被误解析为 bool）
- 多行文本双引号 + \\n 转换后不漂移
"""
import json
from pathlib import Path

import yaml

from validate_chapter import validate_chapter
from yaml_to_chapter_json import convert

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = str(ROOT / "data" / "剧本.schema.json")


def _sample_yaml() -> str:
    """构造一个合法的最小章节 YAML，覆盖 narrate/say/ending 与多行文本。"""
    return (
        'meta:\n'
        '  chapter: 99\n'
        '  title: "测试章节"\n'
        '  requires:\n'
        '    characters: ["甲"]\n'
        '    scenes: ["室内"]\n'
        'scenes:\n'
        '  - id: "s1"\n'
        '    scene: "室内"\n'
        '    time: "白天"\n'
        '    lines:\n'
        '      - { op: "narrate", text: "一句话。\\n第二行。" }\n'
        '      - { op: "say", who: "甲", portrait: "默认", pos: "left", text: "yes" }\n'
        '      - { op: "ending", kind: "NE" }\n'
    )


def test_yaml_validates_against_schema(tmp_path):
    p = tmp_path / "ch.yaml"
    p.write_text(_sample_yaml(), encoding="utf-8")
    ok, errors = validate_chapter(str(p), SCHEMA)
    assert ok, errors


def test_yaml_to_json_roundtrip_preserves_data(tmp_path):
    src = tmp_path / "ch.yaml"
    src.write_text(_sample_yaml(), encoding="utf-8")
    dest = tmp_path / "out" / "ch.json"
    convert(str(src), str(dest))
    with open(src, encoding="utf-8") as f:
        original = yaml.safe_load(f)
    with open(dest, encoding="utf-8") as f:
        converted = json.load(f)
    assert original == converted


def test_yaml_11_bool_trap_string_stays_quoted(tmp_path):
    """YAML 1.1 会把裸 yes/no/on/off 解析为 bool。规则要求 string 双引号，
    这里验证双引号的 'yes' 保持为 str（say 文本）。"""
    p = tmp_path / "ch.yaml"
    p.write_text(_sample_yaml(), encoding="utf-8")
    ok, errors = validate_chapter(str(p), SCHEMA)
    assert ok, errors
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    say_line = doc["scenes"][0]["lines"][1]
    assert say_line["text"] == "yes"
    assert isinstance(say_line["text"], str)


def test_multiline_text_newline_preserved(tmp_path):
    """多行文本用双引号 + \\n，转换后换行不漂移。"""
    src = tmp_path / "ch.yaml"
    src.write_text(_sample_yaml(), encoding="utf-8")
    dest = tmp_path / "ch.json"
    convert(str(src), str(dest))
    with open(dest, encoding="utf-8") as f:
        doc = json.load(f)
    narrate = doc["scenes"][0]["lines"][0]
    assert narrate["text"] == "一句话。\n第二行。"
