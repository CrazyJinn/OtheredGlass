"""图行（LineAudio 逐句节点）的 dashboard 侧封装：行状态分类 / 审批动作 / 统计。

行级审批写节点 status（11 通过 / 0 驳回）——台词**文字**的审批已在 SecScript 定稿审
（台词.md）完成，行 status 只代表音频审批。stale 不再有图上表现：拆分对齐
（script_splitter.py）把改词句在重拆时归一置 0。

line_state / say_counts / all_approved 是纯函数（dict 输入，不连库，可脱库单测）；
读写走 repo.graph_repo（get_script_lines / set_status / set_status_batch）。
"""
from pathlib import Path

from config.settings import PROJECT_ROOT
from repo import graph_repo

_SFX_RAW = PROJECT_ROOT / "15_声音" / "sfx_raw"
_MASTER_ROOT = PROJECT_ROOT / "15_声音"


def master_wav_path(l: dict):
    """音频行（say 配音 / ambient 转场 / 带声景标注 narrate）→ 母带 wav 路径（审批试听源）。

    15_声音/<chapter_stem>/<scene_block_id>/<key>.wav——与 skill 侧
    voice_bundler.voice_master_path 同规，纯从 key 解析（key 是落盘位置的单一权威，
    不用行上 scene_block_id 现算——章改名后 key 内旧 stem 才指向旧 wav）；
    无 key 或 key 解析失败（段数≠4）返回 None。两实现一致性由
    tests/test_script_lines.py 对照 voice_bundler 锁定。
    """
    key = l.get("voice_key") or l.get("ambient_track")
    if not key:
        return None
    parts = key.rsplit("-", 3)
    if len(parts) != 4 or not all(p.strip() for p in parts):
        return None
    _, stem, block, _ = parts
    return _MASTER_ROOT / stem / block / f"{key}.wav"


def get_lines(sc_id):
    """取 SecScript 的逐句行（按 produces.order 升序，含 scene 行 stages→Scene 名/时段）。"""
    return graph_repo.get_script_lines(sc_id)


def _is_audio_line(l: dict) -> bool:
    """音频行：say 配音 / transition 转场音效（存量 op=ambient 兼容）/ 带内嵌氛围标注（ambient_text）的 narrate。"""
    op = l.get("op")
    return op == "say" or op in ("transition", "ambient") \
        or (op == "narrate" and bool(l.get("ambient_text")))


def line_state(l: dict) -> str:
    """图行音频状态分类（非音频行返回 ''）：

    missing（status=0 且从未配过 attempts=0）/ rejected（status=0 且配过 attempts>0）/
    pending（10 配完待审）/ approved（11 已通过）/ void（-1 级联作废，待重拆恢复）。
    """
    if not _is_audio_line(l):
        return ""
    st = l.get("status")
    if st == -1:
        return "void"
    if st == 0:
        return "rejected" if (l.get("attempts") or 0) > 0 else "missing"
    if st == 10:
        return "pending"
    if st == 11:
        return "approved"
    return "missing"


def say_counts(lines: list) -> dict:
    """音频行（say 配音 / ambient 转场 / 带氛围标注的 narrate）状态统计（节级审批 gate 用）。
    键名沿用 say（UI 兼容），口径含全部音频行。"""
    c = {"say": 0, "missing": 0, "pending": 0, "approved": 0, "rejected": 0, "void": 0}
    for l in lines:
        if not _is_audio_line(l):
            continue
        c["say"] += 1
        c[line_state(l)] = c.get(line_state(l), 0) + 1
    return c


def all_approved(lines: list) -> bool:
    """节级通过 gate：全部音频行（say/ambient）status=11（missing/pending/rejected/void 均不允许）。"""
    c = say_counts(lines)
    return c["say"] > 0 and c["approved"] == c["say"]


def set_line_status(node_id, status):
    """单句审批动作（11 通过 / 0 驳回）。通过时顺带清理该行环境音参与数据（见下）。"""
    graph_repo.set_status(node_id, status)


def cleanup_after_approval(l: dict) -> list:
    """环境音行批准（11）后清理参与数据：删 sfx_raw 中该 track 登记的原始素材
    （mp3+wav 成对；登记「文件」列写 stem，两个扩展名都试删）；SOURCES.md 文本登记
    保留（Steam 合规留存，重下无损凭登记 URL）。非环境音行/无登记返回空。"""
    track = l.get("ambient_track")
    if not track:
        return []
    src = _SFX_RAW / "SOURCES.md"
    if not src.exists():
        return []
    removed = []
    try:
        for ln in src.read_text(encoding="utf-8").splitlines():
            if track not in ln or not ln.strip().startswith("|"):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            stem = cells[0].rsplit(".", 1)[0] if cells else ""
            if not stem:
                continue
            for ext in (".mp3", ".wav"):
                p = _SFX_RAW / (stem + ext)
                if p.exists():
                    p.unlink()
                    removed.append(p.name)
    except OSError:
        pass
    return removed


def approve_all_pending(lines: list) -> int:
    """批量通过全部待审行（pending→11）。返回处理行数。"""
    ids = [l["id"] for l in lines if line_state(l) == "pending"]
    if ids:
        graph_repo.set_status_batch(ids, 11)
    return len(ids)


def reject_section(lines: list) -> int:
    """整节驳回：全部音频行（say/ambient/带氛围 narrate）置 0（重配语义，台词/已产 wav 不变）。返回处理行数。"""
    ids = [l["id"] for l in lines if _is_audio_line(l) and l.get("status") != 0]
    if ids:
        graph_repo.set_status_batch(ids, 0)
    return len(ids)
