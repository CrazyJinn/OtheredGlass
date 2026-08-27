"""script_splitter 纯函数单测（parse_md / align / assign_orders / build_actions）——不连 Neo4j。

split 主流程（查图/写图）不在单测范围（需真实库，端到端验证）。
在 99_game/tools 下跑：python -m pytest test_script_splitter.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "scripts"))
import script_splitter as sp  # noqa: E402


MD = """# 酒店醒来

## s00_酒店 酒店-客房（清晨）

旁白:清晨，一缕阳光从窗帘缝隙钻进来。
陆择:嗯……等下还要赶飞机。
陆择[慵懒]:再睡五分钟嘛。

**选择**
- 起床 → 分支:起床
- 继续睡 → 分支:赖床

**分支:起床**

顾盈:哟，醒这么早？

**结局**:BE——没赶上飞机
"""


def _write_md(tmp_path, text=MD):
    p = tmp_path / "台词.md"
    p.write_text(text, encoding="utf-8")
    return str(p)


def _g(op, text, *, who=None, order=0, status=11, nid="g", portrait=None,
       voice_key=None, sha=None, scene_block_id=None, kind=None, scene_name=None):
    """图行 dict（split 图查询返回形状）。"""
    return {"id": nid, "op": op, "who": who, "portrait": portrait, "pos": None,
            "text": text, "kind": kind, "scene_block_id": scene_block_id,
            "status": status, "attempts": 0, "voice_key": voice_key,
            "text_sha1": sha if sha is not None else sp.text_sha1(text or ""),
            "ord": order, "scene_name": scene_name}


# ── parse_md ──

def test_parse_md_basic(tmp_path):
    rows = sp.parse_md(_write_md(tmp_path))
    ops = [r["op"] for r in rows]
    assert ops == ["scene", "narrate", "say", "say", "label", "say", "ending"]
    assert rows[0]["scene_block_id"] == "s00_酒店"
    assert rows[0]["scene_name"] == "酒店-客房"
    assert rows[2] == {"op": "say", "who": "陆择", "portrait": None, "text": "嗯……等下还要赶飞机。"}
    assert rows[3]["portrait"] == "慵懒"
    assert rows[4]["text"] == "起床"            # label 行
    assert rows[6]["kind"] == "BE" and rows[6]["text"] == "没赶上飞机"


def test_parse_md_choice_block_skipped(tmp_path):
    rows = sp.parse_md(_write_md(tmp_path))
    texts = [r.get("text") for r in rows]
    assert "起床 → 分支:起床" not in texts      # 选择块整块跳过（choice 不进图）


def test_parse_md_rejects_unknown_line(tmp_path):
    p = _write_md(tmp_path, "## s0 场（早）\n%%怪行%%\n")
    with pytest.raises(ValueError, match="第 2 行"):
        sp.parse_md(p)


def test_parse_md_requires_scene_header(tmp_path):
    p = _write_md(tmp_path, "旁白:没有任何场景标题\n")
    with pytest.raises(ValueError, match="缺场景"):
        sp.parse_md(p)


# ── align / assign_orders ──

def _md_rows():
    return [
        {"op": "scene", "scene_block_id": "s0", "scene_name": "酒店", "text": None},
        {"op": "say", "who": "陆择", "portrait": None, "text": "第一句"},
        {"op": "say", "who": "陆择", "portrait": None, "text": "第二句"},
        {"op": "narrate", "text": "收尾"},
    ]


def test_align_full_new():
    plan = sp.align(_md_rows(), [])
    assert len(plan["create"]) == 4 and not plan["keep"] and not plan["update"] and not plan["delete"]
    seq, reordered = sp.assign_orders(_md_rows(), plan)
    assert [x["order"] for x in seq] == [1000, 2000, 3000, 4000]
    assert not reordered
    assert all(x["action"] == "create" for x in seq)


def test_align_insert_middle_gets_midpoint_order():
    graph = [_g("scene", None, order=1000, nid="a", scene_block_id="s0", scene_name="酒店"),
             _g("say", "第一句", who="陆择", order=2000, nid="b"),
             _g("narrate", "收尾", order=4000, nid="d")]
    md = [  # 在 第一句 与 收尾 之间插入 第二句
        {"op": "scene", "scene_block_id": "s0", "scene_name": "酒店", "text": None},
        {"op": "say", "who": "陆择", "portrait": None, "text": "第一句"},
        {"op": "say", "who": "陆择", "portrait": None, "text": "第二句"},
        {"op": "narrate", "text": "收尾"},
    ]
    plan = sp.align(md, graph)
    assert len(plan["keep"]) == 3 and len(plan["create"]) == 1
    seq, reordered = sp.assign_orders(md, plan)
    orders = {x["id"] if x["action"] == "create" else x["id"]: x["order"] for x in seq}
    new = [x for x in seq if x["action"] == "create"][0]
    assert new["order"] == 3000                 # (2000+4000)//2 的均分位
    assert not reordered
    assert [x["order"] for x in seq] == [1000, 2000, 3000, 4000]


def test_align_modify_keeps_id_and_marks_stale():
    graph = [_g("say", "旧台词", who="陆择", order=1000, nid="keepme")]
    md = [{"op": "say", "who": "陆择", "portrait": None, "text": "新台词"}]
    plan = sp.align(md, graph)
    assert len(plan["update"]) == 1
    seq, _ = sp.assign_orders(md, plan)
    assert seq[0]["id"] == "keepme" and seq[0]["order"] == 1000
    stmts, report = sp.build_actions(seq, plan, "SC", set())
    assert report["updated"] == [{"id": "keepme", "op": "say", "text": "新台词"}]
    assert any("l.status=0" in s for s in stmts)         # stale 重配
    assert any("keepme" in s and "l.text='新台词'" in s for s in stmts)


def test_align_delete_detaches():
    graph = [_g("say", "第一句", who="A", order=1000, nid="a"),
             _g("say", "将删", who="A", order=2000, nid="del")]
    md = [{"op": "say", "who": "A", "portrait": None, "text": "第一句"}]
    plan = sp.align(md, graph)
    assert len(plan["delete"]) == 1 and plan["delete"][0]["graph"]["id"] == "del"
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC", set())
    assert any("DETACH DELETE l" in s and "del" in s for s in stmts)
    assert report["counts"]["deleted"] == 1


def test_align_repeated_text_pairs_stably():
    graph = [_g("say", "一样的话", who="A", order=1000, nid="x", voice_key="k1"),
             _g("say", "一样的话", who="A", order=2000, nid="y", voice_key="k2"),
             _g("say", "不一样", who="A", order=3000, nid="z")]
    md = [{"op": "say", "who": "A", "portrait": None, "text": "一样的话"},
          {"op": "say", "who": "A", "portrait": None, "text": "一样的话"},
          {"op": "say", "who": "A", "portrait": None, "text": "不一样"}]
    plan = sp.align(md, graph)
    assert len(plan["keep"]) == 3 and not plan["create"] and not plan["delete"]


def test_order_exhaustion_triggers_full_reorder():
    graph = [_g("say", "一", who="A", order=1000, nid="a"),
             _g("say", "三", who="A", order=1001, nid="c")]   # 缝隙差 1，插不进
    md = [{"op": "say", "who": "A", "portrait": None, "text": "一"},
          {"op": "say", "who": "A", "portrait": None, "text": "二"},  # 新句
          {"op": "say", "who": "A", "portrait": None, "text": "三"}]
    plan = sp.align(md, graph)
    seq, reordered = sp.assign_orders(md, plan)
    assert reordered
    assert [x["order"] for x in seq] == [1000, 2000, 3000]
    body, _ = sp.build_actions(seq, plan, "SC", set())
    stmts = sp._order_statements(seq, "SC", reordered) + body
    assert any("SET r.order=3000" in s for s in stmts)   # 被挤开的旧行重排到新位
    assert any("MERGE (sc)-[r:produces]->(l) SET r.order=2000" in s for s in stmts)  # 新行建边带序


# ── build_actions：keep 的恢复与保留 ──

def test_keep_restores_minus1_with_wav(monkeypatch):
    monkeypatch.setattr(sp, "_wav_exists", lambda who, key: True)
    g = _g("say", "第一句", who="A", order=1000, nid="a", status=-1, voice_key="k1")
    md = [{"op": "say", "who": "A", "portrait": None, "text": "第一句"}]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC", set())
    assert report["restored"] == [{"id": "a", "to": 10}]
    assert any("SET l.status=10" in s for s in stmts)


def test_keep_restores_minus1_without_wav_to_zero(monkeypatch):
    monkeypatch.setattr(sp, "_wav_exists", lambda who, key: False)
    g = _g("say", "第一句", who="A", order=1000, nid="a", status=-1, voice_key="k1")
    md = [{"op": "say", "who": "A", "portrait": None, "text": "第一句"}]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    _, report = sp.build_actions(seq, plan, "SC", set())
    assert report["restored"] == [{"id": "a", "to": 0}]


def test_keep_restores_nonsay_to_eleven():
    g = _g("narrate", "收尾", order=1000, nid="a", status=-1)
    md = [{"op": "narrate", "text": "收尾"}]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    _, report = sp.build_actions(seq, plan, "SC", set())
    assert report["restored"] == [{"id": "a", "to": 11}]


def test_keep_preserves_non_minus1_status():
    g = _g("say", "第一句", who="A", order=1000, nid="a", status=11)
    md = [{"op": "say", "who": "A", "portrait": None, "text": "第一句"}]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC", set())
    assert report["counts"]["restored"] == 0
    assert not any("l.status=" in s for s in stmts)       # 不触碰 status（微调回路：11 保持）


def test_keep_updates_portrait_diff_only():
    g = _g("say", "第一句", who="A", order=1000, nid="a", status=11, portrait="旧")
    md = [{"op": "say", "who": "A", "portrait": "新", "text": "第一句"}]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    stmts, _ = sp.build_actions(seq, plan, "SC", set())
    assert any("l.portrait='新'" in s for s in stmts)
    assert not any("l.status=" in s for s in stmts)       # 演出 diff 不动 status


def test_scene_create_builds_stages_edge_and_warns_missing():
    md = [{"op": "scene", "scene_block_id": "s0", "scene_name": "不存在的场景", "text": None}]
    plan = sp.align(md, [])
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC", set())   # scene_names 空 = Scene 缺失
    assert report["warnings"] and "stages" in report["warnings"][0]
    stmts2, report2 = sp.build_actions(seq, plan, "SC", {"不存在的场景"})
    assert any("stages" in s and "MERGE" in s for s in stmts2)


def test_say_create_gets_default_pos_and_status_zero():
    md = [{"op": "scene", "scene_block_id": "s0", "scene_name": "X", "text": None},
          {"op": "say", "who": "陆择", "portrait": None, "text": "嗨"}]
    plan = sp.align(md, [])
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC", set())
    create_stmt = [s for s in stmts if "MERGE (l:LineAudio" in s and "l.op='say'" in s][0]
    assert "l.status=0" in create_stmt and "l.pos='left'" in create_stmt
    assert any("r.order=2000" in s for s in stmts)
