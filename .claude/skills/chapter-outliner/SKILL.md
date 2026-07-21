---
name: chapter-outliner
description: |
  推进 Chapter 图节点的提纲段：读 structurer 的设计简报 + 结构段统合的 Scene + 分支骨架 → 自检 event 丰满度 →（够）按分支节点图先行/本质差异/节奏门控产出章节提纲 YAML（拓扑骨架 + authoring 人读引导块，lines 仅含拓扑占位）→ 落盘 25_剧本/*.outline.yaml + 写 outline_path + status=20。
  前驱：Chapter status=11（结构已批，且 25_剧本/chapter<NN>_设计简报.md 已产出）。若 event 素材不足以支撑提纲，**拒绝产出**并报告缺口（不写 status），由用户补全叙事基础后重调本 skill。
argument-hint: <chapter_id_or_title>
arguments:
  - chapter_id_or_title
allowed-tools: Read, Bash, Write, Edit
---

> **status=-1 = 作废重做**：当 Chapter 被重置为 `status=-1` 时，即使 outline.yaml 已落盘，也**必须重新产出并覆盖**。`-1` 明确表示有旧产物要覆盖，**禁止因文件已存在而跳过，也禁止读旧提纲内容**，直接以当前图节点数据 + 设计简报为唯一来源重新创作。

# 章节提纲（Chapter 提纲段 · status 11→20）

剧情创作三段式的**第二段**（结构段之后、定稿段之前）。读 `chapter-structurer` 产出的设计简报 + 结构段统合好的 Scene + 分支骨架，**先自检本章 event 丰满度**；够丰满才按**分支节点图先行 / 本质差异 / 节奏**三门控产出**提纲 JSON**——确定「章节分几段、每段场景/时间/bgm、choice 分叉与汇合、ending 位置」，`lines` 留空（细节对话由 `chapter-dialoguer` 填）。提纲无审批，产出即 `status=20`（提纲就绪）。

> **素材不足门控**：若本章 event 不够丰满（事件数过少 / 事件链断裂 / Choice 指向的事件缺失 / 出场角色在本章无 involved 事件），**拒绝产出提纲**——不写 status、不落盘，只产出「素材不足报告」（列缺口）返回。用户可手动跑 `nrt-narrative-grower`（独立自增长流程）补全叙事基础后，重调本 skill 复查。

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

#### 1b. 读设计简报 + 查创作上下文

**先读设计简报**：Read `25_剧本/chapter<NN>_设计简报.md`（NN = chapter_no 零填充），取出设计支柱 / 情感弧线 / 戏剧意图 / 核心循环——本章提纲的情感基调与结构依据全靠它。简报缺失则停止并提示先跑 `chapter-structurer`。

再查图：

```cypher
// (1) 本章统合的 Scene（结构段已建 contains 边）+ 视觉上下文，按 order
MATCH (ch:Chapter {id:'<chapter_id>'})-[r:contains]->(s:Scene)
RETURN s.name AS name, s.scene_type AS scene_type, s.atmosphere AS atmosphere,
       s.time_of_day AS time_of_day, s.composition AS composition, s.lighting AS lighting,
       s.description AS description, r.order AS order
ORDER BY r.order;
```

```cypher
// (2) 分支骨架：相关地点的 Choice + 结局事件（Event -occurred_at-> Location <-has_scene- Scene）
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

> 角色声音（LanguageStyle）在提纲段**不查**——outline JSON 无字段承载语气，查了不用；声音留给 `chapter-dialoguer` 段查用。

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

**素材不足时**：**停止——不进入段 2，不写 status、不落盘 outline.yaml**。产出「素材不足报告」返回，列出具体缺口（哪个维度不足 + 涉及的 Scene/角色/Choice），供用户参考补全（可手动跑 `nrt-narrative-grower`）。**禁止硬凑提纲**——空洞提纲会让后续 dialoguer 产出的对话无据可依。

**素材够时**：进入段 2 产出提纲。

### 2. 完成任务（按三门控产出提纲 JSON）

据设计简报（情感弧/戏剧意图）+ Scene 序 + 分支骨架，**先结构后内容**，三步产出提纲（格式见 [00_init/剧本.md](../../../00_init/剧本.md) 的「提纲格式」节——定稿 YAML 的子集 + authoring 块）：

#### 2a. 分支节点图先行（结构验证）

**写一句台词前先画分支拓扑**：用纸面节点图厘清本章分支结构——哪个 scene 分叉、分支在哪汇合、ending 落在哪。自检：
- **无死胡同**：每条分支最终汇合回主线或导向 ending，不存在走不通的路径。
- **自然汇合**：分支不是多条永不相交的平行线（除非有显式 BE/TE 分流设计理由）。
- **落点存在**：choice 的每个 option 跳向的 scene id 都在本章 scenes 内。

> 详见 [references/分支结构方法论.md](references/分支结构方法论.md)「分支节点图先行」。节点图在脑内/草稿推演即可，不必落盘——避免把对话写进结构性死胡同。

#### 2b. 分支本质差异门控

对每个 `choice` 的 options 做**有意义选择测试**：选项之间必须是**戏剧本质不同**（不同价值观取向 / 不同后果路径 / 不同信息揭示），不是 flavor 级文案差异（"我来帮" vs "我晚点帮"不算）。

- 命中 flavor 级差异（表面文案不同、剧情本质相同）→ **标注问题**，在产出报告里建议用户手动补 Choice 的戏剧分化；本次先按现状产出但标记待补。

> 详见 [references/分支结构方法论.md](references/分支结构方法论.md)「分支本质差异门控」。

#### 2c. 节奏/戏剧结构 + 落盘

据设计简报的**情感弧线**安排 scene 序的节奏：明确本章的 turning point（转折点）/ climax（高潮）位置，让情绪有起伏而非平铺。然后产出 outline **YAML**——**拓扑骨架（schema 子集字段）+ `authoring` 人读引导块**。

#### 拓扑骨架（与定稿同结构，dialoguer 必须原样搬到定稿）

1. **meta**：`chapter`(=chapter_no)、`title`、`requires{characters, scenes}`（提纲段不列 portraits，细节对话段才定）。
2. **scenes[]**：每个 scene-block 含 `id`（段标识，章节内唯一）、`scene`(=Scene.name)、`time`、`bgm`、`lines`（**仅含分支拓扑占位**：`choice` / `jump` / `ending` 等；**不写 say/narrate 台词**）。
3. **分支拓扑**：在对应 scene 标注 `choice` 的 options（label + 跳向的 scene id）、`jump` 串联、`ending` 位置与 kind（对齐 `Event.ending_kind` / `option.leads_to_ending`）。

#### authoring 人读引导块（不进定稿，仅供 dialoguer 参考；不进 schema 校验）

回应用户"提纲要能看出剧情发展方向"的诉求，产出人读引导字段：

- **顶层 `authoring`**：`direction`（一段话讲清本章剧情发展方向，**核心字段**）/ `emotion_arc`（情感弧线 start→end + 中途转折）/ `constraints`（给 dialoguer 的硬约束清单）。
- **每 scene 的 `authoring`**：`purpose`（这场戏的戏剧职责）/ `beats`（节拍走向，自然语言列表，**禁写台词**——解决事件粒度粗，给 dialoguer 节拍依据）/ `motif_anchors`（母题/象征物锚点）/ `transition`（场景衔接方式说明）。

字段定义详见 [00_init/剧本.md](../../../00_init/剧本.md)「提纲格式（outline.yaml）」节。

#### YAML 写作安全规则（强制，所有 string 双引号）

- 所有 string 值**强制双引号**（防 YAML 1.1 把裸 `yes/no/on/off` 解析成 bool + 半角冒号断裂）。
- 多行文本用双引号 + `\n`，**禁用块标量** `|` / `>`。
- bool 用小写 `true/false`；字段顺序对齐 schema properties。

#### 落盘

**Write**：`25_剧本/chapter<NN>_<概述>.outline.yaml`（NN = `chapter_no` 零填充，概述取 title 核心主题，清洗 Windows 非法字符：去掉 `/\:*?"<>|` 等）。

> 提纲 = 拓扑骨架（定稿子集）+ authoring 引导块。`chapter-dialoguer` 读此文件，以 `authoring.beats` 为节拍依据，在保持拓扑不变的前提下填 lines 成定稿 `.yaml`；**authoring 块不搬进定稿**。

### 3. 保存结果（写 outline_path + status=20）

```cypher
MATCH (ch:Chapter {id:'<chapter_id>'})
SET ch.outline_path = '<OUTLINE_PATH>',
    ch.status = 20;     // 提纲就绪，无审批，直接进入 chapter-dialoguer
```

**status 写入**：提纲产出 → `20`（提纲就绪）。提纲段**无审批**。

最后汇总：提纲文件 `outline_path`、Chapter `status=20`、分支拓扑概要（分叉/汇合/ending 位置）+ 任何 flavor 级分支的待补标注。

## 参考文档

- 创作方法论：[references/分支结构方法论.md](references/分支结构方法论.md) — 节点图先行/本质差异/后果可见/节奏
- 剧本格式（含提纲格式）：[00_init/剧本.md](../../../00_init/剧本.md) — JSON 结构、11 指令、outline 子集约定
- 剧情 Schema：[00_init/Schema/剧情.md](../../../00_init/Schema/剧情.md) — Chapter/Choice/contains 定义
- 上游：[chapter-structurer](../chapter-structurer/SKILL.md)（建结构 + 产设计简报 → status=11）
- 下游：[chapter-dialoguer](../chapter-dialoguer/SKILL.md)（读提纲填细节对话 → status=30）
