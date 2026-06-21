from core import cascade
from tests.conftest import MockRepo


def _chain():
    """Character -> Appearance -> DesignSheet（全 sync=true），
    DesignSheet -> IllusDesign（sync=false，不在 sync_edges 里）。"""
    r = MockRepo()
    r.add_node("C", "Character", props={})
    r.add_node("A", "AppearanceStyle", status=1)
    r.add_node("D", "DesignSheet", status=11)
    r.add_node("I", "IllusDesign", status=11)
    r.add_sync_edge("C", "A")
    r.add_sync_edge("A", "D")
    return r


def test_cascade_resets_downstream_to_redo():
    r = _chain()
    out = cascade.cascade_reset("C", r)
    ids = {n.id for n in out}
    assert ids == {"A", "D"}
    assert r.nodes["A"]["status"] == -1
    assert r.nodes["D"]["status"] == -1


def test_cascade_does_not_touch_source():
    r = _chain()
    r.nodes["A"]["status"] = 1  # 源是 A 这次
    cascade.cascade_reset("A", r)
    assert r.nodes["A"]["status"] == 1  # 源自身不变
    assert r.nodes["D"]["status"] == -1


def test_cascade_records_levels():
    r = _chain()
    out = cascade.cascade_reset("C", r)
    by_id = {n.id: n.level for n in out}
    assert by_id["A"] == 1
    assert by_id["D"] == 2


def test_cascade_blocked_by_sync_false():
    # D->I 不在 sync_edges，所以 I 不受影响
    r = _chain()
    cascade.cascade_reset("C", r)
    assert r.nodes["I"]["status"] == 11


def test_cascade_empty_when_no_downstream():
    r = MockRepo()
    r.add_node("X", "StandingIllustration", status=2)
    out = cascade.cascade_reset("X", r)
    assert out == []
    assert r.status_calls == []
