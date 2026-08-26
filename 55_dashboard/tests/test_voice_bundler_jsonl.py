"""voice_bundler 节级 JSONL 模式单测：voice key 稳定寻址（漂移冒烟）/ tasks 过滤 / bind_audio。"""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (_PROJECT_ROOT / ".claude" / "scripts", _PROJECT_ROOT / ".claude" / "scripts" / "voice"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import jsonl_script  # noqa: E402
import voice_bundler as vb  # noqa: E402


def _rows():
    return [
        {"op": "meta", "chapter": 0, "title": "序章",
         "requires": {"characters": ["陆择", "顾盈"], "scenes": ["酒店-客房"], "portraits": []},
         "line_seq": 5},
        {"op": "scene", "id": "s00_酒店", "scene": "酒店-客房", "time": "清晨"},
        {"id": "L0001", "op": "narrate", "text": "清晨。"},
        {"id": "L0002", "op": "say", "who": "陆择", "portrait": "慵懒", "pos": "left", "text": "早。"},
        {"id": "L0003", "op": "say", "who": "顾盈", "portrait": "挑眉", "pos": "right", "text": "醒了。"},
        {"id": "L0004", "op": "say", "who": "陆择", "portrait": "玩味", "pos": "left", "text": "嗯。"},
    ]


def test_make_voice_key_format():
    assert vb.make_voice_key("陆择", "chapter00_序章", "s00_酒店", "L0002") == \
        "陆择-chapter00_序章-s00_酒店-L0002"


def _keys(rows, only=(), line_ids=()):
    tasks = vb.collect_section_tasks(rows, "chapter00_序章", only=only, line_ids=line_ids)
    return {it["line_id"]: it["key"] for items in tasks.values() for it in items}


def test_voice_key_stable_across_insert_and_delete():
    """漂移冒烟（核心契约）：插入/删除任意行，未变行的 key 不变——替代旧 line_idx 位置寻址。"""
    rows = _rows()
    before = _keys(rows)

    # 在 L0002 与 L0003 之间插入一行（取水位 L0005 作 id，水位 +1）
    inserted = {"id": jsonl_script.alloc_line_id(rows), "op": "say",
                "who": "顾盈", "portrait": "玩味", "pos": "right", "text": "插句。"}
    rows.insert(4, inserted)
    after_insert = _keys(rows)
    for lid, key in before.items():
        assert after_insert[lid] == key, f"插入行后 {lid} 的 key 漂移了"

    # 删除 L0002，其余 key 仍不变
    rows = [r for r in rows if r.get("id") != "L0002"]
    after_delete = _keys(rows)
    for lid, key in before.items():
        if lid == "L0002":
            continue
        assert after_delete[lid] == key, f"删除行后 {lid} 的 key 漂移了"


def test_collect_section_tasks_only_filter():
    rows = _rows()
    jsonl_script.set_audio(rows, "L0002", key="k2", status="approved", attempts=1, resha1=True)
    jsonl_script.set_audio(rows, "L0003", key="k3", status="rejected", attempts=2, resha1=True)
    jsonl_script.set_audio(rows, "L0004", key="k4", status="pending", attempts=1, resha1=True)
    jsonl_script.find_row(rows, "L0004")["text"] = "改过的台词"  # L0004 → stale

    picked = _keys(rows, only=("missing", "rejected", "stale"))
    assert sorted(picked) == ["L0003", "L0004"]  # L0002 approved 不重配
    # key 由行 id 重算（单一源 make_voice_key），rejected 行重配前后 key 不变
    assert picked["L0003"] == "顾盈-chapter00_序章-s00_酒店-L0003"
    # 全量（无过滤）含全部 say
    assert sorted(_keys(rows)) == ["L0002", "L0003", "L0004"]


def test_collect_section_tasks_lines_whitelist():
    rows = _rows()
    picked = _keys(rows, line_ids=("L0003",))
    assert sorted(picked) == ["L0003"]
    tasks = vb.collect_section_tasks(rows, "chapter00_序章", line_ids=("L0003",))
    assert list(tasks.keys()) == ["顾盈"]  # 按角色分组
    assert tasks["顾盈"][0]["line_id"] == "L0003"


def test_bind_audio_writes_pending_and_attempts(tmp_path):
    p = tmp_path / "台词.jsonl"
    jsonl_script.save(p, _rows())
    tasks = vb.collect_section_tasks(jsonl_script.load(p), "chapter00_序章")
    # 模拟 skill 判别 emotion 后写入 tasks
    for items in tasks.values():
        for it in items:
            it["emotion"] = "调侃"
    stats = vb.bind_audio(p, tasks)
    assert stats == {"bound": 3, "skipped": 0}

    rows = jsonl_script.load(p)
    a = jsonl_script.find_row(rows, "L0002")["audio"]
    assert a == {"key": "陆择-chapter00_序章-s00_酒店-L0002", "emotion": "调侃",
                 "status": "pending", "attempts": 1,
                 "text_sha1": jsonl_script.text_sha1("早。")}

    # 重生成一次：attempts 递增
    vb.bind_audio(p, tasks)
    assert jsonl_script.find_row(jsonl_script.load(p), "L0002")["audio"]["attempts"] == 2

    # keys 过滤（cosyvoice 失败句排除）
    stats = vb.bind_audio(p, tasks, keys=["陆择-chapter00_序章-s00_酒店-L0002"])
    assert stats == {"bound": 1, "skipped": 2}
