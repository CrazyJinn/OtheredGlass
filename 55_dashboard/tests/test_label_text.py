from ui.components.label_text import (
    LABEL_CN, CHAR_ORDER, SCENE_ORDER, label_cn, rank,
)


def test_label_cn_known_labels():
    assert label_cn("AppearanceStyle") == "外貌风格"
    assert label_cn("LanguageStyle") == "语言风格"
    assert label_cn("CostumeStyle") == "着装"
    assert label_cn("DesignSheet") == "设计图"
    assert label_cn("IllusDesign") == "插画设计"
    assert label_cn("StandingIllustration") == "立绘"
    assert label_cn("Scene") == "场景"
    assert label_cn("SceneLayer") == "图层"


def test_label_cn_unknown_returns_raw():
    assert label_cn("SomethingElse") == "SomethingElse"


def test_rank_char_order():
    assert rank("AppearanceStyle", CHAR_ORDER) == 0
    assert rank("LanguageStyle", CHAR_ORDER) == 1
    assert rank("CostumeStyle", CHAR_ORDER) == 2
    assert rank("VoiceDesign", CHAR_ORDER) == 3
    assert rank("StandingIllustration", CHAR_ORDER) == 6


def test_rank_scene_order():
    assert rank("Scene", SCENE_ORDER) == 0
    assert rank("SceneLayer", SCENE_ORDER) == 1


def test_rank_unknown_is_high():
    assert rank("Unknown", CHAR_ORDER) == 99
    assert rank("Scene", CHAR_ORDER) == 99  # 场景 label 不在角色 order 里
