"""图行（LineAudio 逐句节点）的 dashboard 侧封装：行状态分类 / 审批动作 / 统计。

行级审批写节点 status（11 通过 / 0 驳回）——台词**文字**的审批已在 SecScript 定稿审
（台词.md）完成，行 status 只代表音频审批。stale 不再有图上表现：拆分对齐
（script_splitter.py）把改词句在重拆时归一置 0。

line_state / say_counts / all_approved 是纯函数（dict 输入，不连库，可脱库单测）；
读写走 repo.graph_repo（get_script_lines / set_status / set_status_batch）。
"""
from repo import graph_repo


def get_lines(sc_id):
    """取 SecScript 的逐句行（按 produces.order 升序，含 scene 行 stages→Scene 名/时段）。"""
    return graph_repo.get_script_lines(sc_id)


def line_state(l: dict) -> str:
    """图行音频状态分类（非 say 行返回 ''）：

    missing（status=0 且从未配过 attempts=0）/ rejected（status=0 且配过 attempts>0）/
    pending（10 配完待审）/ approved（11 已通过）/ void（-1 级联作废，待重拆恢复）。
    """
    if l.get("op") != "say":
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
    """say 行音频状态统计（节级审批 gate 用）。"""
    c = {"say": 0, "missing": 0, "pending": 0, "approved": 0, "rejected": 0, "void": 0}
    for l in lines:
        if l.get("op") != "say":
            continue
        c["say"] += 1
        c[line_state(l)] = c.get(line_state(l), 0) + 1
    return c


def all_approved(lines: list) -> bool:
    """节级通过 gate：全部 say 行 status=11（missing/pending/rejected/void 均不允许）。"""
    c = say_counts(lines)
    return c["say"] > 0 and c["approved"] == c["say"]


def set_line_status(node_id, status):
    """单句审批动作（11 通过 / 0 驳回）。"""
    graph_repo.set_status(node_id, status)


def approve_all_pending(lines: list) -> int:
    """批量通过全部待审行（pending→11）。返回处理行数。"""
    ids = [l["id"] for l in lines if line_state(l) == "pending"]
    if ids:
        graph_repo.set_status_batch(ids, 11)
    return len(ids)


def reject_section(lines: list) -> int:
    """整节驳回：全部 say 行置 0（重配语义，台词/已产 wav 不变）。返回处理行数。"""
    ids = [l["id"] for l in lines if l.get("op") == "say" and l.get("status") != 0]
    if ids:
        graph_repo.set_status_batch(ids, 0)
    return len(ids)
