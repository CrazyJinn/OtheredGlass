"""label → 中文显示名 + 排序 rank（纯函数，无 streamlit 依赖，便于单测）。

page_overview 用 CHAR_ORDER，page_scene_overview 用 SCENE_ORDER。
"""
LABEL_CN = {
    "AppearanceStyle": "外貌风格",
    "LanguageStyle": "语言风格",
    "CostumeStyle": "着装",
    "VoiceDesign": "声音设计",
    "DesignSheet": "设计图",
    "IllusDesign": "插画设计",
    "StandingIllustration": "立绘",
    "Scene": "场景",
    "SceneLayer": "图层",
}
CHAR_ORDER = [
    "AppearanceStyle", "LanguageStyle", "CostumeStyle", "VoiceDesign",
    "DesignSheet", "IllusDesign", "StandingIllustration",
]
SCENE_ORDER = ["Scene", "SceneLayer"]


def label_cn(label):
    return LABEL_CN.get(label, label)


def rank(label, order):
    return order.index(label) if label in order else 99
