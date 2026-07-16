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
    # Chapter 定稿已批(31) 不被 is_approved 认定——on_edit 沿用 ==11，31 的精细回退未实现
    assert status.is_approved(31) is False


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


def test_chapter_three_stage_status():
    """Chapter 三段式：结构(1→10→11) + 提纲(20) + 定稿(30→31)，两道审批，completion=31。"""
    assert status.completion_status("Chapter") == 31
    assert status.has_approval("Chapter") is True
    # 结构段 status=1（结构就绪）可 submit（→10）；其他阶段不可
    assert status.can_submit("Chapter", 1) is True
    assert status.can_submit("Chapter", 0) is False
    assert status.can_submit("Chapter", 11) is False   # 结构已批
    assert status.can_submit("Chapter", 20) is False   # 提纲就绪（无审批）
    assert status.can_submit("Chapter", 30) is False   # 定稿待审（dialoguer 直写，不经 submit）
    assert status.can_submit("Chapter", 31) is False   # 定稿已批


def test_chapter_status_labels():
    assert status.STATUS_LABEL[20] == "提纲就绪"
    assert status.STATUS_LABEL[30] == "定稿待审"
    assert status.STATUS_LABEL[31] == "定稿已批"
