"""graph_repo 测试：用 mock session 验证 Cypher 与返回映射。"""
from unittest.mock import MagicMock
from repo import graph_repo


def _fake_session(records):
    """返回一个 mock session，run() 返回含 records 的 result；支持 `with sess as s`。"""
    sess = MagicMock()
    sess.__enter__.return_value = sess   # 让 `with sess as s` 中 s 就是 sess
    result = MagicMock()
    result.__iter__ = lambda self: iter(records)
    result.single.return_value = records[0] if records else None
    sess.run.return_value = result
    return sess


def test_get_node_maps_record(monkeypatch):
    rec = {"id": "N1", "label": "Character", "props": {"name": "陆择"}}
    sess = _fake_session([rec])
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    node = graph_repo.get_node("N1")
    assert node["id"] == "N1"
    assert node["label"] == "Character"
    assert node["name"] == "陆择"


def test_set_status_batch_uses_unwind(monkeypatch):
    sess = _fake_session([])
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    graph_repo.set_status_batch(["N1", "N2"], 0)
    cypher = sess.run.call_args[0][0]
    assert "UNWIND" in cypher and "$ids" in cypher
    assert sess.run.call_args[1]["ids"] == ["N1", "N2"]
    assert sess.run.call_args[1]["status"] == 0


def test_get_pending_approvals_filters_status_10(monkeypatch):
    recs = [{"id": "X", "label": "DesignSheet", "status": 10}]
    sess = _fake_session(recs)
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    out = graph_repo.get_pending_approvals()
    assert out == recs
    assert "n.status=10" in sess.run.call_args[0][0]


def test_get_sync_downstream_filters_sync_true(monkeypatch):
    recs = [{"id": "D1", "label": "DesignSheet", "status": 2}]
    sess = _fake_session(recs)
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    out = graph_repo.get_sync_downstream("A1")
    assert out == recs
    cypher = sess.run.call_args[0][0]
    assert "sync = true" in cypher or "sync=true" in cypher
