"""台词 JSONL 共享库（jsonl_script）单测：行字节稳定 / 行级校验 / 投影 / 行级音频状态。"""
import json

from core import script_jsonl as js


def _fixture(tmp_path, rows=None):
    """写一份合法的最小台词.jsonl，返回路径。"""
    rows = rows or [
        {"op": "meta", "chapter": 0, "title": "序章·酒店醒来",
         "requires": {"characters": ["陆择"], "scenes": ["酒店-客房"], "portraits": ["陆择.慵懒"]},
         "line_seq": 4},
        {"op": "scene", "id": "s00_酒店", "scene": "酒店-客房", "time": "清晨"},
        {"id": "L0001", "op": "narrate", "text": "清晨，光切进来。"},
        {"id": "L0002", "op": "say", "who": "陆择", "portrait": "慵懒", "pos": "left",
         "text": "……这窗帘，跟没拉有什么区别。"},
        {"id": "L0003", "op": "say", "who": "陆择", "portrait": "玩味", "pos": "left",
         "text": "醒了？"},
    ]
    p = tmp_path / "台词.jsonl"
    js.save(p, rows)
    return p


# ── 读写与字节稳定 ──

def test_save_roundtrip_bytes_stable(tmp_path):
    p = _fixture(tmp_path)
    t1 = p.read_text(encoding="utf-8")
    js.save(p, js.load(p))
    assert p.read_text(encoding="utf-8") == t1


def test_single_line_edit_touches_one_line(tmp_path):
    """单句修改只碰那一行（其余行字节不变）。"""
    p = _fixture(tmp_path)
    before = p.read_text(encoding="utf-8").splitlines()
    rows = js.load(p)
    js.find_row(rows, "L0003")["text"] = "改过的台词"
    js.save(p, rows)
    after = p.read_text(encoding="utf-8").splitlines()
    assert len(before) == len(after)
    diff = [(b, a) for b, a in zip(before, after) if b != a]
    assert len(diff) == 1


# ── 行级校验 ──

def test_validate_ok(tmp_path):
    ok, errors = js.validate(_fixture(tmp_path))
    assert ok, errors


def test_validate_rejects_duplicate_line_id(tmp_path):
    p = _fixture(tmp_path)
    rows = js.load(p)
    rows.append({"id": "L0002", "op": "say", "who": "陆择", "portrait": "慵懒",
                 "pos": "left", "text": "重复 id"})
    js.save(p, rows)
    ok, errors = js.validate(p)
    assert not ok
    assert any("重复" in e for e in errors)


def test_validate_rejects_line_id_over_seq(tmp_path):
    """手改插入行忘 bump 水位 → id ≥ line_seq 报错，且错误信息指向修法。"""
    p = _fixture(tmp_path)
    rows = js.load(p)
    rows.append({"id": "L0099", "op": "say", "who": "陆择", "portrait": "慵懒",
                 "pos": "left", "text": "越过水位的行"})
    js.save(p, rows)
    ok, errors = js.validate(p)
    assert not ok
    assert any("水位" in e for e in errors)


def test_validate_say_missing_field(tmp_path):
    p = _fixture(tmp_path)
    rows = js.load(p)
    del rows[3]["text"]
    js.save(p, rows)
    ok, errors = js.validate(p)
    assert not ok
    assert any("text 必填" in e for e in errors)


def test_validate_say_forbidden_fields(tmp_path):
    """say 不得写 emotion/voice（emotion 配音期判别入 audio.emotion；voice 由 audio.key 投影）。"""
    p = _fixture(tmp_path)
    rows = js.load(p)
    rows[3]["emotion"] = "平静"
    rows[3]["voice"] = "陆择-xxx"
    js.save(p, rows)
    ok, errors = js.validate(p)
    assert not ok
    assert any("不得写 emotion" in e for e in errors)
    assert any("不得写 voice" in e for e in errors)


def test_validate_line_before_scene(tmp_path):
    rows = [
        {"op": "meta", "chapter": 0, "title": "t", "requires": {}, "line_seq": 2},
        {"id": "L0001", "op": "narrate", "text": "悬空旁白"},
    ]
    errors = js.validate_rows(rows)
    assert any("scene 行之前" in e for e in errors)


# ── 投影 ──

def test_project_structure(tmp_path):
    doc = js.project(js.load(_fixture(tmp_path)))
    assert set(doc.keys()) == {"meta", "scenes"}
    assert "line_seq" not in doc["meta"] and doc["meta"]["chapter"] == 0
    blk = doc["scenes"][0]
    assert blk == {"id": "s00_酒店", "scene": "酒店-客房", "time": "清晨", "lines": [
        {"op": "narrate", "text": "清晨，光切进来。"},
        {"op": "say", "who": "陆择", "portrait": "慵懒", "pos": "left",
         "text": "……这窗帘，跟没拉有什么区别。"},
        {"op": "say", "who": "陆择", "portrait": "玩味", "pos": "left", "text": "醒了？"},
    ]}


def test_project_drops_id_and_maps_voice(tmp_path):
    p = _fixture(tmp_path)
    rows = js.load(p)
    js.set_audio(rows, "L0002", key="陆择-chapter00_序章-s00_酒店-L0002",
                 emotion="平静", status="pending", attempts=1, resha1=True)
    doc = js.project(rows)
    say = doc["scenes"][0]["lines"][1]
    assert "id" not in say and "audio" not in say and "emotion" not in say
    assert say["voice"] == "陆择-chapter00_序章-s00_酒店-L0002"


# ── 行级音频状态 ──

def test_line_state_stale(tmp_path):
    p = _fixture(tmp_path)
    rows = js.load(p)
    js.set_audio(rows, "L0002", key="k", status="approved", attempts=1, resha1=True)
    assert js.line_state(js.find_row(rows, "L0002")) == "approved"
    js.find_row(rows, "L0002")["text"] = "改了台词"
    assert js.line_state(js.find_row(rows, "L0002")) == "stale"


def test_needs_regen_picks_missing_rejected_stale(tmp_path):
    p = _fixture(tmp_path)
    rows = js.load(p)
    # L0002 approved 且未改；L0003 rejected
    js.set_audio(rows, "L0002", key="k2", status="approved", attempts=1, resha1=True)
    js.set_audio(rows, "L0003", key="k3", status="rejected", attempts=2, resha1=True)
    ids = [x["id"] for x in js.needs_regen(rows)]
    assert ids == ["L0003"]  # L0001 是 narrate 无音频概念；L0002 approved


def test_needs_regen_includes_stale_after_text_edit(tmp_path):
    p = _fixture(tmp_path)
    rows = js.load(p)
    js.set_audio(rows, "L0002", key="k2", status="approved", attempts=1, resha1=True)
    js.find_row(rows, "L0002")["text"] = "改了"
    ids = [x["id"] for x in js.needs_regen(rows)]
    assert "L0002" in ids and "L0003" in ids  # L0002 stale + L0003 missing


def test_set_audio_attempts_increment(tmp_path):
    p = _fixture(tmp_path)
    rows = js.load(p)
    js.set_audio(rows, "L0002", key="k", status="pending", attempts=1, resha1=True)
    old = dict(js.find_row(rows, "L0002")["audio"])
    js.set_audio(rows, "L0002", key="k2", status="pending",
                 attempts=old["attempts"] + 1, resha1=True)
    assert js.find_row(rows, "L0002")["audio"]["attempts"] == 2


def test_audio_counts_and_gate(tmp_path):
    p = _fixture(tmp_path)
    rows = js.load(p)
    c = js.audio_counts(rows)
    assert c == {"say": 2, "missing": 2, "pending": 0, "approved": 0, "rejected": 0, "stale": 0}
    assert not js.all_approved(rows)
    js.set_audio(rows, "L0002", key="k2", status="approved", attempts=1, resha1=True)
    js.set_audio(rows, "L0003", key="k3", status="approved", attempts=1, resha1=True)
    assert js.all_approved(rows)


def test_reset_all_audio(tmp_path):
    p = _fixture(tmp_path)
    rows = js.load(p)
    js.set_audio(rows, "L0002", key="k2", status="approved", attempts=1, resha1=True)
    js.set_audio(rows, "L0003", key="k3", status="rejected", attempts=1, resha1=True)
    n = js.reset_all_audio(rows)
    assert n == 2
    assert all(js.find_row(rows, i)["audio"]["status"] == "pending" for i in ("L0002", "L0003"))


# ── 行 id 水位 ──

def test_alloc_line_id_advances_seq(tmp_path):
    p = _fixture(tmp_path)
    rows = js.load(p)
    assert js.next_line_id(rows) == "L0004"
    nid = js.alloc_line_id(rows)
    assert nid == "L0004" and rows[0]["line_seq"] == 5
