"""显式定义 status 流转规则与 enum 词表（不解析 .md）。"""

# -1 作废重做（sync 级联重置后）；0 待处理；生产态 1/2；审批专属 10 待审 / 11 批准；驳回归 0。
# Chapter 例外：拆为 结构(1→10→11) / 提纲(20) / 定稿(30→31) 三段，两道审批，completion=31。
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
    # 剧情（Chapter 三段式：结构审 + 定稿审两道审批）
    "Chapter":             {"legal": [-1, 0, 1, 10, 11, 20, 30, 31], "completion": 31, "has_approval": True},
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
}


def completion_status(label):
    return NODE_STATUS.get(label, {}).get("completion")


def has_approval(label):
    return NODE_STATUS.get(label, {}).get("has_approval", False)


def is_approved(status):
    return status == 11


def can_submit(label, current_status):
    """只有有审批的节点，在完成态时才能提交审批。无 status 字段的节点（如 Character）返回 False。

    Chapter 例外：结构段在 status=1（结构就绪）时 submit→10（结构待审）；
    定稿段(30)由 chapter-dialoguer 直接写入，不经 submit。
    """
    if not has_approval(label):
        return False
    if current_status is None:
        return False
    if label == "Chapter":
        return current_status == 1
    return current_status == completion_status(label)
