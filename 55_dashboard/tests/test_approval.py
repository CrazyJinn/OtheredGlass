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


def test_approve_and_reject():
    assert approval.approve() == 11
    assert approval.reject() == 0


def test_on_edit_reverts_approved():
    assert approval.on_edit(11) == 0


def test_on_edit_keeps_other():
    assert approval.on_edit(2) is None
    assert approval.on_edit(10) is None
    assert approval.on_edit(0) is None
