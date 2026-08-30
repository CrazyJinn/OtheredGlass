"""显式定义 status 流转规则与 enum 词表（不解析 .md）。"""

# -1 作废重做（sync 级联重置后）；0 待处理；生产态 1/2；审批专属 10 待审 / 11 批准；驳回归 0。
# 剧情：Chapter 章级结构段（0→10→11，10 由 structurer 直写无 submit 步，completion=11）；节级产物链
# SecOutline（0→1 无审批）/ SecScript（0→1→10→11 定稿审，script_path 指台词.md）/ LineAudio
# （**逐句节点**：SecScript-[:produces {order}]->LineAudio 1:N；行级 status 只代表音频审批——
# 台词文字的审批已在 SecScript 定稿审完成。say 行 0→10→11，非 say 行拆分即 11）。
# Section 为纯编排容器无 status。
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
    # 剧情（Chapter 结构审 + 节级产物链：SecOutline 无审批，SecScript/LineAudio 各一道审批）
    "Chapter":             {"legal": [-1, 0, 10, 11],         "completion": 11, "has_approval": True},
    "SecOutline":          {"legal": [-1, 0, 1],              "completion": 1,  "has_approval": False},
    "SecScript":           {"legal": [-1, 0, 1, 10, 11],      "completion": 11, "has_approval": True},
    "LineAudio":           {"legal": [-1, 0, 10, 11],         "completion": 11, "has_approval": True},
    # 声音（角色基线音色设计）：1=instruct 完成，10=候选固化即待审（skill 生产完成直写，无 submit 步；
    # 10 两态由 candidates_path 区分——非空=候选待选（审批中心「采用」固化，status 仍 10），空=单 ref 待审）；
    # 2=历史兼容值（旧流程生产态，legal 保留供存量节点经编辑器 submit 迁 10）
    "VoiceDesign":         {"legal": [-1, 0, 1, 2, 10, 11],       "completion": 10, "has_approval": True},
    # 音乐（场景背景音乐，人工生成链）：1=文字描述已产出（等用户手动生成 wav），2=音频已归档（无审批，
    # 手工放入文件夹即合格）
    "BgmTrack":            {"legal": [-1, 0, 1, 2],               "completion": 2,  "has_approval": False},
}

ENUM_OPTIONS = {
    "gender": ["男", "女"],
    "type": ["行动", "交流", "转折", "状态变化"],
    "knowledge_level": ["1", "2", "3"],
    "priority": ["P0", "P1", "P2"],
    "scene_type": ["dialogue", "functional", "combat", "ui"],
    "layer_type": ["background", "floor", "decor", "mask"],
    # LineAudio 逐句行：op 行类型（choice/jump 暂不进图，建模后续设计）；pos 立绘位；kind 结局类型
    "op": ["say", "narrate", "transition", "scene", "label", "ending"],
    "pos": ["left", "center", "right"],
    "kind": ["BE", "TE", "HE", "NE"],
    # LineAudio 逐句行：clone_mode 配音演绎通道（icl=ICL ref 韵律迁移缺省 / xvec=仅说话人向量文本主导演绎）
    "clone_mode": ["icl", "xvec"],
}

STATUS_LABEL = {
    -1: "需重做", 0: "待处理", 1: "已完成", 2: "图片完成",
    10: "待审", 11: "批准",
}


def completion_status(label):
    return NODE_STATUS.get(label, {}).get("completion")


def has_approval(label):
    return NODE_STATUS.get(label, {}).get("has_approval", False)


def is_approved(status, label=None):
    """已批准态：status==11（全图统一；含剧情产物 SecScript/LineAudio 与 VoiceDesign）。

    注意美术节点（DesignSheet/IllusDesign/StandingIllustration/SceneLayer）的 completion=2
    是历史遗留死值，实际审批走 10→11，故此处按「status==11」而非 completion_status 判定，
    避免把 11 误判为未批准。
    """
    return status == 11


def can_submit(label, current_status):
    """只有有审批的节点，在完成态时才能提交审批。无 status 字段的节点（如 Character/Section）返回 False。

    Chapter / VoiceDesign / SecScript / LineAudio：生产 skill 完成即直写 10（待审），不经 submit；
    VoiceDesign 仅存量 status=2（旧流程生产态）保留 submit 迁移通道。
    """
    if not has_approval(label):
        return False
    if current_status is None:
        return False
    if label == "VoiceDesign":
        # 生产完成已直写 10（待审）；仅存量 status=2（旧流程生产态）保留 submit 迁移通道
        return current_status == 2
    if label in ("SecScript", "LineAudio", "Chapter"):
        # 生产完成已直写 10（待审）；SecScript 的 1 是草稿态，重跑 dialoguer 提审，不走 submit
        return False
    return current_status == completion_status(label)
