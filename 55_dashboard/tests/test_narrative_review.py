"""叙事审批相关测试：cypher 拆分、多语句写入、建议读取与留痕持久化（不连真实 DB）。"""
import json
from unittest.mock import MagicMock

from config import settings
from core import narrative_review
from repo import graph_repo


# ─── split_cypher_script ──────────────────────────────────────

def test_split_simple_multi():
    out = graph_repo.split_cypher_script("MATCH (a) RETURN 1; MATCH (b) RETURN 2;")
    assert out == ["MATCH (a) RETURN 1", "MATCH (b) RETURN 2"]


def test_split_semicolon_inside_string_not_split():
    cypher = "MERGE (n:X{id:'a;b'}) SET n.t='x;y'; MATCH (n) RETURN n;"
    out = graph_repo.split_cypher_script(cypher)
    assert out == [
        "MERGE (n:X{id:'a;b'}) SET n.t='x;y'",
        "MATCH (n) RETURN n",
    ]


def test_split_line_comment_ignored():
    out = graph_repo.split_cypher_script(
        "// comment\nMATCH (a) RETURN 1;\n// trailing\nMATCH (b) RETURN 2;"
    )
    assert out == ["MATCH (a) RETURN 1", "MATCH (b) RETURN 2"]


def test_split_real_suggestion_node_plus_two_edges():
    # 取自 02_剧情数据 第二条结构：1 条节点 SET + 2 条边 MERGE
    s2 = (
        "MERGE (n:Event{id:'ODWIDpIazg'}) SET n.title='温蔓青行踪追查';"
        "MATCH (n:Event{id:'ODWIDpIazg'}),(c:Character{id:'NvCkQmFPFq'}) "
        "MERGE (c)-[:involved{role:'当事人'}]->(n);"
        "MATCH (n:Event{id:'ODWIDpIazg'}),(w:Character{id:'NvCkQmFPFr'}) "
        "MERGE (w)-[:involved{role:'当事人'}]->(n);"
    )
    out = graph_repo.split_cypher_script(s2)
    assert len(out) == 3
    assert out[0].startswith("MERGE (n:Event")
    assert "involved" in out[1] and "involved" in out[2]


# ─── run_write_script ─────────────────────────────────────────

def _fake_write_session():
    """mock session：execute_write 真正回调 work 并注入 mock tx；支持 with 语法。"""
    sess = MagicMock()
    sess.__enter__.return_value = sess
    tx = MagicMock()
    sess.execute_write.side_effect = lambda work: work(tx)
    return sess, tx


def test_run_write_script_runs_each_statement_in_single_tx(monkeypatch):
    sess, tx = _fake_write_session()
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    n = graph_repo.run_write_script("MATCH (a) SET a.x=1; MATCH (b) SET b.y=2;")
    assert n == 2
    assert tx.run.call_count == 2
    assert tx.run.call_args_list[0].args[0] == "MATCH (a) SET a.x=1"
    assert tx.run.call_args_list[1].args[0] == "MATCH (b) SET b.y=2"
    sess.execute_write.assert_called_once()  # 单事务


def test_run_write_script_empty_skips_db(monkeypatch):
    sess, tx = _fake_write_session()
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    assert graph_repo.run_write_script("   // only comment\n") == 0
    sess.execute_write.assert_not_called()


# ─── narrative_review 读取与留痕 ───────────────────────────────

def _patch_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "NARRATIVE_DATA_DIR", tmp_path)
    monkeypatch.setattr(narrative_review, "REVIEWED_PATH", tmp_path / "_reviewed.json")


def test_load_suggestions_flattens_with_key(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    (tmp_path / "2026-01-01_建议.json").write_text(json.dumps([
        {"check": "x", "priority": "high", "reason": "r", "content": "c", "cypher": "MATCH (a) RETURN 1;"},
        {"check": "y", "priority": "low", "reason": "r2", "content": "c2", "cypher": "MATCH (b) RETURN 2;"},
    ]), encoding="utf-8")
    items = narrative_review.load_suggestions()
    assert [i["key"] for i in items] == ["2026-01-01_建议.json#0", "2026-01-01_建议.json#1"]
    assert items[0]["source_file"] == "2026-01-01_建议.json"
    assert items[0]["index"] == 0
    assert items[0]["cypher"].startswith("MATCH")


def test_load_suggestions_excludes_reviewed_file(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    (tmp_path / "_reviewed.json").write_text(json.dumps({"k": 1}), encoding="utf-8")
    (tmp_path / "2026-01-01_建议.json").write_text(
        json.dumps([{"check": "x", "priority": "high", "cypher": "MATCH (a) RETURN 1;"}]),
        encoding="utf-8",
    )
    items = narrative_review.load_suggestions()
    assert len(items) == 1
    assert items[0]["source_file"] == "2026-01-01_建议.json"


def test_load_suggestions_skips_corrupt(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    (tmp_path / "bad_建议.json").write_text("{not json", encoding="utf-8")
    assert narrative_review.load_suggestions() == []


def test_load_reviewed_missing_returns_empty(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    assert narrative_review.load_reviewed() == {}


def test_mark_reviewed_persists_and_merges(tmp_path, monkeypatch):
    rp = tmp_path / "_reviewed.json"
    _patch_data_dir(tmp_path, monkeypatch)
    narrative_review.mark_reviewed("f.json#0", "approved")
    data = json.loads(rp.read_text(encoding="utf-8"))
    assert data["f.json#0"]["status"] == "approved"
    assert "ts" in data["f.json#0"]

    narrative_review.mark_reviewed("f.json#1", "rejected")
    data = json.loads(rp.read_text(encoding="utf-8"))
    assert data["f.json#0"]["status"] == "approved"   # 前一条保留
    assert data["f.json#1"]["status"] == "rejected"
