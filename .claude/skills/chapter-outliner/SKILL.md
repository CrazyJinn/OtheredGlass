---
name: chapter-outliner
description: |
  推进 Chapter 图节点的提纲段：读结构段统合的 Scene + 角色性格/分支骨架 → 产出章节提纲 JSON（meta + scenes 骨架 + 分支拓扑，lines 留空）→ 落盘 25_剧本/*.outline.json + 写 outline_path + status=20（提纲就绪）。
  前驱：Chapter status=11（结构已批）。在章节结构审批通过、需要产出提纲时使用。
argument-hint: <chapter_id_or_title>
arguments:
  - chapter_id_or_title
allowed-tools: Read, Bash, Write, Edit
---

> **status=-1 = 作废重做**：当 Chapter 被重置为 `status=-1` 时，即使 outline.json 已落盘，也**必须重新产出并覆盖**。`-1` 明确表示有旧产物要覆盖，**禁止因文件已存在而跳过，也禁止读旧提纲内容**，直接以当前图节点数据为唯一来源重新创作。

# 章节提纲（Chapter 提纲段 · status 11→20）

剧情创作三段式的**第二段**（结构段之后、定稿段之前）。读结构段统合好的 Scene + 出场角色性格 + 分支骨架，产出**提纲 JSON**——确定「章节分几段、每段场景/时间/bgm、choice 分叉与汇合、ending 位置」，但 `lines` 留空（细节对话由 `chapter-dialoguer` 填）。提纲无审批，产出即 `status=20`（提纲就绪）。

## 参数

| 参数 | 说明 |
|------|------|
| chapter_id_or_title | Chapter 节点 ID（snowflake）或 title 或 chapter_no |

## 流程（三段式：查状态 → 完成任务 → 保存结果）

> 本 skill 是 Chapter 提纲段 status 的写入点。提纲 JSON 由本 skill 直接创作产出，无纯产出子 skill。

### 1. 查询目标节点状态

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查询。

#### 1a. 解析 Chapter + 前驱校验

```cypher
MATCH (ch:Chapter) WHERE ch.id='<input>' OR ch.title='<input>' OR ch.chapter_no=<input>
RETURN ch.id AS id, ch.title AS title, ch.chapter_no AS chapter_no,
       ch.summary AS summary, ch.branch_summary AS branch_summary,
       ch.outline_path AS outline_path, ch.status AS status
LIMIT 1
```

**前驱校验**：`ch.status = 11`（结构已批），否则停止并提示先完成结构段（`chapter-structurer`）+ 结构审。

#### 1b. 查创作上下文

```cypher
// (1) 本章统合的 Scene（结构段已建 contains 边）+ 视觉上下文，按 order
MATCH (ch:Chapter {id:'<chapter_id>'})-[r:contains]->(s:Scene)
RETURN s.name AS name, s.scene_type AS scene_type, s.atmosphere AS atmosphere,
       s.time_of_day AS time_of_day, s.composition AS composition, s.lighting AS lighting,
       s.description AS description, r.order AS order
ORDER BY r.order;
```

```cypher
// (2) 出场角色 + 语言习惯（提纲要定角色语气基调）
MATCH (char:Character) WHERE char.name IN ['<角色名1>','<角色名2>']
OPTIONAL MATCH (char)-[:has_voice_style]->(voice:LanguageStyle)
RETURN char.name AS name, char.description AS description, char.character_tags AS tags,
       voice.vocabulary AS vocabulary, voice.rhythm AS rhythm,
       voice.habits AS habits, voice.emotion_patterns AS emotion_patterns,
       voice.description AS voice_desc
LIMIT 20
```

```cypher
// (3) 分支骨架：相关地点的 Choice + 结局事件（Event -occurred_at-> Location <-has_scene- Scene）
MATCH (s:Scene {name: '<scene名>'})<-[:has_scene]-(loc:Location)
MATCH (e:Event)-[:occurred_at]->(loc)
OPTIONAL MATCH (e)-[:presents]->(choice:Choice)
OPTIONAL MATCH (choice)-[op:option]->(target:Event)
RETURN e.title AS event_title, e.time AS event_time, e.ending_kind AS ending_kind,
       e.description AS event_desc, choice.name AS choice_name,
       op.label AS option_label, op.leads_to_ending AS leads_to_ending,
       target.title AS target_event, target.ending_kind AS target_ending
ORDER BY e.time LIMIT 100
```

### 2. 完成任务（产出提纲 JSON）

据 Scene 序、角色性格、分支骨架，产出**提纲 JSON**（格式见 [00_init/剧本.md](../../../00_init/剧本.md) 的「提纲格式」节——是定稿 JSON 的子集）：

1. **meta**：`chapter`(=chapter_no)、`title`、`requires{characters, scenes}`（提纲段不列 portraits，细节对话段才定）。
2. **scenes[]**：每个 scene-block 含 `id`（段标识，章节内唯一）、`scene`(=Scene.name)、`time`、`bgm`、`lines: []`（**留空**，待 dialoguer 填）。
3. **分支拓扑**：在对应 scene 标注 `choice` 的 options（label + 跳向的 scene id）、`jump` 串联、`ending` 位置与 kind（对齐 `Event.ending_kind` / `option.leads_to_ending`）。可用占位 line（如 `{"type":"choice","options":[...]}` / `{"type":"ending","kind":"BE"}`）写在 lines 里表达拓扑，但**不写 say/narrate 台词**。
4. **Write 落盘**：`25_剧本/chapter<NN>_<概述>.outline.json`（NN = `chapter_no` 零填充，概述取 title 核心主题，清洗 Windows 非法字符：去掉 `/\:*?"<>|` 等）。

> 提纲是定稿 JSON 的子集（meta + scenes 骨架，lines 仅含拓扑占位）。`chapter-dialoguer` 读此文件填 lines 成定稿。

### 3. 保存结果（写 outline_path + status=20）

```cypher
MATCH (ch:Chapter {id:'<chapter_id>'})
SET ch.outline_path = '<OUTLINE_PATH>',
    ch.status = 20;     // 提纲就绪，无审批，直接进入 chapter-dialoguer
```

**status 写入**：提纲产出 → `20`（提纲就绪）。提纲段**无审批**。

最后汇总：提纲文件 `outline_path`、Chapter `status=20`、scenes 骨架与分支拓扑概要。

## 参考文档

- 剧本格式（含提纲格式）：[00_init/剧本.md](../../../00_init/剧本.md) — JSON 结构、11 指令、outline 子集约定
- 剧情 Schema：[00_init/Schema/剧情.md](../../../00_init/Schema/剧情.md) — Chapter/Choice/contains 定义
- 上游：[chapter-structurer](../chapter-structurer/SKILL.md)（建章节结构 → status=11）
- 下游：[chapter-dialoguer](../chapter-dialoguer/SKILL.md)（读提纲填细节对话 → status=30）
