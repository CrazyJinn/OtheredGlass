"""script_splitter 纯函数单测（parse_md / align / assign_orders / build_actions）——不连 Neo4j。

split 主流程（查图/写图）不在单测范围（需真实库，端到端验证）。
在 99_game/tools 下跑：python -m pytest test_script_splitter.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "skills"
                        / "section-voice-publisher" / "scripts"))
import script_splitter as sp  # noqa: E402


MD = """# 酒店醒来

## s00_酒店 酒店-客房（清晨）

旁白:清晨，一缕阳光从窗帘缝隙钻进来。
陆择:嗯……等下还要赶飞机。

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


def _g(op, text, *, who=None, order=0, status=11, nid="g",
       voice_key=None, sha=None, scene_block_id=None, kind=None, pos=None):
    """图行 dict（split 图查询返回形状）。"""
    return {"id": nid, "op": op, "who": who, "pos": pos,
            "text": text, "kind": kind, "scene_block_id": scene_block_id,
            "status": status, "attempts": 0, "voice_key": voice_key,
            "text_sha1": sha if sha is not None else sp.text_sha1(text or ""),
            "ord": order}


# ── parse_md ──

def test_parse_md_basic(tmp_path):
    parsed = sp.parse_md(_write_md(tmp_path))
    rows, blocks = parsed["rows"], parsed["blocks"]
    ops = [r["op"] for r in rows]
    assert ops == ["narrate", "say", "label", "say", "ending"]   # scene 行已去图化
    assert blocks == [{"block": "s00_酒店", "scene_name": "酒店-客房"}]
    assert rows[0]["scene_block_id"] == "s00_酒店"
    assert rows[1] == {"op": "say", "who": "陆择", "text": "嗯……等下还要赶飞机。",
                       "scene_block_id": "s00_酒店"}
    assert rows[2]["text"] == "起床"            # label 行
    assert rows[4]["kind"] == "BE" and rows[4]["text"] == "没赶上飞机"


def test_parse_md_choice_block_skipped(tmp_path):
    rows = sp.parse_md(_write_md(tmp_path))["rows"]
    texts = [r.get("text") for r in rows]
    assert "起床 → 分支:起床" not in texts      # 选择块整块跳过（choice 不进图）


def test_parse_md_rejects_unknown_line(tmp_path):
    p = _write_md(tmp_path, "## s0 场（早）\n%%怪行%%\n")
    with pytest.raises(ValueError, match="第 2 行"):
        sp.parse_md(p)


def test_parse_md_rejects_legacy_portrait_bracket(tmp_path):
    """演出层已与台词分离：残留 [表情] 标注必须显式报错，不得静默吞掉。"""
    p = _write_md(tmp_path, "## s0 场（早）\n陆择[微笑]:再睡五分钟嘛。\n")
    with pytest.raises(ValueError, match="第 2 行"):
        sp.parse_md(p)


def test_parse_md_requires_scene_header(tmp_path):
    p = _write_md(tmp_path, "# 只有节标题\n\n")   # 无任何场景二级标题
    with pytest.raises(ValueError, match="缺场景"):
        sp.parse_md(p)


def test_parse_md_line_before_first_scene_header(tmp_path):
    p = _write_md(tmp_path, "旁白:出现在首个场景标题之前\n## s0 场（早）\n")
    with pytest.raises(ValueError, match="首个场景标题之前"):
        sp.parse_md(p)


# ── align / assign_orders ──

def _md_rows():
    return [
        {"op": "say", "who": "陆择", "text": "第一句", "scene_block_id": "s0"},
        {"op": "say", "who": "陆择", "text": "第二句", "scene_block_id": "s0"},
        {"op": "narrate", "text": "收尾", "scene_block_id": "s0"},
    ]


def test_align_full_new():
    plan = sp.align(_md_rows(), [])
    assert len(plan["create"]) == 3 and not plan["keep"] and not plan["update"] and not plan["delete"]
    seq, reordered = sp.assign_orders(_md_rows(), plan)
    assert [x["order"] for x in seq] == [1000, 2000, 3000]
    assert not reordered
    assert all(x["action"] == "create" for x in seq)


def test_align_insert_middle_gets_midpoint_order():
    graph = [_g("say", "第一句", who="陆择", order=1000, nid="b"),
             _g("narrate", "收尾", order=3000, nid="d")]
    md = [  # 在 第一句 与 收尾 之间插入 第二句
        {"op": "say", "who": "陆择", "text": "第一句", "scene_block_id": "s0"},
        {"op": "say", "who": "陆择", "text": "第二句", "scene_block_id": "s0"},
        {"op": "narrate", "text": "收尾", "scene_block_id": "s0"},
    ]
    plan = sp.align(md, graph)
    assert len(plan["keep"]) == 2 and len(plan["create"]) == 1
    seq, reordered = sp.assign_orders(md, plan)
    new = [x for x in seq if x["action"] == "create"][0]
    assert new["order"] == 2000                 # (1000+3000)//2 中点
    assert not reordered
    assert [x["order"] for x in seq] == [1000, 2000, 3000]


def test_align_modify_keeps_id_and_marks_stale():
    graph = [_g("say", "旧台词", who="陆择", order=1000, nid="keepme")]
    md = [{"op": "say", "who": "陆择", "text": "新台词", "scene_block_id": "s0"}]
    plan = sp.align(md, graph)
    assert len(plan["update"]) == 1
    seq, _ = sp.assign_orders(md, plan)
    assert seq[0]["id"] == "keepme" and seq[0]["order"] == 1000
    stmts, report = sp.build_actions(seq, plan, "SC")
    assert report["updated"] == [{"id": "keepme", "op": "say", "text": "新台词"}]
    assert any("l.status=0" in s for s in stmts)         # stale 重配
    assert any("keepme" in s and "l.text='新台词'" in s for s in stmts)


def test_align_delete_detaches():
    graph = [_g("say", "第一句", who="A", order=1000, nid="a"),
             _g("say", "将删", who="A", order=2000, nid="del")]
    md = [{"op": "say", "who": "A", "text": "第一句", "scene_block_id": "s0"}]
    plan = sp.align(md, graph)
    assert len(plan["delete"]) == 1 and plan["delete"][0]["graph"]["id"] == "del"
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC")
    assert any("DETACH DELETE l" in s and "del" in s for s in stmts)
    assert report["counts"]["deleted"] == 1


def test_align_repeated_text_pairs_stably():
    graph = [_g("say", "一样的话", who="A", order=1000, nid="x", voice_key="k1"),
             _g("say", "一样的话", who="A", order=2000, nid="y", voice_key="k2"),
             _g("say", "不一样", who="A", order=3000, nid="z")]
    md = [{"op": "say", "who": "A", "text": "一样的话", "scene_block_id": "s0"},
          {"op": "say", "who": "A", "text": "一样的话", "scene_block_id": "s0"},
          {"op": "say", "who": "A", "text": "不一样", "scene_block_id": "s0"}]
    plan = sp.align(md, graph)
    assert len(plan["keep"]) == 3 and not plan["create"] and not plan["delete"]


def test_order_exhaustion_triggers_full_reorder():
    graph = [_g("say", "一", who="A", order=1000, nid="a"),
             _g("say", "三", who="A", order=1001, nid="c")]   # 缝隙差 1，插不进
    md = [{"op": "say", "who": "A", "text": "一", "scene_block_id": "s0"},
          {"op": "say", "who": "A", "text": "二", "scene_block_id": "s0"},  # 新句
          {"op": "say", "who": "A", "text": "三", "scene_block_id": "s0"}]
    plan = sp.align(md, graph)
    seq, reordered = sp.assign_orders(md, plan)
    assert reordered
    assert [x["order"] for x in seq] == [1000, 2000, 3000]
    body, _ = sp.build_actions(seq, plan, "SC")
    stmts = sp._order_statements(seq, "SC", reordered) + body
    assert any("SET r.order=3000" in s for s in stmts)   # 被挤开的旧行重排到新位
    assert any("MERGE (sc)-[r:produces]->(l) SET r.order=2000" in s for s in stmts)  # 新行建边带序


# ── build_actions：keep 的恢复与保留 ──

def test_keep_restores_minus1_with_wav(monkeypatch):
    monkeypatch.setattr(sp, "_wav_exists", lambda key: True)
    g = _g("say", "第一句", who="A", order=1000, nid="a", status=-1, voice_key="k1")
    md = [{"op": "say", "who": "A", "text": "第一句", "scene_block_id": "s0"}]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC")
    assert report["restored"] == [{"id": "a", "to": 10}]
    assert any("SET l.status=10" in s for s in stmts)


def test_keep_restores_minus1_without_wav_to_zero(monkeypatch):
    monkeypatch.setattr(sp, "_wav_exists", lambda key: False)
    g = _g("say", "第一句", who="A", order=1000, nid="a", status=-1, voice_key="k1")
    md = [{"op": "say", "who": "A", "text": "第一句", "scene_block_id": "s0"}]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    _, report = sp.build_actions(seq, plan, "SC")
    assert report["restored"] == [{"id": "a", "to": 0}]


def test_keep_restores_nonsay_to_eleven():
    g = _g("narrate", "收尾", order=1000, nid="a", status=-1)
    md = [{"op": "narrate", "text": "收尾", "scene_block_id": "s0"}]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    _, report = sp.build_actions(seq, plan, "SC")
    assert report["restored"] == [{"id": "a", "to": 11}]


def test_keep_preserves_non_minus1_status():
    g = _g("say", "第一句", who="A", order=1000, nid="a", status=11)
    md = [{"op": "say", "who": "A", "text": "第一句", "scene_block_id": "s0"}]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC")
    assert report["counts"]["restored"] == 0
    assert not any("l.status=" in s for s in stmts)       # 不触碰 status（微调回路：11 保持）


def test_keep_backfills_scene_block_id():
    g = _g("say", "第一句", who="A", order=1000, nid="a", status=11, scene_block_id=None)
    md = [{"op": "say", "who": "A", "text": "第一句", "scene_block_id": "s00_酒店"}]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    stmts, _ = sp.build_actions(seq, plan, "SC")
    assert any("SET l.scene_block_id='s00_酒店'" in s for s in stmts)


# ── 演出层已剥离：语句不含 portrait 属性 ──

def test_create_update_stmts_have_no_portrait_property():
    graph = [_g("say", "旧台词", who="A", order=1000, nid="keepme")]
    md = [{"op": "say", "who": "A", "text": "新句", "scene_block_id": "s0"},
          {"op": "say", "who": "A", "text": "全新", "scene_block_id": "s0"}]
    plan = sp.align(md, graph)
    seq, _ = sp.assign_orders(md, plan)
    stmts, _ = sp.build_actions(seq, plan, "SC")
    assert stmts
    assert not any("l.portrait" in s for s in stmts)      # portrait 属性已废弃（选绘走 uses 边）


def test_say_create_gets_default_pos_and_status_zero():
    md = [{"op": "say", "who": "陆择", "text": "嗨", "scene_block_id": "s0"}]
    plan = sp.align(md, [])
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC")
    create_stmt = [s for s in stmts if "MERGE (l:LineAudio" in s and "l.op='say'" in s][0]
    assert "l.status=0" in create_stmt and "l.pos='center'" in create_stmt  # 单人块居中
    assert any("r.order=1000" in s for s in stmts)


# ── 环境音行（transition / ambience）与块级 pos 分配 ──

def test_parse_md_transition_line(tmp_path):
    """「环境音:」独立行 → op=transition（转场音效行）；旁白内嵌【环境音:x】→ narrate.ambient_text。"""
    md = ("## s0 场（早）\n"
          "环境音:推门时门口的风铃清脆作响\n"
          "旁白:雨点骤然砸落【环境音:骤雨由疏转密】\n")
    rows = sp.parse_md(_write_md(tmp_path, md))["rows"]
    assert rows[0] == {"op": "transition", "text": "推门时门口的风铃清脆作响",
                       "scene_block_id": "s0"}
    assert rows[1] == {"op": "narrate", "text": "雨点骤然砸落",
                       "ambient_text": "骤雨由疏转密", "scene_block_id": "s0"}


def test_block_pos_two_speakers_split_sides():
    """双人块：先说话者 left、后说话者 right（对话分侧）；create/update 都按块规则值。"""
    md = [
        {"op": "say", "who": "小夏", "text": "欢迎光临。", "scene_block_id": "s0"},
        {"op": "say", "who": "陆择", "text": "来杯拿铁。", "scene_block_id": "s0"},
    ]
    graph = [_g("say", "欢迎光临呀。", who="小夏", order=1000, nid="a", pos="left")]  # 旧文本 → update
    plan = sp.align(md, graph)
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC")
    create_stmt = [s for s in stmts if "MERGE (l:LineAudio" in s and "l.op='say'" in s
                   and "来杯拿铁" in s][0]
    assert "l.pos='right'" in create_stmt                       # 后说话者 right（create 规则值）
    update_stmt = [s for s in stmts if "MATCH (l:LineAudio" in s and "欢迎光临。" in s][0]
    assert "l.pos='left'" in update_stmt                        # 先说话者规则值 left（update 全量 SET）


def test_keep_pos_diff_self_heals():
    """keep 行存量 pos 与块规则不一致（如全 left 旧数据）→ 自愈补写 SET l.pos；一致则不写。"""
    g = _g("say", "第一句", who="A", order=1000, nid="a", status=11, pos="left")
    md = [
        {"op": "say", "who": "A", "text": "第一句", "scene_block_id": "s0"},
        {"op": "say", "who": "B", "text": "第二句", "scene_block_id": "s0"},
    ]
    plan = sp.align(md, [g])
    seq, _ = sp.assign_orders(md, plan)
    stmts, report = sp.build_actions(seq, plan, "SC")
    assert not any("SET l.pos=" in s and "'a'" in s for s in stmts)     # 规则 left 与存量 left 一致 → 不写
    # 反例：单人块规则 center，存量 left → 补写 center
    g2 = dict(_g("say", "独白", who="A", order=1000, nid="b", status=11), pos="left")
    md2 = [{"op": "say", "who": "A", "text": "独白", "scene_block_id": "s0"}]
    plan2 = sp.align(md2, [g2])
    seq2, _ = sp.assign_orders(md2, plan2)
    stmts2, _ = sp.build_actions(seq2, plan2, "SC")
    assert any("SET l.pos='center'" in s and "'b'" in s for s in stmts2)


def test_legacy_ambient_graph_row_aligns_as_keep():
    """存量 op=ambient 图行 vs md op=transition：签名归一对齐为 keep，且落图自愈 SET op。"""
    g = _g("ambient", "风铃作响", order=1000, nid="amb1", status=11)
    md = [{"op": "transition", "text": "风铃作响", "scene_block_id": "s0"}]
    plan = sp.align(md, [g])
    assert len(plan["keep"]) == 1 and not plan["update"]      # 不误置 0 重配
    seq, _ = sp.assign_orders(md, plan)
    stmts, _ = sp.build_actions(seq, plan, "SC")
    assert any("SET l.op='transition'" in s for s in stmts)   # 幂等自愈改名
