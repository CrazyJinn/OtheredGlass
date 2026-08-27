"""merge_sections_to_chapter 单测：图行投影 → N 节合并 → 章级 JSON（演出由图注入）。

覆盖：
- graph_lines_to_doc：图行（LineAudio 形状）→ 投影 doc（label→name、
  ending→kind+title、voice_key→voice、requires 从行推导、scene time 取 stages→Scene）
- 2 节合并：scenes[] 顺序 = 节序、requires 并集、id 保持唯一
- 合并产物通过 schema 校验
- scene-block id 重复时报错（防御 structurer 预分配失败）
- chapter-map：portrait 整键改写 + requires 重推导 + BGM 注入 scene-block

fetch_chapter（图查询 + 前置校验）不连库，端到端验证。
"""
import json
import sys
from pathlib import Path

import pytest

from merge_sections_to_chapter import graph_lines_to_doc, merge
from validate_chapter import validate_chapter

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = str(ROOT / "data" / "剧本.schema.json")


def _line(op, text=None, *, who=None, portrait=None, pos=None, kind=None,
          scene_block_id=None, voice_key=None, lid="N1"):
    """图行 dict（fetch_chapter 查询返回形状）。"""
    return {"lid": lid, "op": op, "who": who, "portrait": portrait, "pos": pos,
            "text": text, "kind": kind, "scene_block_id": scene_block_id,
            "voice_key": voice_key, "line_status": 11}


def _sec_lines(scene_id, scene_name, lines, scene_time=None):
    """一节图行序列（scene 行打头）。"""
    return [{"lid": "S", "op": "scene", "scene_block_id": scene_id, "scene_name": scene_name,
             "scene_time": scene_time, "line_status": 11, "who": None, "portrait": None,
             "pos": None, "text": None, "kind": None, "voice_key": None}] + lines


def _dump_validate(doc, tmp_path):
    out = tmp_path / "ch.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return validate_chapter(str(out), SCHEMA)


# ── graph_lines_to_doc 投影 ──

def test_graph_lines_to_doc_projection_details():
    lines = _sec_lines("s00_酒店", "酒店-客房", [
        _line("narrate", "清晨。", lid="N1"),
        _line("say", "醒这么早？", who="顾盈", portrait="挑眉", pos="left",
              voice_key="顾盈-chapter00_序章-s00_酒店-N2", lid="N2"),
        _line("label", "留下", lid="N3"),
        _line("ending", "没赶上飞机", kind="BE", lid="N4"),
    ], scene_time="清晨")
    doc = graph_lines_to_doc(lines, 0, "酒店醒来")
    assert doc["meta"]["chapter"] == 0 and doc["meta"]["title"] == "酒店醒来"
    # requires 从行推导
    assert doc["meta"]["requires"] == {"characters": ["顾盈"], "scenes": ["酒店-客房"],
                                       "portraits": ["挑眉"]}
    blk = doc["scenes"][0]
    assert blk["id"] == "s00_酒店" and blk["scene"] == "酒店-客房" and blk["time"] == "清晨"
    assert blk["lines"][0] == {"op": "narrate", "text": "清晨。"}
    say = blk["lines"][1]
    assert say["voice"] == "顾盈-chapter00_序章-s00_酒店-N2"   # voice_key → voice
    assert say["portrait"] == "挑眉" and say["pos"] == "left"
    assert blk["lines"][2] == {"op": "label", "name": "留下"}   # label text → name
    assert blk["lines"][3] == {"op": "ending", "kind": "BE", "title": "没赶上飞机"}


def test_graph_lines_to_doc_say_defaults_and_unvoiced():
    """portrait 缺省空串 / pos 缺省 left / 未配音行无 voice。"""
    lines = _sec_lines("s1", "室内", [_line("say", "x", who="陆择", lid="N1")])
    doc = graph_lines_to_doc(lines, 1, "节")
    say = doc["scenes"][0]["lines"][0]
    assert say["portrait"] == "" and say["pos"] == "left" and "voice" not in say


# ── merge ──

def test_merge_two_sections_concat_scenes_and_union_requires():
    sec1 = graph_lines_to_doc(_sec_lines("s01_桥上", "长江大桥-栏杆", [
        _line("say", "夜风。", who="陈默", portrait="沉重", pos="center", lid="N1"),
    ]), 1, "节1")
    sec2 = graph_lines_to_doc(_sec_lines("s02_出租屋", "出租屋", [
        _line("say", "回来了。", who="陈默", portrait="疲惫", pos="center", lid="N2"),
        _line("say", "嗯。", who="陆择", portrait="平静", pos="left", lid="N3"),
    ]), 1, "节2")

    doc = merge([sec1, sec2], chapter=1, title="新皮肤·Day0")
    assert [s["id"] for s in doc["scenes"]] == ["s01_桥上", "s02_出租屋"]
    assert doc["meta"]["requires"]["characters"] == ["陈默", "陆择"]      # 并集保序去重
    assert doc["meta"]["requires"]["scenes"] == ["长江大桥-栏杆", "出租屋"]
    assert doc["meta"]["requires"]["portraits"] == ["沉重", "疲惫", "平静"]
    assert doc["meta"]["chapter"] == 1 and doc["meta"]["title"] == "新皮肤·Day0"


def test_merge_validates_against_schema(tmp_path):
    """图行投影合并产物通过运行时章 JSON schema（ending/label/narrate/say 全行型）。"""
    sec1 = graph_lines_to_doc(_sec_lines("s01_桥上", "长江大桥-栏杆", [
        _line("narrate", "风停了。", lid="N1"),
        _line("label", "keep", lid="N2"),
        _line("ending", "一切照旧", kind="TE", lid="N3"),
    ]), 1, "节1")
    doc = merge([sec1], chapter=1, title="新皮肤")
    ok, errors = _dump_validate(doc, tmp_path)
    assert ok, errors


def test_merge_rejects_duplicate_scene_id():
    sec1 = graph_lines_to_doc(_sec_lines("路口", "马路-路口", [
        _line("narrate", "a", lid="N1")]), 1, "节1")
    sec2 = graph_lines_to_doc(_sec_lines("路口", "出租屋", [
        _line("narrate", "b", lid="N2")]), 1, "节2")  # 与节1 id 重复
    with pytest.raises(ValueError, match="重复"):
        merge([sec1, sec2], chapter=1, title="x")


def test_merge_with_chapter_map_rewrites_portrait_and_injects_bgm(tmp_path):
    """带 chapter_map：say.portrait 从纯变体改写为 guid 整键 + requires 重推导 + bgm 注入。"""
    sec1 = graph_lines_to_doc(_sec_lines("酒店", "酒店-客房", [
        _line("say", "呵。", who="陆择", portrait="慵懒", pos="left", lid="N1"),
        _line("say", "醒了？", who="陆择", portrait="玩味", pos="left", lid="N2"),
    ]), 0, "sec00")
    sec2 = graph_lines_to_doc(_sec_lines("咖啡店", "街角咖啡店-点餐台", [
        _line("say", "美式。", who="陆择", portrait="慵懒", pos="left", lid="N3"),
    ]), 0, "sec01")

    chapter_map = {
        "portraits": {
            "酒店-客房": {"陆择": {"慵懒": "陆择-赤裸上身-慵懒-PHSE4iftNQ",
                                    "玩味": "陆择-赤裸上身-玩味-PHSE4iftNR"}},
            "街角咖啡店-点餐台": {"陆择": {"慵懒": "陆择-商务休闲着装-慵懒-PJajqyM6s4"}},
        },
        "bgm": {"酒店-客房": {"track": "晨离", "mode": "play", "loop": True}},
    }
    doc = merge([sec1, sec2], chapter=0, title="序章", chapter_map=chapter_map)

    # sec00 陆择 portrait 改为赤裸上身整键（两句各自命中）
    assert doc["scenes"][0]["lines"][0]["portrait"] == "陆择-赤裸上身-慵懒-PHSE4iftNQ"
    assert doc["scenes"][0]["lines"][1]["portrait"] == "陆择-赤裸上身-玩味-PHSE4iftNR"
    # sec01 陆择.慵懒 改为商务休闲整键（同名变体不同键 → 不冲突）；该场景无 BGM 映射 → 不注入
    assert doc["scenes"][1]["lines"][0]["portrait"] == "陆择-商务休闲着装-慵懒-PJajqyM6s4"
    assert "bgm" not in doc["scenes"][1]
    # BGM 注入到酒店-客房 scene-block（图推导，行上不存）
    assert doc["scenes"][0]["bgm"] == {"track": "晨离", "mode": "play", "loop": True}
    # requires.portraits 从改写后 lines 重推导（保序去重）
    assert doc["meta"]["requires"]["portraits"] == [
        "陆择-赤裸上身-慵懒-PHSE4iftNQ",
        "陆择-赤裸上身-玩味-PHSE4iftNR",
        "陆择-商务休闲着装-慵懒-PJajqyM6s4",
    ]
    ok, errors = _dump_validate(doc, tmp_path)
    assert ok, errors


def test_merge_chapter_map_unknown_scene_ignored():
    """map 含本章不存在的 scene → 不报错、不影响（portrait 保持原值并进 requires）。"""
    sec = graph_lines_to_doc(_sec_lines("s1", "室内", [
        _line("say", "x", who="陆择", portrait="慵懒", pos="center", lid="N1")]), 0, "s")
    chapter_map = {"portraits": {"不存在场景": {"陆择": {"慵懒": "X-Y-Z-I"}}}, "bgm": {}}
    doc = merge([sec], chapter=0, title="x", chapter_map=chapter_map)
    assert doc["scenes"][0]["lines"][0]["portrait"] == "慵懒"  # 未命中，不改写
    assert doc["meta"]["requires"]["portraits"] == ["慵懒"]


def test_merge_without_chapter_map_keeps_pure_concat():
    """无 chapter_map：纯拼接（requires 取各节并集，portrait 不改写、无 bgm 注入）。"""
    sec = graph_lines_to_doc(_sec_lines("s1", "室内", [
        _line("say", "x", who="陆择", portrait="慵懒", pos="center", lid="N1")]), 0, "s")
    doc = merge([sec], chapter=0, title="x")  # 不传 chapter_map
    assert doc["scenes"][0]["lines"][0]["portrait"] == "慵懒"
    assert doc["meta"]["requires"]["portraits"] == ["慵懒"]
