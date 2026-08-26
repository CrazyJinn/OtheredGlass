"""审批状态机：submit/approve/reject + 编辑回退规则。

全图统一：待审 10 → 批准 11，驳回 10 → 0。剧情产物 SecScript（定稿审）与 LineAudio（声音审）
由生产 skill 直写 10、不走 submit；节级产物链的上下游作废由 sync 级联（cascade.py）沿
produces 边完成，审批互不牵连。
"""
from core import status


class IllegalTransition(Exception):
    pass


def submit(label, current_status):
    if not status.can_submit(label, current_status):
        raise IllegalTransition(f"{label} status={current_status} 不可提交审批")
    return 10  # 结构待审（Chapter 结构段）/ 通用待审


def approve(current_status):
    """通过：待审(10)→批准(11)，全图通用。"""
    return {10: 11}.get(current_status, 11)


def reject(current_status):
    """驳回：待审(10)→0 重做。

    剧情产物链各节点独立——驳回 SecScript 只重写定稿（SecOutline 不动）；驳回 LineAudio 只重配
    （台词不变，重跑 section-voice-publisher 覆盖 wav；SecScript 不动）。
    """
    return 0


def resubmit(label, current_status):
    """重新提交审批（SecScript 人工微调回路）：已批(11)→待审(10)，其他状态非法。

    用户直接编辑台词 JSONL 后点「重新提交审批」：SecScript 11→10 重走定稿审；
    台词已变 → LineAudio 由回调方置 -1（stale 机制后续只重配被改句）。
    """
    if current_status != 11:
        raise IllegalTransition(f"{label} status={current_status} 不可重新提交（仅已批 11）")
    return 10


def on_edit(label, current_status):
    """编辑节点时：已批准(11)则回退 0，否则不改（返回 None）。

    编辑已批 SecScript → SecScript 回 0 重做定稿，且 cascade 沿 produces 边把 LineAudio 重置 -1
    （台词变会致 voice key 的 line_idx 漂移，必须重配）；编辑已就绪 SecOutline → 自身无审批不回退，
    cascade 沿 produces 链把 SecScript/LineAudio 重置 -1。产物链上下游作废由 cascade 完成，此处只管自身。
    """
    if not status.is_approved(current_status, label):
        return None
    return 0
