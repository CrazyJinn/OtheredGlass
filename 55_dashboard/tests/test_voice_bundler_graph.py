"""voice_bundler 图行模式单测：voice key（节点 id 寻址）/ collect_graph_tasks / bind_graph 语句。"""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (_PROJECT_ROOT / ".claude" / "scripts", _PROJECT_ROOT / ".claude" / "scripts" / "voice"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import voice_bundler as vb  # noqa: E402


def _lines():
    """图行序列（fetch_section 的 lines 形状，按 ord）：scene + narrate + 3 say。"""
    return [
        {"id": "S0", "op": "scene", "scene_block_id": "s00_酒店", "status": 11, "who": None, "text": None},
        {"id": "N1", "op": "narrate", "text": "清晨。", "status": 11, "who": None},
        {"id": "N2", "op": "say", "who": "陆择", "text": "早。", "status": 0, "attempts": 1,
         "voice_key": "陆择-chapter00_序章-s00_酒店-N2"},
        {"id": "N3", "op": "say", "who": "顾盈", "text": "醒了。", "status": 0, "attempts": 0},
        {"id": "N4", "op": "say", "who": "陆择", "text": "嗯。", "status": 0, "attempts": None},
    ]


def test_make_voice_key_format():
    assert vb.make_voice_key("陆择", "chapter00_序章", "s00_酒店", "Nv93TkkkgC") == \
        "陆择-chapter00_序章-s00_酒店-Nv93TkkkgC"


def _keys(lines, node_ids=()):
    tasks = vb.collect_graph_tasks(lines, "chapter00_序章", node_ids=node_ids)
    return {it["node_id"]: it["key"] for items in tasks.values() for it in items}


def test_collect_graph_tasks_picks_status_zero_and_derives_scene():
    """挑行 = say 且 status=0（待配/被驳回/stale 拆分已归一）；scene 段按 order 遍历推导。"""
    lines = _lines()
    lines[1]["status"] = 0  # narrate 置 0 也不挑（无音频语义）
    picked = _keys(lines)
    assert sorted(picked) == ["N2", "N3", "N4"]
    assert picked["N3"] == "顾盈-chapter00_序章-s00_酒店-N3"  # scene_block_id 从前驱 scene 行推导


def test_collect_graph_tasks_node_whitelist_and_grouping():
    tasks = vb.collect_graph_tasks(_lines(), "chapter00_序章", node_ids=("N3",))
    assert list(tasks.keys()) == ["顾盈"]                       # 按角色分组
    assert tasks["顾盈"][0]["node_id"] == "N3"
    assert tasks["顾盈"][0]["text"] == "醒了。"


def test_voice_key_stable_across_insert_and_delete():
    """漂移冒烟（核心契约）：插入/删除行，未变行节点 id 不变 → key 不变。"""
    lines = _lines()
    before = _keys(lines)
    inserted = {"id": "NEW", "op": "say", "who": "顾盈", "text": "插句。", "status": 0, "attempts": 0}
    lines.insert(4, inserted)
    after_insert = _keys(lines)
    for nid, key in before.items():
        assert after_insert[nid] == key
    lines = [l for l in lines if l["id"] != "N2"]
    after_delete = _keys(lines)
    for nid, key in before.items():
        if nid == "N2":
            continue
        assert after_delete[nid] == key


def test_bind_graph_builds_statements(monkeypatch):
    """bind_graph 语句构造（monkeypatch 写图，不连库）：voice_key/emotion/tts_text/
    attempts+1/text_sha1/status=10；keys 过滤排除失败句。"""
    captured = []
    monkeypatch.setattr(vb, "_run_cypher_multi", lambda stmts: captured.extend(stmts))
    tasks = vb.collect_graph_tasks(_lines(), "chapter00_序章")
    for items in tasks.values():
        for it in items:
            it["emotion"] = "调侃"
            it["tts_text"] = it["text"] + "……"

    stats = vb.bind_graph(tasks)
    assert stats == {"bound": 3, "skipped": 0}
    assert len(captured) == 3
    stmt = [s for s in captured if "N3" in s][0]
    assert "l.voice_key='顾盈-chapter00_序章-s00_酒店-N3'" in stmt
    assert "l.emotion='调侃'" in stmt
    assert "l.tts_text='醒了。……'" in stmt
    assert "l.attempts=coalesce(l.attempts,0)+1" in stmt
    assert f"l.text_sha1='{vb._text_sha1('醒了。')}'" in stmt
    assert "l.status=10" in stmt

    # keys 过滤（publish 失败句排除）
    captured.clear()
    stats = vb.bind_graph(tasks, keys=["顾盈-chapter00_序章-s00_酒店-N3"])
    assert stats == {"bound": 1, "skipped": 2}
    assert len(captured) == 1
