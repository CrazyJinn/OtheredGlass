"""显式定义 status 流转规则与 enum 词表（不解析 .md）。"""

# -1 作废重做（sync 级联重置后）；0 首次待生成；生产态 1/2；审批专属 10 待审 / 11 批准。驳回归 0。
NODE_STATUS = {
    "AppearanceStyle":     {"legal": [-1, 0, 1],          "completion": 1, "has_approval": False},
    "LanguageStyle":       {"legal": [-1, 0, 1],          "completion": 1, "has_approval": False},
    "CostumeStyle":        {"legal": [-1, 0, 1],          "completion": 1, "has_approval": False},
    "DesignSheet":         {"legal": [-1, 0, 1, 2, 10, 11], "completion": 2, "has_approval": True},
    "IllusDesign":         {"legal": [-1, 0, 1, 2, 10, 11], "completion": 2, "has_approval": True},
    "StandingIllustration":{"legal": [-1, 0, 1, 2, 10, 11], "completion": 2, "has_approval": True},
}

ENUM_OPTIONS = {
    "gender": ["男", "女"],
    "type": ["行动", "交流", "转折", "状态变化"],
    "knowledge_level": ["1", "2", "3"],
}

STATUS_LABEL = {
    -1: "需重做", 0: "待处理", 1: "已完成", 2: "图片完成", 10: "待审", 11: "批准",
}


def completion_status(label):
    return NODE_STATUS[label]["completion"]


def has_approval(label):
    return NODE_STATUS[label]["has_approval"]


def is_approved(status):
    return status == 11


def can_submit(label, status):
    """只有有审批的节点，在完成态时才能提交审批。"""
    return has_approval(label) and status == completion_status(label)
