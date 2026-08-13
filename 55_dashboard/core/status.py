"""显式定义 status 流转规则与 enum 词表（不解析 .md）。"""

# -1 作废重做（sync 级联重置后）；0 待处理；生产态 1/2；审批专属 10 待审 / 11 批准；驳回归 0。
# 剧情两层：Chapter 章级结构段（1→10→11，completion=11）；Section 节级提纲/定稿/配音段（20→30→31→32→33，completion=33）。
NODE_STATUS = {
    "AppearanceStyle":     {"legal": [-1, 0, 1],          "completion": 1, "has_approval": False},
    "LanguageStyle":       {"legal": [-1, 0, 1],          "completion": 1, "has_approval": False},
    "CostumeStyle":        {"legal": [-1, 0, 1],          "completion": 1, "has_approval": False},
    "DesignSheet":         {"legal": [-1, 0, 1, 2, 10, 11], "completion": 2, "has_approval": True},
    "IllusDesign":         {"legal": [-1, 0, 1, 2, 10, 11], "completion": 2, "has_approval": True},
    "StandingIllustration":{"legal": [-1, 0, 1, 2, 10, 11], "completion": 2, "has_approval": True},
    # 场景美术
    "Scene":               {"legal": [-1, 0, 1],            "completion": 1, "has_approval": False},
    "SceneLayer":          {"legal": [-1, 0, 1, 2, 10, 11], "completion": 2, "has_approval": True},
    # 剧情（Chapter 章级结构审 + Section 节级定稿审，各一道审批）
    "Chapter":             {"legal": [-1, 0, 1, 10, 11],          "completion": 11, "has_approval": True},
    "Section":             {"legal": [-1, 0, 20, 30, 31, 32, 33], "completion": 33, "has_approval": True},
    # 声音（角色基线音色档案，无审批；VoiceDesign 设计 + clone prompt 固化即 status=1）
    "VoiceProfile":        {"legal": [-1, 0, 1],                  "completion": 1, "has_approval": False},
}

ENUM_OPTIONS = {
    "gender": ["男", "女"],
    "type": ["行动", "交流", "转折", "状态变化"],
    "knowledge_level": ["1", "2", "3"],
    "priority": ["P0", "P1", "P2"],
    "scene_type": ["dialogue", "functional", "combat", "ui"],
    "layer_type": ["background", "floor", "decor", "mask"],
}

STATUS_LABEL = {
    -1: "需重做", 0: "待处理", 1: "已完成", 2: "图片完成",
    10: "待审", 11: "批准",
    20: "提纲就绪", 30: "定稿待审", 31: "定稿已批",
    32: "声音待审", 33: "声音已批",
}


def completion_status(label):
    return NODE_STATUS.get(label, {}).get("completion")


def has_approval(label):
    return NODE_STATUS.get(label, {}).get("has_approval", False)


def is_approved(status, label=None):
    """已批准态：通用审批 11；Section 定稿已批 31 / 声音已批 33。

    注意美术节点（DesignSheet/IllusDesign/StandingIllustration/SceneLayer）的 completion=2
    是历史遗留死值，实际审批走 10→11，故此处按「status==11」而非 completion_status 判定，
    避免把 11 误判为未批准。Section 的 32（声音待审）不算已批。
    """
    if status == 11:
        return True
    if label == "Section" and status in (31, 33):
        return True
    return False


def can_submit(label, current_status):
    """只有有审批的节点，在完成态时才能提交审批。无 status 字段的节点（如 Character）返回 False。

    Chapter：结构段在 status=1（结构就绪）时 submit→10（结构待审）。
    Section：定稿段(30)由 chapter-dialoguer 直接写入，不经 submit；completion=31 但禁止 submit
    （否则 status==31 时 can_submit 会返回 True，submit 把已批节回退到 10 毁数据）。
    """
    if not has_approval(label):
        return False
    if current_status is None:
        return False
    if label == "Chapter":
        return current_status == 1
    if label == "Section":
        return False
    return current_status == completion_status(label)
