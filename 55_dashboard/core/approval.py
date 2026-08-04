"""审批状态机：submit/approve/reject + 编辑回退规则。

Chapter 有两道审批：结构审（submit 1→10，approve 10→11）与定稿审（dialoguer 直写 30，approve 30→31）。
故 approve/reject 按 current_status 决定目标值。
"""
from core import status


class IllegalTransition(Exception):
    pass


def submit(label, current_status):
    if not status.can_submit(label, current_status):
        raise IllegalTransition(f"{label} status={current_status} 不可提交审批")
    return 10  # 结构待审（Chapter 结构段）/ 通用待审


def approve(current_status):
    """通过：结构待审(10)/通用待审(10)→批准(11)；定稿待审(30)→定稿已批(31)。"""
    return {10: 11, 30: 31}.get(current_status, 11)


def reject(current_status):
    """驳回：定稿待审(30)→回提纲就绪(20)重写对话（提纲不重做）；其他→0。"""
    if current_status == 30:
        return 20
    return 0


def on_edit(label, current_status):
    """编辑节点时：已批准则回退，否则不改（返回 None）。

    - Section 定稿已批(31)→回提纲就绪(20)：保留提纲，重做定稿（Section 的 sync 出边 contains
      为 sync=false，编辑 Section 不级联到 Scene，仅自身回退）。
    - 其余已批准(11)→回 0（结构/美术重做）。
    """
    if not status.is_approved(current_status, label):
        return None
    if label == "Section":
        return 20
    return 0
