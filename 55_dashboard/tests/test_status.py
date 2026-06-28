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


def test_unknown_label_does_not_raise():
    """无 status 流转的节点（Character/Event 等）不再 KeyError。"""
    assert status.has_approval("Character") is False
    assert status.completion_status("Character") is None
    assert status.can_submit("Character", 0) is False
    assert status.can_submit("Character", None) is False


def test_priority_enum_registered():
    assert status.ENUM_OPTIONS["priority"] == ["P0", "P1", "P2"]


def test_scene_status_registration():
    """Scene 数据节点：无审批，completion=1。"""
    assert status.completion_status("Scene") == 1
    assert status.has_approval("Scene") is False
    assert status.can_submit("Scene", 1) is False  # 无审批


def test_scenelayer_status_registration():
    """SceneLayer 生产节点：有审批，completion=2。"""
    assert status.completion_status("SceneLayer") == 2
    assert status.has_approval("SceneLayer") is True
    assert status.can_submit("SceneLayer", 2) is True
    assert status.can_submit("SceneLayer", 1) is False


def test_scene_enum_options_registered():
    assert status.ENUM_OPTIONS["scene_type"] == ["dialogue", "functional", "combat", "ui"]
    assert status.ENUM_OPTIONS["layer_type"] == ["background", "floor", "decor", "mask"]
