---
name: chapter-outliner
description: |
  推进 Chapter 图节点的提纲段：读结构段统合的 Scene + 角色性格/分支骨架 → 自检 event 丰满度 →（够）产出章节提纲 JSON（meta + scenes 骨架 + 分支拓扑，lines 留空）→ 落盘 25_剧本/*.outline.json + 写 outline_path + status=20。
  前驱：Chapter status=11（结构已批）。若 event 素材不足以支撑提纲，**拒绝产出**并报告缺口（不写 status），交 plot-design 转探索补素材。
argument-hint: <chapter_id_or_title>
arguments:
  - chapter_id_or_title
allowed-tools: Read, Bash, Write, Edit
---

> **status=-1 = 作废重做**：当 Chapter 被重置为 `status=-1` 时，即使 outline.json 已落盘，也**必须重新产出并覆盖**。`-1` 明确表示有旧产物要覆盖，**禁止因文件已存在而跳过，也禁止读旧提纲内容**，直接以当前图节点数据为唯一来源重新创作。

# 章节提纲（Chapter 提纲段 · status 11→20）

剧情创作三段式的**第二段**（结构段之后、定稿段之前）。读结构段统合好的 Scene + 出场角色性格 + 分支骨架，**先自检本章 event 丰满度**；够丰满才产出**提纲 JSON**——确定「章节分几段、每段场景/时间/bgm、choice 分叉与汇合、ending 位置」，`lines` 留空（细节对话由 `chapter-dialoguer` 填）。提纲无审批，产出即 `status=20`（提纲就绪）。

> **素材不足门控**：若本章 event 不够丰满（事件数过少 / 事件链断裂 / Choice 指向的事件缺失 / 出场角色在本章无 involved 事件），**拒绝产出提纲**——不写 status、不落盘，只产出「素材不足报告」（列缺口）返回。由 plot-design 接住后转 `nrt-narrative-grower` + `nrt-graph-builder` 探索补素材，审批写回后重调本 skill 复查。

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

#### 1c. event 丰满度自检（素材不足门控）

本章提纲的剧情密度靠 event 支撑。进入段 2 创作前，先体检本章范围内 event 的丰满度——**不足则拒绝产出提纲**，避免为空洞骨架浪费后续立绘出图。聚焦本章 Scene 所属 Location 的 Event：

```cypher
// (1) 本章涉及的 Event 数量 + 清单（Chapter→contains→Scene<-has_scene-Location<-occurred_at-Event）
MATCH (ch:Chapter {id:'<chapter_id>'})-[:contains]->(s:Scene)<-[:has_scene]-(loc:Location)
MATCH (e:Event)-[:occurred_at]->(loc)
RETURN count(DISTINCT e) AS event_count, collect(DISTINCT e.title) AS events;

// (2) Event 之间的 evt_relation 链（事件是否连贯，非孤岛）
MATCH (ch:Chapter {id:'<chapter_id>'})-[:contains]->(s:Scene)<-[:has_scene]-(loc:Location)<-[:occurred_at]-(e1:Event)
MATCH (e1)-[:evt_relation]->(e2:Event)
RETURN count(*) AS relation_count;

// (3) Choice option 指向的 target Event 是否存在（分支是否有落点）
MATCH (ch:Chapter {id:'<chapter_id>'})-[:contains]->(s:Scene)<-[:has_scene]-(loc:Location)<-[:occurred_at]-(e:Event)
MATCH (e)-[:presents]->(c:Choice)-[op:option]->(target:Event)
RETURN c.name AS choice, collect(op.label) AS options, collect(target.title) AS targets;

// (4) 出场角色在本章地点的 involved Event 数（角色弧有着落否）
MATCH (ch:Chapter {id:'<chapter_id>'})-[:contains]->(s:Scene)<-[:has_scene]-(loc:Location)<-[:occurred_at]-(e:Event)<-[:involved]-(char:Character)
RETURN char.name AS char, count(DISTINCT e) AS event_count;
```

**判断（定性，不硬编码阈值）**：综合体检结果判定 event 是否够支撑本章剧情密度。命中任一即判「素材不足」：
- **event_count 明显过少**（本章每个 Scene 平均不足 ~1 个 Event，撑不起段落）
- **事件链断裂**（Event 间几乎无 evt_relation，关键转折无承接）
- **Choice 分支无落点**（option 指向的 target Event 缺失）
- **出场角色无着落**（主要角色在本章 involved 的 Event = 0，角色弧空转）

**素材不足时**：**停止——不进入段 2，不写 status、不落盘 outline.json**。产出「素材不足报告」返回，列出具体缺口（哪个维度不足 + 涉及的 Scene/角色/Choice），供 plot-design 转探索补全。**禁止硬凑提纲**——空洞提纲会让后续 dialoguer 产出的对话无据可依。

**素材够时**：进入段 2 产出提纲。

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
