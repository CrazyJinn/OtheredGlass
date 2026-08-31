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
    """全图统一：status==11 即已批（含剧情产物 SecScript/LineAudio），无 label 特例。"""
    assert status.is_approved(11) is True
    assert status.is_approved(11, "SecScript") is True
    assert status.is_approved(11, "LineAudio") is True
    assert status.is_approved(2) is False
    assert status.is_approved(1, "SecOutline") is False   # 提纲就绪非审批态
    assert status.is_approved(10, "SecScript") is False   # 待审不算已批


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


def test_chapter_structural_status():
    """Chapter 章级结构段：0→10→11，structurer 生产完成直写 10（无 submit 步），completion=11。"""
    assert status.completion_status("Chapter") == 11
    assert status.has_approval("Chapter") is True
    # 结构段生产完成直写 10（待审），任何状态都无 submit 通道
    assert status.can_submit("Chapter", 1) is False  # 旧「结构就绪」态已废弃（legal 亦不含 1）
    assert status.can_submit("Chapter", 0) is False
    assert status.can_submit("Chapter", 10) is False   # 结构待审
    assert status.can_submit("Chapter", 11) is False   # 结构已批


def test_outline_status():
    """SecOutline 节级提纲产物：0→1 无审批，completion=1。"""
    assert status.completion_status("SecOutline") == 1
    assert status.has_approval("SecOutline") is False
    assert status.can_submit("SecOutline", 0) is False
    assert status.can_submit("SecOutline", 1) is False   # 无审批


def test_script_status():
    """SecScript 节级定稿产物：0→1→10→11 一道定稿审，dialoguer 直写 10 不经 submit。"""
    assert status.completion_status("SecScript") == 11
    assert status.has_approval("SecScript") is True
    # 定稿(10)由 dialoguer 直写不经 submit；1 是草稿态，重跑 dialoguer 提审，不走 submit
    assert status.can_submit("SecScript", 0) is False
    assert status.can_submit("SecScript", 1) is False
    assert status.can_submit("SecScript", 10) is False
    assert status.can_submit("SecScript", 11) is False   # 已批不可被 submit 回退


def test_voiceover_status():
    """LineAudio 节级配音产物：0→10→11 一道声音审，voice-publisher 直写 10 不经 submit。"""
    assert status.completion_status("LineAudio") == 11
    assert status.has_approval("LineAudio") is True
    assert status.can_submit("LineAudio", 0) is False
    assert status.can_submit("LineAudio", 10) is False
    assert status.can_submit("LineAudio", 11) is False


def test_legacy_section_values_removed():
    """Section 已拆为产物链（Section 无 status）；旧专属值 20-33 从词表移除。"""
    assert "Section" not in status.NODE_STATUS
    for v in (20, 30, 31, 32, 33):
        assert v not in status.STATUS_LABEL


def test_voicedesign_status():
    """VoiceDesign 角色基线音色：1=instruct 完成，10=ref_audio 固化即待审（生产完成直写，无 submit 步）。"""
    assert status.completion_status("VoiceDesign") == 10
    assert status.has_approval("VoiceDesign") is True
    assert status.can_submit("VoiceDesign", 1) is False  # 仅文本设计未固化可听载体
    assert status.can_submit("VoiceDesign", 2) is True   # 存量旧流程生产态，保留 submit 迁移通道
    assert status.can_submit("VoiceDesign", 10) is False  # 已待审，无需再提交
    assert status.can_submit("VoiceDesign", 11) is False  # 已批不可被 submit 回退
