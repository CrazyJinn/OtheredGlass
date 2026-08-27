"""图行（LineAudio 逐句节点）状态分类/统计纯函数单测（不连 Neo4j）。"""
from core import script_lines as sl


def _line(op="say", status=None, attempts=None, **kw):
    return {"op": op, "status": status, "attempts": attempts, "id": kw.get("nid", "N1"),
            "who": kw.get("who", "陆择"), "text": kw.get("text", "x")}


# ── line_state ──

def test_line_state_nonsay_empty():
    assert sl.line_state(_line(op="narrate")) == ""
    assert sl.line_state(_line(op="scene")) == ""


def test_line_state_missing_vs_rejected():
    """status=0：配过（attempts>0）= 被驳回；从未配 = 未配音。"""
    assert sl.line_state(_line(status=0, attempts=None)) == "missing"
    assert sl.line_state(_line(status=0, attempts=0)) == "missing"
    assert sl.line_state(_line(status=0, attempts=2)) == "rejected"


def test_line_state_pending_approved_void():
    assert sl.line_state(_line(status=10, attempts=1)) == "pending"
    assert sl.line_state(_line(status=11, attempts=1)) == "approved"
    assert sl.line_state(_line(status=-1, attempts=1)) == "void"


# ── say_counts / all_approved ──

def test_say_counts_and_gate():
    lines = [
        _line(op="scene", nid="S"),
        _line(status=10, attempts=1, nid="A"),
        _line(status=0, attempts=2, nid="B"),
        _line(status=0, nid="C"),
        _line(status=-1, attempts=1, nid="D"),
        _line(op="narrate", nid="E"),   # 非 say 不计
    ]
    c = sl.say_counts(lines)
    assert c == {"say": 4, "missing": 1, "pending": 1, "approved": 0, "rejected": 1, "void": 1}
    assert not sl.all_approved(lines)
    fixed = [l if l["id"] != "S" else l for l in lines]
    for l in fixed:
        if l.get("op") == "say":
            l["status"] = 11
    assert sl.all_approved(fixed)


def test_all_approved_requires_say_rows():
    assert not sl.all_approved([])                       # 无 say 行不算通过
    assert not sl.all_approved([_line(op="narrate")])    # 只有旁白不算
