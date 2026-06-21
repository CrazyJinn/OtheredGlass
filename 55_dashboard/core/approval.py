"""审批状态机：submit/approve/reject + 编辑回退规则。"""
from core import status


class IllegalTransition(Exception):
    pass


def submit(label, current_status):
    if not status.can_submit(label, current_status):
        raise IllegalTransition(f"{label} status={current_status} 不可提交审批")
    return 10


def approve():
    return 11


def reject():
    return 0


def on_edit(current_status):
    """编辑节点时：已批准则回退到 0，否则不改（返回 None）。"""
    if status.is_approved(current_status):
        return 0
    return None
