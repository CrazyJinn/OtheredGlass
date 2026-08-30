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


# ── ambient 行（环境音，与 say 同走 0→10→11 行级音频审）──

def test_ambient_line_state():
    assert sl.line_state(_line(op="ambient", status=0, attempts=None)) == "missing"
    assert sl.line_state(_line(op="ambient", status=10, attempts=1)) == "pending"
    assert sl.line_state(_line(op="ambient", status=11, attempts=1)) == "approved"
    assert sl.line_state(_line(op="ambient", status=-1, attempts=1)) == "void"


def test_ambient_counts_into_gate():
    """ambient 行进节完成 gate：未批 ambient 挡住整节，全批后通过。"""
    lines = [_line(op="scene", nid="S"), _line(status=11, attempts=1, nid="A"),
             _line(op="ambient", status=10, attempts=1, nid="AMB")]
    c = sl.say_counts(lines)
    assert c["say"] == 2 and c["pending"] == 1
    assert not sl.all_approved(lines)
    lines[-1]["status"] = 11
    assert sl.all_approved(lines)


def test_ambient_reject_section_included():
    """整节驳回把 ambient 行一并置 0（mock repo 验证 id 集合）。"""
    import core.script_lines as sl_mod

    captured = {}

    class _MockRepo:
        def set_status_batch(self, ids, status):
            captured["ids"], captured["status"] = ids, status

    orig = sl_mod.graph_repo
    sl_mod.graph_repo = _MockRepo()
    try:
        lines = [_line(status=11, attempts=1, nid="A"),
                 _line(op="narrate", nid="N"),
                 _line(op="ambient", status=11, attempts=1, nid="AMB")]
        n = sl.reject_section(lines)
        assert n == 2 and set(captured["ids"]) == {"A", "AMB"} and captured["status"] == 0
    finally:
        sl_mod.graph_repo = orig


# ── 氛围型 narrate（旁白内嵌【环境音】，带 ambient_text 的 narrate 是音频行）──

def test_ambient_narrate_is_audio_line():
    """带 ambient_text 的 narrate 进分类/统计/驳回；纯 narrate 不进。"""
    amb_n = _line(op="narrate", nid="AN", text="正文")
    amb_n["ambient_text"] = "雨声渐密"
    assert sl.line_state(amb_n) == "missing"            # status=0 未产
    amb_n["status"], amb_n["attempts"] = 10, 1
    assert sl.line_state(amb_n) == "pending"
    assert sl.say_counts([amb_n])["say"] == 1           # 进 gate 口径
    assert sl.say_counts([_line(op="narrate", nid="P")])["say"] == 0  # 纯旁白不进
    lines = [amb_n, _line(op="narrate", nid="P", status=11)]
    lines[0]["status"] = 11
    assert sl.all_approved(lines)                        # 氛围旁白 11 + 纯旁白（不计）→ 通过


# ── master_wav_path（审批试听源 = 母带 15_声音/，运行时副本归发布期）──

def test_master_wav_path_say_and_ambient():
    """say 行用 voice_key、ambient/narrate 声景行用 ambient_track，路径段从 key 解析。"""
    say = {"op": "say", "voice_key": "陆择-chapter00_序章-s00_酒店-Nv93TkkkgC"}
    assert sl.master_wav_path(say) == sl._MASTER_ROOT / "chapter00_序章" / "s00_酒店" \
        / "陆择-chapter00_序章-s00_酒店-Nv93TkkkgC.wav"
    amb = {"op": "narrate", "ambient_track": "amb-chapter00_序章-s01_路口-Pz3xmsRauP"}
    assert sl.master_wav_path(amb) == sl._MASTER_ROOT / "chapter00_序章" / "s01_路口" \
        / "amb-chapter00_序章-s01_路口-Pz3xmsRauP.wav"


def test_master_wav_path_none_cases():
    """无 key / 键段数不足（char 段缺失）→ None（UI 走缺文件提示）。"""
    assert sl.master_wav_path({"op": "say"}) is None
    assert sl.master_wav_path({"op": "say", "voice_key": "chapter00_序章-s00_酒店-N1"}) is None


def test_master_wav_path_matches_skill_voice_bundler():
    """与 skill 侧 voice_bundler.voice_master_path 同规（跨实现一致性锁定，
    照 test_voice_bundler_graph 的 sys.path 先例 import）。"""
    import sys
    from pathlib import Path
    from config import settings

    root = Path(__file__).resolve().parents[2]
    for p in (root / ".claude" / "skills" / "section-voice-publisher" / "scripts",):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import voice_bundler as vb  # noqa: E402

    for key in ("陆择-chapter00_序章-s00_酒店-Nv93TkkkgC",
                "amb-chapter00_序章-s01_路口-Pz3xmsRauP",
                "Eve-黑伞-chapter01_新皮肤-s02_夹缝-PxSB6uJTm6"):
        assert sl.master_wav_path({"voice_key": key}) == vb.voice_master_path(settings.PROJECT_ROOT, key)
