"""graph_repo 测试：用 mock session 验证 Cypher 与返回映射。"""
from unittest.mock import MagicMock

import pytest

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


def test_export_csv_all_returns_data_field(monkeypatch):
    rec = {"n": 5, "r": 3, "data": '"_id","_labels","name"\n"1",":Character","陆择"\n'}
    sess = _fake_session([rec])
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    csv_text, stats = graph_repo.export_csv_all()
    assert "_id" in csv_text and "陆择" in csv_text
    assert stats == {"nodes": 5, "relationships": 3}
    cypher = sess.run.call_args[0][0].replace(" ", "")
    assert "apoc.export.csv.all(null" in cypher
    assert "stream:true" in cypher


def test_export_csv_all_empty_data_raises(monkeypatch):
    rec = {"n": 0, "r": 0, "data": ""}
    sess = _fake_session([rec])
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    with pytest.raises(RuntimeError):
        graph_repo.export_csv_all()


def test_export_csv_all_pure_fallback(monkeypatch):
    node_recs = [{"id": "C1", "labels": ["Character"], "props": {"name": "陆择"}}]
    rel_recs = [{"start": "C1", "end": "A1", "type": "has_appearance", "props": {"sync": True}}]
    sess = MagicMock()
    sess.__enter__.return_value = sess
    r1, r2 = MagicMock(), MagicMock()
    r1.__iter__ = lambda self: iter(node_recs)
    r2.__iter__ = lambda self: iter(rel_recs)
    sess.run.side_effect = [r1, r2]  # 两次 run：节点、边
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    csv_text, stats = graph_repo.export_csv_all_pure()
    assert "节点" in csv_text and "陆择" in csv_text
    assert "边" in csv_text and "has_appearance" in csv_text
    assert stats == {"nodes": 1, "relationships": 1}


def test_get_location_graph_uses_scene_edges(monkeypatch):
    """get_location_graph 沿 _SCENE_EDGES 白名单遍历，起点 Location。"""
    sess = MagicMock()
    sess.__enter__.return_value = sess
    r1, r2, r3 = MagicMock(), MagicMock(), MagicMock()
    r1.__iter__ = lambda self: iter([{"id": "S1"}, {"id": "L1"}])
    r2.__iter__ = lambda self: iter([
        {"id": "S1", "label": "Scene", "status": 0, "name": "咖啡店-点餐台"},
        {"id": "L1", "label": "SceneLayer", "status": 0, "name": "咖啡店-点餐台-背景"},
    ])
    r3.__iter__ = lambda self: iter([
        {"f": "S1", "t": "L1", "ty": "has_layer", "sync": True},
    ])
    sess.run.side_effect = [r1, r2, r3]
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)

    g = graph_repo.get_location_graph("LOC1")
    first_cypher = sess.run.call_args_list[0][0][0]
    assert "has_scene" in first_cypher and "has_layer" in first_cypher
    assert "Location" in first_cypher
    assert sess.run.call_args_list[0][1]["id"] == "LOC1"
    assert len(g["nodes"]) == 2
    assert g["nodes"][0]["label"] == "Scene"
    assert len(g["edges"]) == 1
    assert g["edges"][0]["type"] == "has_layer"


def test_get_location_graph_empty_ids_returns_empty(monkeypatch):
    """无场景节点时返回空，不发起后续查询。"""
    sess = _fake_session([])
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    g = graph_repo.get_location_graph("LOC1")
    assert g == {"nodes": [], "edges": []}


def test_get_upstream_location_id_uses_scene_edges(monkeypatch):
    sess = _fake_session([{"lid": "LOC1"}])
    monkeypatch.setattr(graph_repo, "_session", lambda: sess)
    assert graph_repo.get_upstream_location_id("S1") == "LOC1"
    cypher = sess.run.call_args[0][0]
    assert "has_scene" in cypher and "Location" in cypher
