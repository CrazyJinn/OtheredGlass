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


def test_chapter_two_stage_approval():
    """Chapter 两道审批：结构审(10→11)、定稿审(30→31)；定稿驳回→回提纲就绪(20)。"""
    assert approval.approve(10) == 11   # 结构审通过
    assert approval.approve(30) == 31   # 定稿审通过
    assert approval.reject(30) == 20    # 定稿驳回→回提纲就绪重写对话
    assert approval.reject(10) == 0     # 结构审驳回→0


def test_submit_chapter_structural_stage():
    """Chapter 结构段：status=1（结构就绪）可 submit→10。"""
    assert approval.submit("Chapter", 1) == 10


def test_submit_rejects_chapter_other_stages():
    with pytest.raises(approval.IllegalTransition):
        approval.submit("Chapter", 0)
    with pytest.raises(approval.IllegalTransition):
        approval.submit("Chapter", 20)  # 提纲就绪不可 submit
    with pytest.raises(approval.IllegalTransition):
        approval.submit("Chapter", 30)  # 定稿待审不可 submit
    with pytest.raises(approval.IllegalTransition):
        approval.submit("Chapter", 11)  # 结构已批不可 submit


def test_on_edit_reverts_approved():
    assert approval.on_edit(11) == 0


def test_on_edit_keeps_other():
    assert approval.on_edit(2) is None
    assert approval.on_edit(10) is None
    assert approval.on_edit(0) is None
