from core import status


def test_completion_status():
    assert status.completion_status("DesignSheet") == 2
    assert status.completion_status("CostumeStyle") == 1
    assert status.completion_status("AppearanceStyle") == 1


def test_has_approval():
    assert status.has_approval("DesignSheet") is True
    assert status.has_approval("AppearanceStyle") is False
    assert status.has_approval("CostumeStyle") is False


def test_is_approved():
    assert status.is_approved(11) is True
    assert status.is_approved(2) is False


def test_can_submit_only_at_completion():
    assert status.can_submit("DesignSheet", 2) is True
    assert status.can_submit("DesignSheet", 0) is False
    assert status.can_submit("DesignSheet", 11) is False
    assert status.can_submit("AppearanceStyle", 1) is False  # 无审批


def test_enum_options_present():
    assert "男" in status.ENUM_OPTIONS["gender"]
    assert "行动" in status.ENUM_OPTIONS["type"]
