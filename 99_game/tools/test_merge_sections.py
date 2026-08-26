"""merge_sections_to_chapter 单测：N 节台词 JSONL 合并 → 章级 JSON（演出由图注入）。

覆盖：
- 2 节合并：scenes[] 顺序 = 节序、requires 并集、id 保持唯一
- 跨节 jump（节1 choice scene:<节2 段id>）合并后仍合法
- 合并产物通过 schema 校验
- scene-block id 重复时报错（防御 structurer 预分配失败）
- chapter-map：portrait 整键改写 + requires 重推导 + BGM 注入 scene-block
"""
import json
import sys
from pathlib import Path

import pytest

from merge_sections_to_chapter import merge
from validate_chapter import validate_chapter

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = str(ROOT / "data" / "剧本.schema.json")
_SCRIPTS = ROOT.parent / ".claude" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import jsonl_script  # noqa: E402


def _sec_rows(chapter, title, scene_id, scene_name, lines, characters=None, portraits=None):
    """构造一节最小合法台词 rows（meta + scene 分隔行 + 台词行带行 id 与水位）。"""
    rows = [
        {"op": "meta", "chapter": chapter, "title": title,
         "requires": {"characters": characters or [], "scenes": [scene_name],
                      "portraits": portraits or []},
         "line_seq": 1 + len(lines)},
        {"op": "scene", "id": scene_id, "scene": scene_name},
    ]
    for i, line in enumerate(lines, 1):
        rows.append({"id": f"L{i:04d}", **line})
    return rows


def _write_jsonl(tmp_path, name, rows):
    p = tmp_path / name
    jsonl_script.save(p, rows)
    return str(p)


def _dump_validate(doc, tmp_path):
    out = tmp_path / "ch.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return validate_chapter(str(out), SCHEMA)


def test_merge_two_sections_concat_scenes_and_union_requires(tmp_path):
    sec1 = _sec_rows(1, "节1", "s01_桥上", "长江大桥-栏杆",
                     [{"op": "narrate", "text": "夜风。"}],
                     characters=["陈默"], portraits=["陈默.沉重"])
    sec2 = _sec_rows(1, "节2", "s02_出租屋", "出租屋",
                     [{"op": "say", "who": "陈默", "portrait": "疲惫", "pos": "center", "text": "回来了。"}],
                     characters=["陈默", "陆择"], portraits=["陈默.疲惫"])
    p1 = _write_jsonl(tmp_path, "sec1.jsonl", sec1)
    p2 = _write_jsonl(tmp_path, "sec2.jsonl", sec2)

    doc = merge([p1, p2], chapter=1, title="新皮肤·Day0")

    # scenes 按节序拼接，id 唯一
    assert [s["id"] for s in doc["scenes"]] == ["s01_桥上", "s02_出租屋"]
    # requires 并集保序去重（陈默 不重复）
    assert doc["meta"]["requires"]["characters"] == ["陈默", "陆择"]
    assert doc["meta"]["requires"]["scenes"] == ["长江大桥-栏杆", "出租屋"]
    assert doc["meta"]["requires"]["portraits"] == ["陈默.沉重", "陈默.疲惫"]
    # meta chapter/title 取 CLI 参数；台词行 id/audio 已被投影丢弃
    assert doc["meta"]["chapter"] == 1
    assert doc["meta"]["title"] == "新皮肤·Day0"
    assert "id" not in doc["scenes"][0]["lines"][0]


def test_merge_cross_section_jump_validates(tmp_path):
    """节1 choice 跳到节2 的段 id（跨节 jump，拍平后同章内 scene: 寻址）。"""
    sec1 = _sec_rows(1, "节1", "s01_桥上", "长江大桥-栏杆", [
        {"op": "choice", "options": [
            {"label": "跳下", "scene": "s02_出租屋", "leads_to_ending": True},
            {"label": "再想", "to": "keep"},
        ]},
        {"op": "label", "name": "keep"},
        {"op": "narrate", "text": "风停了。"},
    ])
    sec2 = _sec_rows(1, "节2", "s02_出租屋", "出租屋", [
        {"op": "narrate", "text": "结局。"},
        {"op": "ending", "kind": "BE"},
    ])
    p1 = _write_jsonl(tmp_path, "sec1.jsonl", sec1)
    p2 = _write_jsonl(tmp_path, "sec2.jsonl", sec2)

    doc = merge([p1, p2], chapter=1, title="新皮肤")
    ok, errors = _dump_validate(doc, tmp_path)
    assert ok, errors


def test_merge_rejects_duplicate_scene_id(tmp_path):
    sec1 = _sec_rows(1, "节1", "路口", "马路-路口", [{"op": "narrate", "text": "a"}])
    sec2 = _sec_rows(1, "节2", "路口", "出租屋", [{"op": "narrate", "text": "b"}])  # 与节1 id 重复
    p1 = _write_jsonl(tmp_path, "sec1.jsonl", sec1)
    p2 = _write_jsonl(tmp_path, "sec2.jsonl", sec2)

    with pytest.raises(ValueError, match="重复"):
        merge([p1, p2], chapter=1, title="x")


def test_merge_handles_missing_requires(tmp_path):
    """节 meta 缺 requires 时不崩（视作空并集）。"""
    rows = [
        {"op": "meta", "chapter": 1, "title": "节1", "line_seq": 2},
        {"op": "scene", "id": "s1", "scene": "室内"},
        {"id": "L0001", "op": "ending", "kind": "TE"},
    ]
    p = _write_jsonl(tmp_path, "sec.jsonl", rows)
    doc = merge([p], chapter=1, title="章")
    assert doc["meta"]["requires"] == {"characters": [], "scenes": [], "portraits": []}
    assert len(doc["scenes"]) == 1


def test_merge_with_chapter_map_rewrites_portrait_and_injects_bgm(tmp_path):
    """带 chapter_map：say.portrait 从纯变体改写为 guid 整键 + requires 重推导 + bgm 注入。"""
    sec1 = _sec_rows(0, "sec00", "酒店", "酒店-客房", [
        {"op": "say", "who": "陆择", "portrait": "慵懒", "pos": "left", "text": "呵。"},
        {"op": "say", "who": "陆择", "portrait": "玩味", "pos": "left", "text": "醒了？"},
    ], characters=["陆择"], portraits=["陆择.慵懒", "陆择.玩味"])
    sec2 = _sec_rows(0, "sec01", "咖啡店", "街角咖啡店-点餐台", [
        {"op": "say", "who": "陆择", "portrait": "慵懒", "pos": "left", "text": "美式。"},
    ], characters=["陆择"], portraits=["陆择.慵懒"])
    p1 = _write_jsonl(tmp_path, "sec1.jsonl", sec1)
    p2 = _write_jsonl(tmp_path, "sec2.jsonl", sec2)

    chapter_map = {
        "portraits": {
            "酒店-客房": {"陆择": {"慵懒": "陆择-赤裸上身-慵懒-PHSE4iftNQ",
                                        "玩味": "陆择-赤裸上身-玩味-PHSE4iftNR"}},
            "街角咖啡店-点餐台": {"陆择": {"慵懒": "陆择-商务休闲着装-慵懒-PJajqyM6s4"}},
        },
        "bgm": {"酒店-客房": {"track": "晨离", "mode": "play", "loop": True}},
    }
    doc = merge([p1, p2], chapter=0, title="序章", chapter_map=chapter_map)

    # sec00 陆择 portrait 改为赤裸上身整键（两句各自命中）
    assert doc["scenes"][0]["lines"][0]["portrait"] == "陆择-赤裸上身-慵懒-PHSE4iftNQ"
    assert doc["scenes"][0]["lines"][1]["portrait"] == "陆择-赤裸上身-玩味-PHSE4iftNR"
    # sec01 陆择.慵懒 改为商务休闲整键（同名变体不同键 → 不冲突）；该场景无 BGM 映射 → 不注入
    assert doc["scenes"][1]["lines"][0]["portrait"] == "陆择-商务休闲着装-慵懒-PJajqyM6s4"
    assert "bgm" not in doc["scenes"][1]
    # BGM 注入到酒店-客房 scene-block（台词文件不写演出，由图推导）
    assert doc["scenes"][0]["bgm"] == {"track": "晨离", "mode": "play", "loop": True}
    # requires.portraits 从改写后 lines 重推导（保序去重）
    assert doc["meta"]["requires"]["portraits"] == [
        "陆择-赤裸上身-慵懒-PHSE4iftNQ",
        "陆择-赤裸上身-玩味-PHSE4iftNR",
        "陆择-商务休闲着装-慵懒-PJajqyM6s4",
    ]
    # 产物过 schema（整键含中文+字母数字，type:string 允许）
    ok, errors = _dump_validate(doc, tmp_path)
    assert ok, errors


def test_merge_chapter_map_unknown_scene_ignored(tmp_path):
    """map 含本章不存在的 scene → 不报错、不影响（portrait 保持原值并进 requires）。"""
    rows = _sec_rows(0, "s", "s1", "室内", [
        {"op": "say", "who": "陆择", "portrait": "慵懒", "pos": "center", "text": "x"},
    ], characters=["陆择"], portraits=["陆择.慵懒"])
    p = _write_jsonl(tmp_path, "sec.jsonl", rows)
    chapter_map = {"portraits": {"不存在场景": {"陆择": {"慵懒": "X-Y-Z-I"}}}, "bgm": {}}
    doc = merge([p], chapter=0, title="x", chapter_map=chapter_map)
    assert doc["scenes"][0]["lines"][0]["portrait"] == "慵懒"  # 未命中，不改写
    assert doc["meta"]["requires"]["portraits"] == ["慵懒"]


def test_merge_without_chapter_map_keeps_pure_concat(tmp_path):
    """无 chapter_map：纯拼接（requires 取各节并集，portrait 不改写、无 bgm 注入）。"""
    rows = _sec_rows(0, "s", "s1", "室内", [
        {"op": "say", "who": "陆择", "portrait": "慵懒", "pos": "center", "text": "x"},
    ], characters=["陆择"], portraits=["陆择.慵懒"])
    p = _write_jsonl(tmp_path, "sec.jsonl", rows)
    doc = merge([p], chapter=0, title="x")  # 不传 chapter_map
    assert doc["scenes"][0]["lines"][0]["portrait"] == "慵懒"
    assert doc["meta"]["requires"]["portraits"] == ["陆择.慵懒"]
