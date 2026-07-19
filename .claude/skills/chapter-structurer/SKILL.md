---
name: chapter-structurer
description: |
  推进 Chapter 图节点的结构段：解析/创建 Chapter → 校验 Scene 前驱 → 把 N 个 Scene 统合进章节（contains 边）→ 产出章节设计简报（设计支柱/情感弧/戏剧意图，锚定全链路创作意图）→ 写 status=1（结构就绪，待结构审）。
  在需要建立章节结构或重做章节结构时使用。设计简报供下游 chapter-outliner / chapter-dialoguer 对齐。
argument-hint: <chapter_id_or_title>
arguments:
  - chapter_id_or_title
allowed-tools: Read, Bash, Write
---

> **status=-1 = 作废重做**：当 Chapter 被 sync 级联或手动重置为 `status=-1` 时，即使 contains 边 + 设计简报已存在，也**必须重新统合 Scene、重新产出设计简报并覆盖**（重走 0→1）。重做时先删除旧 contains 边再重建（contains 是本章权威，order 可能变）；设计简报直接覆盖。禁止因产物已存在而跳过。

# 章节结构（Chapter 结构段 · status 0→1）

剧情创作三段式（`chapter-structurer` → 结构审 → `chapter-outliner` → `chapter-dialoguer` → 定稿审）的**第一段**。建立章节骨架并锚定创作意图：创建/补全 Chapter 节点的编排属性 + 用 `contains` 边统合本章 N 个 Scene + **产出章节设计简报**（全链路创作意图的唯一锚点），推进到 `status=1`（结构就绪）。**不创作对话**。

## 参数

| 参数 | 说明 |
|------|------|
| chapter_id_or_title | Chapter 节点 ID（snowflake）或 title 或 chapter_no。首次创建时调用方需在 prompt 中提供 `title`/`chapter_no`/`summary`/`branch_summary`，缺失则停止。 |

## 流程（三段式：查状态 → 完成任务 → 保存结果）

> 本 skill 是 Chapter 结构段 status 的写入点 + 设计简报的产出点。不调子 skill。

### 1. 查询目标节点状态

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查询。

#### 1a. 解析或创建 Chapter

```cypher
MATCH (ch:Chapter) WHERE ch.id='<input>' OR ch.title='<input>' OR ch.chapter_no=<input>
RETURN ch.id AS id, ch.title AS title, ch.chapter_no AS chapter_no,
       ch.summary AS summary, ch.branch_summary AS branch_summary,
       ch.status AS status
LIMIT 1
```

- **已存在**：用其 `id` + `summary` 作为统合依据。`status=-1` 进入重做（段 3 先清旧 contains 边）。
- **不存在**（首次创建）：需从调用方（plot-design agent / 用户）获取 `title`/`chapter_no`/`summary`/`branch_summary`；缺失则停止并提示。生成新 id：
  ```bash
  python "${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py" -n 1 -q
  ```

#### 1b. 查候选 Scene + 前驱校验

从 `summary` 提及的地点名查 Scene：

```cypher
MATCH (s:Scene)
WHERE s.name STARTS WITH '<地点名>'
RETURN s.name AS name, s.scene_type AS scene_type, s.atmosphere AS atmosphere,
       s.time_of_day AS time_of_day, s.composition AS composition, s.lighting AS lighting,
       s.description AS description, s.status AS status
ORDER BY s.name LIMIT 50
```

> **前驱校验**：所选 Scene 的 `status` 必须为 `1`（已完成）。`status=0/-1` 表示场景未就绪，停止并提示先推进 `scene-designer`。

### 2. 完成任务（编排章节结构 + 产出设计简报）

#### 2a. 选 Scene + 排序

据 `summary` 的叙事范围，从候选 Scene 选定本章统合的 N 个 Scene，排定 `order`（按本章剧情首次出现顺序，从 0 起）。确定「本章分几段、每段在哪个 Scene、先后顺序」。

> 结构段只定 Scene 序，不定分支拓扑（分支/结局拓扑由 `chapter-outliner` 在提纲里定）。

#### 2b. 产出章节设计简报（全链路创作意图锚点）

下游 outliner/dialoguer 都读它对齐——**这是"本章要表达什么"的唯一显式记录**。基于 `summary` + 所选 Scene 推导，Write 产出 `25_剧本/chapter<NN>_设计简报.md`（NN = `chapter_no` 零填充，命名同 outline.yaml 规则），含四节：

- **设计支柱**（3–5 个不可妥协的玩家体验/情感目标）——本章必须传递什么。
- **情感弧线**（本章情绪起点→终点的轨迹）。
- **戏剧意图**（本章在整部作品里的任务：建立什么 / 转折什么 / 收束什么）。
- **本章核心循环**（galgame 适配：即时体验段 / 本章节目标 / 长期留存钩子）。

> 每节怎么写详见 [references/设计简报方法论.md](references/设计简报方法论.md)——产出前读它。简报是创作锚点不是剧本，保持精炼（半页内）。

### 3. 保存结果（MERGE 兜底 + 写 status）

`--multi` 单事务，节点先于边；`status=-1` 重做时先清旧 contains 边：

```cypher
// 0.（仅 status=-1 重做时）清旧 contains 边——本章权威，order 可能变
MATCH (ch:Chapter {id:'<chapter_id>'})-[r:contains]->() DELETE r;

// 1. MERGE Chapter + 写编排属性 + status=1（结构就绪）
MERGE (ch:Chapter {id:'<chapter_id>'})
  ON CREATE SET ch.status = 0;
MATCH (ch:Chapter {id:'<chapter_id>'})
SET ch.title = '<title>',
    ch.chapter_no = <chapter_no>,
    ch.summary = '<summary>',
    ch.branch_summary = '<branch_summary>',
    ch.status = 1;     // 结构就绪，待 dashboard submit→10 结构审

// 2. MERGE contains 边（对选定的每个 Scene.name，按排定的 order）
MATCH (ch:Chapter {id:'<chapter_id>'}), (s:Scene {name:'<scene_name>'})
MERGE (ch)-[r:contains]->(s) SET r.order = <order>, r.sync = false;
```

**status 写入**：结构段完成 → `1`（结构就绪）。后续由 dashboard `submit` 1→10（结构待审）→ `approve` 10→11（结构已批），才进入 `chapter-outliner`。

最后汇总：设计简报路径 `25_剧本/chapter<NN>_设计简报.md`、统合的 Scene 列表（含 order）、Chapter `status=1`。

## 参考文档

- 创作方法论：[references/设计简报方法论.md](references/设计简报方法论.md) — 设计支柱/情感弧线/戏剧意图/核心循环各节写法
- 剧情 Schema：[00_init/Schema/剧情.md](../../../00_init/Schema/剧情.md) — Chapter/contains 定义、status 三段流转
- 场景美术 Schema：[00_init/Schema/场景美术.md](../../../00_init/Schema/场景美术.md) — Scene 字段
- 下游：[chapter-outliner](../chapter-outliner/SKILL.md)（读设计简报 + 结构批 status=11 后产出提纲）
