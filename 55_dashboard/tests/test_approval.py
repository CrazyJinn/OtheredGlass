import pytest
from core import approval


def test_submit_at_completion_returns_10():
    assert approval.submit("DesignSheet", 2) == 10


def test_submit_rejects_wrong_status():
    with pytest.raises(approval.IllegalTransition):
        approval.submit("DesignSheet", 0)
    with pytest.raises(approval.IllegalTransition):
        approval.submit("DesignSheet", 11)


def test_submit_rejects_no_approval_label():
    with pytest.raises(approval.IllegalTransition):
        approval.submit("AppearanceStyle", 1)
    with pytest.raises(approval.IllegalTransition):
        approval.submit("CostumeStyle", 1)


def test_approve_and_reject_default():
    # 通用待审(10) → 批准(11)；驳回 → 0
    assert approval.approve(10) == 11
    assert approval.reject(10) == 0


def test_chapter_structural_approval():
    """Chapter 结构审：10→11 通过；驳回→0。"""
    assert approval.approve(10) == 11   # 结构审通过
    assert approval.reject(10) == 0     # 结构审驳回→0


def test_chapter_no_submit_channel():
    """Chapter 结构段：structurer 生产完成直写 10，任何状态都无 submit 通道。"""
    with pytest.raises(approval.IllegalTransition):
        approval.submit("Chapter", 1)   # 旧「结构就绪」存量态也不再可 submit
    with pytest.raises(approval.IllegalTransition):
        approval.submit("Chapter", 0)
    with pytest.raises(approval.IllegalTransition):
        approval.submit("Chapter", 11)  # 结构已批不可 submit


def test_on_edit_reverts_approved():
    assert approval.on_edit("DesignSheet", 11) == 0
    assert approval.on_edit("Chapter", 11) == 0


def test_on_edit_script_and_voiceover_revert_to_zero():
    """编辑已批剧情产物 → 回 0 重做；产物链上下游作废由 cascade 沿 produces 边完成，此处只管自身。"""
    assert approval.on_edit("SecScript", 11) == 0
    assert approval.on_edit("LineAudio", 11) == 0


def test_on_edit_keeps_other():
    assert approval.on_edit("DesignSheet", 2) is None
    assert approval.on_edit("DesignSheet", 10) is None
    assert approval.on_edit("DesignSheet", 0) is None
    assert approval.on_edit("SecScript", 10) is None      # 待审不回退
    assert approval.on_edit("LineAudio", 10) is None
    assert approval.on_edit("SecOutline", 1) is None      # 无审批，就绪不回退（级联由 cascade 管）


def test_script_approval():
    """SecScript 定稿审：dialoguer 直写 10 → approve 11；驳回 10→0（只重写定稿，SecOutline 不动）。"""
    assert approval.approve(10) == 11
    assert approval.reject(10) == 0


def test_submit_rejects_script_and_voiceover():
    """SecScript/LineAudio 禁止 submit（定稿 10 由 dialoguer 直写、声音 10 由 section-voice-publisher 直写）。"""
    with pytest.raises(approval.IllegalTransition):
        approval.submit("SecScript", 1)    # 草稿态不走 submit，重跑 dialoguer 提审
    with pytest.raises(approval.IllegalTransition):
        approval.submit("SecScript", 10)
    with pytest.raises(approval.IllegalTransition):
        approval.submit("LineAudio", 0)
    with pytest.raises(approval.IllegalTransition):
        approval.submit("LineAudio", 10)


def test_voiceover_approval():
    """LineAudio 声音审：voice-publisher 直写 10 → approve 11；驳回 10→0 只重配（SecScript 不动）。"""
    assert approval.approve(10) == 11
    assert approval.reject(10) == 0


def test_resubmit_approved_to_pending():
    """SecScript 人工微调回路：已批(11)→重新提交(10)；其他状态非法。"""
    assert approval.resubmit("SecScript", 11) == 10
    with pytest.raises(approval.IllegalTransition):
        approval.resubmit("SecScript", 10)
    with pytest.raises(approval.IllegalTransition):
        approval.resubmit("SecScript", 0)
    with pytest.raises(approval.IllegalTransition):
        approval.resubmit("SecScript", 1)
