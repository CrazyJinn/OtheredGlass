"""merge_sections_to_chapter 单测：图行投影 → N 节合并 → 章级 JSON（演出由图注入）。

覆盖：
- graph_lines_to_doc：图行（LineAudio 形状）→ 投影 doc（label→name、
  ending→kind+title、voice_key→voice、say.portrait = uses 边解析的整键、requires 从行推导）
- 2 节合并：scenes[] 顺序 = 节序、requires 并集、id 保持唯一
- 合并产物通过 schema 校验
- scene-block id 重复时报错（防御 structurer 预分配失败）
- chapter-map：仅 bgm 段注入 scene-block（portrait 已在投影期沿 uses 解析）

fetch_chapter / fetch_uses_portrait_keys（图查询 + 前置校验）不连库，端到端验证。
"""
import json
from pathlib import Path

import pytest

from merge_sections_to_chapter import graph_lines_to_doc, merge
from validate_chapter import validate_chapter

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = str(ROOT / "data" / "剧本.schema.json")


def _line(op, text=None, *, who=None, pos=None, kind=None,
          scene_block_id=None, voice_key=None, lid="N1", ambient_track=None):
    """图行 dict（fetch_chapter 查询返回形状——portrait 已不在 RETURN 列）。"""
    return {"lid": lid, "op": op, "who": who, "pos": pos,
            "text": text, "kind": kind, "scene_block_id": scene_block_id,
            "voice_key": voice_key, "ambient_track": ambient_track, "line_status": 11}


def _blocks(*pairs):
    """scene_blocks（[{block, scene_name}]）。"""
    return [{"block": b, "scene_name": s} for b, s in pairs]


def _dump_validate(doc, tmp_path):
    out = tmp_path / "ch.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return validate_chapter(str(out), SCHEMA)


# ── graph_lines_to_doc 投影 ──

def test_graph_lines_to_doc_projects_uses_portrait_key():
    """portrait_keys（uses 边解析）→ say.portrait 整键 + requires 收集。"""
    lines = [
        _line("narrate", "清晨。", scene_block_id="s00_酒店", lid="N1"),
        _line("say", "醒这么早？", who="顾盈", pos="left", scene_block_id="s00_酒店",
              voice_key="顾盈-chapter00_序章-s00_酒店-N2", lid="N2"),
        _line("label", "留下", scene_block_id="s00_酒店", lid="N3"),
        _line("ending", "没赶上飞机", kind="BE", scene_block_id="s00_酒店", lid="N4"),
    ]
    keys = {"N2": "顾盈-酒店晨离-挑眉-P2vQL2d9db"}
    doc = graph_lines_to_doc(lines, _blocks(("s00_酒店", "酒店-客房")),
                             {"酒店-客房": "清晨"}, 0, "酒店醒来", portrait_keys=keys)
    assert doc["meta"]["chapter"] == 0 and doc["meta"]["title"] == "酒店醒来"
    assert doc["meta"]["requires"] == {"characters": ["顾盈"], "scenes": ["酒店-客房"],
                                       "portraits": ["顾盈-酒店晨离-挑眉-P2vQL2d9db"]}
    blk = doc["scenes"][0]
    assert blk["id"] == "s00_酒店" and blk["scene"] == "酒店-客房" and blk["time"] == "清晨"
    assert blk["lines"][0] == {"op": "narrate", "text": "清晨。"}
    say = blk["lines"][1]
    assert say["voice"] == "顾盈-chapter00_序章-s00_酒店-N2"   # voice_key → voice
    assert say["portrait"] == "顾盈-酒店晨离-挑眉-P2vQL2d9db" and say["pos"] == "left"
    assert blk["lines"][2] == {"op": "label", "name": "留下"}   # label text → name
    assert blk["lines"][3] == {"op": "ending", "kind": "BE", "title": "没赶上飞机"}


def test_graph_lines_to_doc_missing_key_empty_and_excluded_from_requires():
    """无 uses 边的 say 行：portrait 空串（运行时占位图兜底）且不进 requires。"""
    lines = [_line("say", "x", who="陆择", scene_block_id="s1", lid="N1")]
    doc = graph_lines_to_doc(lines, _blocks(("s1", "室内")), {}, 1, "节")
    say = doc["scenes"][0]["lines"][0]
    assert say["portrait"] == "" and say["pos"] == "left" and "voice" not in say
    assert doc["meta"]["requires"]["portraits"] == []
    assert doc["meta"]["requires"]["characters"] == ["陆择"]


def test_graph_lines_to_doc_blocks_drive_scene_structure():
    """scene-block 结构来自 scene_blocks（scene 行已去图化），行按块归属归块。"""
    lines = [
        _line("say", "屋里。", who="陆择", scene_block_id="s0", lid="N1"),
        _line("say", "外面。", who="陆择", scene_block_id="s1", lid="N2"),
    ]
    doc = graph_lines_to_doc(lines, _blocks(("s0", "室内"), ("s1", "马路-路口")),
                             {}, 0, "节")
    assert [b["id"] for b in doc["scenes"]] == ["s0", "s1"]
    assert doc["scenes"][0]["lines"][0]["text"] == "屋里。"
    assert doc["scenes"][1]["lines"][0]["text"] == "外面。"
    assert doc["meta"]["requires"]["scenes"] == ["室内", "马路-路口"]


# ── 环境音两型投影（transition 独立行 / ambience 挂 narrate）──

def test_transition_line_projects_transition_op():
    """转场音效独立行（op=transition，存量 ambient 兜底归一）→ {"op":"transition","track"}。"""
    lines = [
        _line("narrate", "街角的咖啡店。", scene_block_id="s01", lid="N1"),
        _line("transition", "推门时门口的风铃清脆作响",
              ambient_track="amb-ch0-s01-P1", scene_block_id="s01", lid="N2"),
        _line("ambient", "存量旧行", ambient_track="amb-ch0-s01-P0",
              scene_block_id="s01", lid="N3"),  # 存量值兜底归一
    ]
    doc = graph_lines_to_doc(lines, _blocks(("s01", "咖啡店")), {}, 0, "节")
    ls = doc["scenes"][0]["lines"]
    assert ls[0] == {"op": "narrate", "text": "街角的咖啡店。"}   # 纯 narrate 无 ambience 键
    assert ls[1] == {"op": "transition", "track": "amb-ch0-s01-P1"}
    assert ls[2] == {"op": "transition", "track": "amb-ch0-s01-P0"}  # 存量归一


def test_narrate_with_ambient_track_projects_ambience_key():
    """氛围声景（narrate+ambient_track）→ narrate 行带 ambience 键（不再拍平成独立行）。"""
    lines = [
        _line("narrate", "雨点骤然砸落", ambient_track="amb-ch0-s01-P2",
              scene_block_id="s01", lid="N1"),
    ]
    doc = graph_lines_to_doc(lines, _blocks(("s01", "马路-路口")), {}, 0, "节")
    assert doc["scenes"][0]["lines"] == [
        {"op": "narrate", "text": "雨点骤然砸落", "ambience": "amb-ch0-s01-P2"}]


# ── merge ──

def test_merge_two_sections_concat_scenes_and_union_requires():
    key1 = "陈默-日常-沉重-Ab00000001"
    key2 = "陈默-日常-疲惫-Ab00000002"
    key3 = "陆择-日常-平静-Ab00000003"
    sec1 = graph_lines_to_doc(
        [_line("say", "夜风。", who="陈默", pos="center", scene_block_id="s01_桥上", lid="N1")],
        _blocks(("s01_桥上", "长江大桥-栏杆")), {}, 1, "节1",
        portrait_keys={"N1": key1})
    sec2 = graph_lines_to_doc(
        [_line("say", "回来了。", who="陈默", pos="center", scene_block_id="s02_出租屋", lid="N2"),
         _line("say", "嗯。", who="陆择", pos="left", scene_block_id="s02_出租屋", lid="N3")],
        _blocks(("s02_出租屋", "出租屋")), {}, 1, "节2",
        portrait_keys={"N2": key2, "N3": key3})

    doc = merge([sec1, sec2], chapter=1, title="新皮肤·Day0")
    assert [s["id"] for s in doc["scenes"]] == ["s01_桥上", "s02_出租屋"]
    assert doc["meta"]["requires"]["characters"] == ["陈默", "陆择"]      # 并集保序去重
    assert doc["meta"]["requires"]["scenes"] == ["长江大桥-栏杆", "出租屋"]
    assert doc["meta"]["requires"]["portraits"] == [key1, key2, key3]    # 整键并集
    assert doc["meta"]["chapter"] == 1 and doc["meta"]["title"] == "新皮肤·Day0"


def test_merge_validates_against_schema(tmp_path):
    """图行投影合并产物通过运行时章 JSON schema（ending/label/narrate/say 全行型）。"""
    sec1 = graph_lines_to_doc(
        [_line("narrate", "风停了。", scene_block_id="s01_桥上", lid="N1"),
         _line("label", "keep", scene_block_id="s01_桥上", lid="N2"),
         _line("ending", "一切照旧", kind="TE", scene_block_id="s01_桥上", lid="N3")],
        _blocks(("s01_桥上", "长江大桥-栏杆")), {}, 1, "节1")
    doc = merge([sec1], chapter=1, title="新皮肤")
    ok, errors = _dump_validate(doc, tmp_path)
    assert ok, errors


def test_merge_rejects_duplicate_scene_id():
    sec1 = graph_lines_to_doc(
        [_line("narrate", "a", scene_block_id="路口", lid="N1")],
        _blocks(("路口", "马路-路口")), {}, 1, "节1")
    sec2 = graph_lines_to_doc(
        [_line("narrate", "b", scene_block_id="路口", lid="N2")],
        _blocks(("路口", "出租屋")), {}, 1, "节2")   # 与节1 id 重复
    with pytest.raises(ValueError, match="重复"):
        merge([sec1, sec2], chapter=1, title="x")


def test_merge_with_chapter_map_injects_bgm_only(tmp_path):
    """带 chapter_map（现仅 bgm 段）：portrait 已是投影期整键，map 只注入 BGM。"""
    key = "陆择-赤裸上身-慵懒-PHSE4iftNQ"
    sec1 = graph_lines_to_doc(
        [_line("say", "呵。", who="陆择", pos="left", scene_block_id="酒店", lid="N1"),
         _line("say", "醒了？", who="陆择", pos="left", scene_block_id="酒店", lid="N2")],
        _blocks(("酒店", "酒店-客房")), {}, 0, "sec00",
        portrait_keys={"N1": key, "N2": key})
    sec2 = graph_lines_to_doc(
        [_line("say", "美式。", who="陆择", pos="left", scene_block_id="咖啡店", lid="N3")],
        _blocks(("咖啡店", "街角咖啡店-点餐台")), {}, 0, "sec01",
        portrait_keys={"N3": "陆择-商务休闲-慵懒-PJajqyM6s4"})

    chapter_map = {"bgm": {"酒店-客房": {"track": "晨离", "mode": "play", "loop": True}}}
    doc = merge([sec1, sec2], chapter=0, title="序章", chapter_map=chapter_map)

    # portrait 不受 map 影响（投影期已解析）；BGM 注入到酒店-客房 scene-block
    assert doc["scenes"][0]["lines"][0]["portrait"] == key
    assert doc["scenes"][0]["bgm"] == {"track": "晨离", "mode": "play", "loop": True}
    assert "bgm" not in doc["scenes"][1]                      # 该场景无 BGM 映射 → 不注入
    assert doc["meta"]["requires"]["portraits"] == [
        key, "陆择-商务休闲-慵懒-PJajqyM6s4"]
    ok, errors = _dump_validate(doc, tmp_path)
    assert ok, errors


def test_merge_without_chapter_map_keeps_pure_concat():
    """无 chapter_map：纯拼接（requires 取各节并集，无 bgm 注入）。"""
    key = "陆择-赤裸上身-慵懒-PHSE4iftNQ"
    sec = graph_lines_to_doc(
        [_line("say", "x", who="陆择", pos="center", scene_block_id="s1", lid="N1")],
        _blocks(("s1", "室内")), {}, 0, "s", portrait_keys={"N1": key})
    doc = merge([sec], chapter=0, title="x")  # 不传 chapter_map
    assert doc["scenes"][0]["lines"][0]["portrait"] == key
    assert doc["meta"]["requires"]["portraits"] == [key]
    assert "bgm" not in doc["scenes"][0]
