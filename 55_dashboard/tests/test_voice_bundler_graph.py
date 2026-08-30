"""voice_bundler 图行模式单测：voice key（节点 id 寻址）/ collect_graph_tasks / bind_graph 语句。"""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (_PROJECT_ROOT / ".claude" / "scripts", _PROJECT_ROOT / ".claude" / "skills" / "section-voice-publisher" / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import voice_bundler as vb  # noqa: E402


def _lines():
    """图行序列（fetch_section 的 lines 形状，按 ord）：narrate + 3 say（scene 行已去图化，
    块归属在各行 scene_block_id 上直读）。"""
    return [
        {"id": "N1", "op": "narrate", "text": "清晨。", "status": 11, "who": None,
         "scene_block_id": "s00_酒店"},
        {"id": "N2", "op": "say", "who": "陆择", "text": "早。", "status": 0, "attempts": 1,
         "scene_block_id": "s00_酒店",
         "voice_key": "陆择-chapter00_序章-s00_酒店-N2"},
        {"id": "N3", "op": "say", "who": "顾盈", "text": "醒了。", "status": 0, "attempts": 0,
         "scene_block_id": "s00_酒店"},
        {"id": "N4", "op": "say", "who": "陆择", "text": "嗯。", "status": 0, "attempts": None,
         "scene_block_id": "s00_酒店"},
    ]


def test_make_voice_key_format():
    assert vb.make_voice_key("陆择", "chapter00_序章", "s00_酒店", "Nv93TkkkgC") == \
        "陆择-chapter00_序章-s00_酒店-Nv93TkkkgC"


def _keys(lines, node_ids=()):
    tasks = vb.collect_graph_tasks(lines, "chapter00_序章", node_ids=node_ids)
    return {it["node_id"]: it["key"] for items in tasks.values() for it in items}


def test_collect_graph_tasks_picks_status_zero_and_reads_block():
    """挑行 = say 且 status=0（待配/被驳回/stale 拆分已归一）；块归属行上直读。"""
    lines = _lines()
    lines[0]["status"] = 0  # narrate 置 0 也不挑（无音频语义）
    picked = _keys(lines)
    assert sorted(picked) == ["N2", "N3", "N4"]
    assert picked["N3"] == "顾盈-chapter00_序章-s00_酒店-N3"  # scene_block_id 行上直读


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


# ── clone_mode（icl/xvec 演绎通道：透传初值 → LLM 判别 → bind 归一终值）──

def test_normalize_clone_mode():
    """归一：'xvec' 原样（大小写/空白宽容）；None/'icl'/脏值一律 'icl'（缺省）。"""
    assert vb.normalize_clone_mode("xvec") == "xvec"
    assert vb.normalize_clone_mode(" XVEC ") == "xvec"
    assert vb.normalize_clone_mode("icl") == "icl"
    assert vb.normalize_clone_mode(None) == "icl"
    assert vb.normalize_clone_mode("garbage") == "icl"


def test_collect_graph_tasks_passes_through_clone_mode():
    """透传：图上现值（上轮 bind 终值/人工改值）进 task 项作 3b 判别初值；未判过=None。"""
    lines = _lines()
    lines[1]["clone_mode"] = "xvec"  # N2：人工在 dashboard 改过
    lines[2]["clone_mode"] = "icl"   # N3：上轮 bind 写的终值
    items = {it["node_id"]: it
             for v in vb.collect_graph_tasks(lines, "chapter00_序章").values() for it in v}
    assert items["N2"]["clone_mode"] == "xvec"
    assert items["N3"]["clone_mode"] == "icl"
    assert items["N4"]["clone_mode"] is None  # 从未判过（缺省 icl 语义）


def test_bind_graph_writes_normalized_clone_mode(monkeypatch):
    """bind 写归一化终值（=本句实际合成模式，下轮重配初值）：None→icl、脏值归一。"""
    captured = []
    monkeypatch.setattr(vb, "_run_cypher_multi", lambda stmts: captured.extend(stmts))
    tasks = vb.collect_graph_tasks(_lines(), "chapter00_序章")
    items = {it["node_id"]: it for v in tasks.values() for it in v}
    items["N2"]["clone_mode"] = "xvec"
    items["N3"]["clone_mode"] = None
    items["N4"]["clone_mode"] = "XVEC "
    vb.bind_graph(tasks)
    by_node = {nid: s for nid in ("N2", "N3", "N4") for s in captured if f"id:'{nid}'" in s}
    assert "l.clone_mode='xvec'" in by_node["N2"]
    assert "l.clone_mode='icl'" in by_node["N3"]   # 从未判过 → 缺省 icl 落图
    assert "l.clone_mode='xvec'" in by_node["N4"]  # LLM 脏值归一


def test_collect_graph_tasks_picks_invalidated_lines():
    """-1 可重配：级联作废/存量迁移重做行与 0 同为待配（禁止把 -1 滤掉）。"""
    lines = _lines()
    lines[3]["status"] = -1  # N4：级联作废（编辑已批 SecScript 触发）
    picked = _keys(lines)
    assert sorted(picked) == ["N2", "N3", "N4"]


# ── publish（发布期：已批音频键 → 母带拷运行时；生成期 sync 已废除）──

def test_collect_approved_audio_keys_field_driven():
    """以 vk/at 字段存在为准（不看 op——narrate 内嵌声景同样发布）、去重、滤 null。"""
    rows = [
        {"vk": "陆择-chapter00_序章-s00_酒店-N2", "at": None},
        {"vk": None, "at": "amb-chapter00_序章-s01_路口-Pz3xmsRauP"},  # narrate 内嵌声景
        {"vk": "陆择-chapter00_序章-s00_酒店-N2", "at": None},          # 重复
    ]
    assert vb.collect_approved_audio_keys(rows) == [
        "陆择-chapter00_序章-s00_酒店-N2", "amb-chapter00_序章-s01_路口-Pz3xmsRauP",
    ]


def test_publish_runtime_routes_and_idempotent(tmp_path):
    """amb- 前缀路由 sfx、voice key 路由 voices；母带缺失计 missing；幂等重跑全 skipped。"""
    mk = "陆择-chapter00_序章-s00_酒店-N2"
    ak = "amb-chapter00_序章-s01_路口-Pz3xmsRauP"
    mk_missing = "amb-chapter00_序章-s02_夹缝-N9"
    for key in (mk, ak):
        src = vb.voice_master_path(tmp_path, key)
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"wav-bytes")
    voices, sfx = tmp_path / "voices", tmp_path / "sfx"

    stats = vb.publish_runtime(tmp_path, [mk, ak, mk_missing], voices, runtime_sfx=sfx)
    assert stats["copied"] == 1 and stats["missing"] == 0
    assert stats["copied_sfx"] == 1 and stats["missing_sfx"] == 1
    assert (voices / f"{mk}.wav").read_bytes() == b"wav-bytes"
    assert (sfx / f"{ak}.wav").read_bytes() == b"wav-bytes"
    assert not (sfx / f"{mk_missing}.wav").exists()

    # 幂等：母带未变重跑 → 全 skipped，不再拷贝
    stats2 = vb.publish_runtime(tmp_path, [mk, ak], voices, runtime_sfx=sfx)
    assert stats2["skipped"] == 1 and stats2["skipped_sfx"] == 1
    assert stats2["copied"] == 0 and stats2["copied_sfx"] == 0
