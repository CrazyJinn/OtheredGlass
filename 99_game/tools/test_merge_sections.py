"""merge_sections_to_chapter 单测：N 节合并 → 章级 JSON。

覆盖：
- 2 节合并：scenes[] 顺序 = 节序、requires 并集、id 保持唯一
- 跨节 jump（节1 choice scene:<节2 段id>）合并后仍合法
- 合并产物通过 schema 校验
- scene-block id 重复时报错（防御 structurer 预分配失败）
"""
import json
from pathlib import Path

import pytest

from merge_sections_to_chapter import merge
from validate_chapter import validate_chapter

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = str(ROOT / "data" / "剧本.schema.json")


def _sec(chapter, title, scene_id, scene_name, lines, characters=None, portraits=None):
    """构造一节最小合法定稿 dict。"""
    return {
        "meta": {
            "chapter": chapter,
            "title": title,
            "requires": {
                "characters": characters or [],
                "scenes": [scene_name],
                "portraits": portraits or [],
            },
        },
        "scenes": [{"id": scene_id, "scene": scene_name, "lines": lines}],
    }


def _write_yaml(tmp_path, name, doc):
    import yaml
    p = tmp_path / name
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
    return str(p)


def test_merge_two_sections_concat_scenes_and_union_requires(tmp_path):
    sec1 = _sec(1, "节1", "s01_桥上", "长江大桥-栏杆",
                [{"op": "narrate", "text": "夜风。"}],
                characters=["陈默"], portraits=["陈默.沉重"])
    sec2 = _sec(1, "节2", "s02_出租屋", "出租屋",
                [{"op": "say", "who": "陈默", "portrait": "疲惫", "pos": "center", "text": "回来了。"}],
                characters=["陈默", "陆择"], portraits=["陈默.疲惫"])
    p1 = _write_yaml(tmp_path, "sec1.yaml", sec1)
    p2 = _write_yaml(tmp_path, "sec2.yaml", sec2)

    doc = merge([p1, p2], chapter=1, title="新皮肤·Day0")

    # scenes 按节序拼接，id 唯一
    assert [s["id"] for s in doc["scenes"]] == ["s01_桥上", "s02_出租屋"]
    # requires 并集保序去重（陈默 不重复）
    assert doc["meta"]["requires"]["characters"] == ["陈默", "陆择"]
    assert doc["meta"]["requires"]["scenes"] == ["长江大桥-栏杆", "出租屋"]
    assert doc["meta"]["requires"]["portraits"] == ["陈默.沉重", "陈默.疲惫"]
    # meta chapter/title 取 CLI 参数
    assert doc["meta"]["chapter"] == 1
    assert doc["meta"]["title"] == "新皮肤·Day0"


def test_merge_cross_section_jump_validates(tmp_path):
    """节1 choice 跳到节2 的段 id（跨节 jump，拍平后同章内 scene: 寻址）。"""
    sec1 = _sec(1, "节1", "s01_桥上", "长江大桥-栏杆", [
        {"op": "choice", "options": [
            {"label": "跳下", "scene": "s02_出租屋", "leads_to_ending": True},
            {"label": "再想", "to": "keep"},
        ]},
        {"op": "label", "name": "keep"},
        {"op": "narrate", "text": "风停了。"},
    ])
    sec2 = _sec(1, "节2", "s02_出租屋", "出租屋", [
        {"op": "narrate", "text": "结局。"},
        {"op": "ending", "kind": "BE"},
    ])
    p1 = _write_yaml(tmp_path, "sec1.yaml", sec1)
    p2 = _write_yaml(tmp_path, "sec2.yaml", sec2)

    doc = merge([p1, p2], chapter=1, title="新皮肤")
    out = tmp_path / "ch.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    ok, errors = validate_chapter(str(out), SCHEMA)
    assert ok, errors


def test_merge_rejects_duplicate_scene_id(tmp_path):
    sec1 = _sec(1, "节1", "路口", "马路-路口", [{"op": "narrate", "text": "a"}])
    sec2 = _sec(1, "节2", "路口", "出租屋", [{"op": "narrate", "text": "b"}])  # 与节1 id 重复
    p1 = _write_yaml(tmp_path, "sec1.yaml", sec1)
    p2 = _write_yaml(tmp_path, "sec2.yaml", sec2)

    with pytest.raises(ValueError, match="重复"):
        merge([p1, p2], chapter=1, title="x")


def test_merge_handles_missing_requires(tmp_path):
    """节 yaml 缺 meta.requires 时不崩（视作空并集）。"""
    sec = {"meta": {"chapter": 1, "title": "节1"},
           "scenes": [{"id": "s1", "scene": "室内", "lines": [{"op": "ending", "kind": "TE"}]}]}
    p = _write_yaml(tmp_path, "sec.yaml", sec)
    doc = merge([p], chapter=1, title="章")
    assert doc["meta"]["requires"] == {"characters": [], "scenes": [], "portraits": []}
    assert len(doc["scenes"]) == 1
