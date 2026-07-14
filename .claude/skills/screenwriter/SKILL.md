---
name: screenwriter
description: |
  推进 Chapter 图节点：查询编排上下文 → 创作剧本对话、组装 JSON → 保存结果
  （MERGE 兜底建 Chapter 节点 + contains/depicts 边，写 script_path/status + 跑 validate 校验）。
  在需要创作或重做章节剧本时使用。
argument-hint: <chapter_id_or_title> [target_status]
arguments:
  - chapter_id_or_title
  - target_status
allowed-tools: Read, Bash, Write, Edit
---

> **status=-1 = 作废重做**：当 Chapter 被 sync 级联或手动重置为 `status=-1` 时，即使 `script_path` 已有值、剧本 JSON 已落盘，也**必须重新生成并覆盖**（重走 0→1→2→10）。`-1` 明确表示有旧产物要覆盖，**禁止因文件已存在而跳过，也禁止读旧剧本内容**，直接以当前图节点数据为唯一来源重新创作。重做时先删除旧 `contains` 边再重建（`depicts` 边 MERGE 幂等，不主动删）。

# 章节剧本（Chapter）

据章节叙事范围（`Chapter.summary`）+ 角色性格/语言习惯（LanguageStyle）+ 场景视觉上下文（Scene）+ 分支骨架（Choice/Event），创作逐句对话，组装为剧本 JSON（格式见 [00_init/剧本.md](../../../00_init/剧本.md)），落盘 `25_剧本/`（**创作/审阅区，非运行时**；审阅通过后由 `chapter-publisher` skill 发布到 `99_game/`）。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| chapter_id_or_title | Chapter 节点 ID（snowflake）或 title 或 chapter_no | 必传 |
| target_status | 推进目标：`1`（仅草稿）或 `2`（草稿+校验→提交待审） | `2` |

## 流程（三段式：查状态 → 完成任务 → 保存结果）

> 本 skill 是 Chapter `status` 的唯一写入点；剧本 JSON 由本 skill 直接创作产出。编剧是高自由度创作任务，**无纯产出子 skill**（区别于美术链的 prompt-assembler）——创作与写图都在本 skill 内完成，由「保存结果」步统一写入。

### 1. 查询目标节点状态

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查询。

#### 1a. 解析或创建 Chapter

```cypher
MATCH (ch:Chapter) WHERE ch.id='<input>' OR ch.title='<input>' OR ch.chapter_no=<input>
RETURN ch.id AS id, ch.title AS title, ch.chapter_no AS chapter_no,
       ch.summary AS summary, ch.branch_summary AS branch_summary,
       ch.script_path AS script_path, ch.status AS status
LIMIT 1
```

- **已存在**：用返回的 `id` + `summary` 作为创作纲要。`status=-1` 进入重做（段 3 先清旧 contains 边）。
- **不存在**（首次创建）：需从调用方（plot-design agent / 用户）获取 `title` / `chapter_no` / `summary`；缺失则停止并提示。生成新 id：
  ```bash
  python "${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py" -n 1 -q
  ```

#### 1b. 查询创作上下文

从 `summary` 提及的地点名、角色名，分 4 类查询（每条加 `LIMIT`）：

```cypher
// (2) 相关 Scene 视觉上下文（按 summary 提及的地点名定位）
MATCH (s:Scene)
WHERE s.name STARTS WITH '<地点名>'
RETURN s.name AS name, s.scene_type AS scene_type, s.atmosphere AS atmosphere,
       s.time_of_day AS time_of_day, s.composition AS composition, s.lighting AS lighting,
       s.description AS description, s.status AS status
ORDER BY s.name LIMIT 50
```

> **前驱校验**：所用 Scene 的 `status` 应为 `1`（已完成）。`status=0/-1` 表示场景未就绪，停止并提示先推进 `scene-designer`。

```cypher
// (3) 出场角色 + 语言习惯（创作对话的核心依据）
MATCH (char:Character) WHERE char.name IN ['<角色名1>','<角色名2>']
OPTIONAL MATCH (char)-[:has_voice_style]->(voice:LanguageStyle)
RETURN char.name AS name, char.description AS description, char.character_tags AS tags,
       voice.id AS voice_id,
       voice.vocabulary AS vocabulary, voice.rhythm AS rhythm,
       voice.habits AS habits, voice.emotion_patterns AS emotion_patterns,
       voice.description AS voice_desc
LIMIT 20
```

```cypher
// (4) 分支骨架：相关地点的 Choice + 结局事件（Event -occurred_at-> Location <-has_scene- Scene）
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

```cypher
// (5) 各角色现有立绘变体（供 portrait 选用；status=11 可直接用，<11 标注为缺口）
MATCH (char:Character) WHERE char.name IN ['<角色名>']
MATCH (char)-[:has_appearance]->(:AppearanceStyle)-[:produces]->(:DesignSheet)-[:produces]->(illus:IllusDesign)
MATCH (illus)-[:expands_to]->(stand:StandingIllustration)
RETURN char.name AS char_name, stand.id AS stand_id, stand.variant_label AS variant,
       stand.status AS status, illus.id AS illus_id
ORDER BY char_name, variant LIMIT 200
```

### 2. 完成任务（创作剧本 JSON）

据角色性格/语言习惯（`vocabulary`/`rhythm`/`habits`/`emotion_patterns`）、场景氛围、分支骨架，创作逐句对话，组装剧本 JSON：

1. **meta**：`chapter`（= `chapter_no`）、`title`、`requires{characters, scenes, portraits}`。`portraits` = 全章 `say`/`show` 用到的 `<角色>.<变体>` 逻辑名集合。
2. **scenes[]**：每个 scene-block 含 `id`（段标识，章节内唯一）、`scene`（= `Scene.name`）、`time`、`bgm`、`lines[]`。
3. **lines**：用 11 条指令（`say`/`narrate`/`show`/`hide`/`bg`/`bgm`/`sfx`/`choice`/`label`/`jump`/`ending`）。每条 `say` 必带 `who`/`portrait`/`pos`/`text` 全四字段，`pos` ∈ `left`/`center`/`right`。台词风格严格遵循角色 LanguageStyle。
4. **变体选用规则**：
   - 优先用 `status=11` 的已有变体。
   - 剧情需要某个不存在/未批准的变体（如「陈默.沉重」），仍写入 `portrait` 字段，并记录为「缺口」——段 3 兜底建 `StandingIllustration(status=0)` + `depicts` 边，交 `char-design` 推进。
5. **分支与结局**：`choice.options[]` 每项含 `label` + `to`/`scene`/`file` 至少其一；结局用 `ending{kind:BE/TE/HE/NE}`，对齐 `Event.ending_kind` 与 `option.leads_to_ending`。
6. **Write 落盘**：`25_剧本/chapter<NN>_<概述>.json`（NN = `chapter_no` 零填充，概述取 title 核心主题，清洗 Windows 非法字符）。**这是创作/审阅区，非运行时**——`Chapter.script_path` 指向此 `25_剧本/` 路径；审阅通过（status=11）+ 立绘就绪后，由 `chapter-publisher` skill 发布到 `99_game/data/chapters/`。

> 格式细节、11 指令字段、跳转寻址、manifest 映射——严格按 [00_init/剧本.md](../../../00_init/剧本.md) 与 [99_game/data/剧本.schema.json](../../../99_game/data/剧本.schema.json)。生成后必须通过 schema 校验（段 3a）才交付。

### 3. 保存结果（MERGE 兜底 + 校验 + 写 status）

#### 3a. 跑 validate 校验

```bash
python 99_game/tools/validate_chapter.py '<script_path>' 99_game/data/剧本.schema.json
```

- 打印 `OK` → 通过，继续 3b 写 `status=10`（`target_status=2` 时）。
- 打印 `FAIL` → 报告错误列表，**写 `status=1`**（草稿存在但未通过校验），返回提示修复后重跑。

#### 3b. 写图（`--multi` 单事务，节点先于边；`status=-1` 重做时先清旧 contains 边）

```cypher
// 0.（仅 status=-1 重做时）清旧 contains 边——本章权威，order 可能变
MATCH (ch:Chapter {id: '<chapter_id>'})-[r:contains]->() DELETE r;

// 1. MERGE Chapter + 写编排属性 + status
MERGE (ch:Chapter {id: '<chapter_id>'})
  ON CREATE SET ch.status = 0;
MATCH (ch:Chapter {id: '<chapter_id>'})
SET ch.title = '<title>',
    ch.chapter_no = <chapter_no>,
    ch.script_path = '<script_path>',
    ch.summary = '<summary>',
    ch.branch_summary = '<branch_summary>',
    ch.status = <1 | 10>;     // target_status=1 或 validate 失败 → 1；target_status=2 且校验通过 → 10（待审）

// 2. MERGE contains 边（对 JSON 中每个用到的 Scene.name，按 scene-block 首次出现 order）
MATCH (ch:Chapter {id: '<chapter_id>'}), (s:Scene {name: '<scene_name>'})
MERGE (ch)-[r:contains]->(s) SET r.order = <order>, r.sync = false;
```

#### 3c. 立绘缺口兜底（对每个「缺口」变体）

对段 2 记录的每个不存在/未批准变体 `<char_name>.<variant_label>`：

**① 选 IllusDesign**（多着装歧义处理：V1 立绘逻辑名不含着装维度，映射到默认着装）：

```cypher
// 优先：该场景事件 wears 指定的着装
MATCH (s:Scene {name:'<scene_name>'})<-[:has_scene]-(loc:Location)
MATCH (e:Event)-[:occurred_at]->(loc)
MATCH (e)-[:wears]->(cos:CostumeStyle)<-[:has_costume]-(char:Character {name:'<char_name>'})
MATCH (cos)-[:outfit_for]->(illus:IllusDesign)
RETURN illus.id AS illus_id, illus.status AS illus_status LIMIT 1;
// 兜底：无 wears 时，取角色第一套（默认）着装的 IllusDesign
MATCH (char:Character {name:'<char_name>'})-[:has_costume]->(cos:CostumeStyle)
MATCH (cos)-[:outfit_for]->(illus:IllusDesign)
RETURN illus.id AS illus_id, illus.status AS illus_status ORDER BY cos.id LIMIT 1;
```

- 查不到任何 IllusDesign → 角色美术链未就绪，报告「需先推进 char-design 全链」，该变体 `portrait` 仍写入 JSON（运行时占位图兜底），但跳过建节点。

**② 兜底建 StandingIllustration(status=0) + expands_to + ref_style + depicts**（生成新 stand_id：`snowflake_base62.py -n 1 -q`）：

```cypher
MERGE (stand:StandingIllustration {id: '<stand_id>'})
  ON CREATE SET stand.status = 0, stand.variant_label = '<variant_label>';
MATCH (illus:IllusDesign {id: '<illus_id>'}), (stand:StandingIllustration {id: '<stand_id>'})
MERGE (illus)-[r:expands_to]->(stand) SET r.sync = true, r.variant_label = '<variant_label>';
MATCH (voice:LanguageStyle {id: '<voice_id>'}), (stand:StandingIllustration {id: '<stand_id>'})
MERGE (voice)-[r:ref_style]->(stand) SET r.sync = true;
MATCH (s:Scene {name: '<scene_name>'}), (stand:StandingIllustration {id: '<stand_id>'})
MERGE (s)-[r:depicts]->(stand) SET r.sync = false;
```

> `expands_to`/`ref_style` 边的 `sync=true` 沿用美术链语义（上游 IllusDesign/LanguageStyle 更新会级联重置该立绘）；`depicts` 边 `sync=false`（编排引用，不级联）。`illus.status<11` 不阻断建节点——`char-stand-designer` 前驱校验会等 IllusDesign 批准后推进，或由 `char-design` agent 全链推进上游。

**status 写入**：仅草稿（`target_status=1` 或 validate 失败）→ `1`；草稿+校验通过（`target_status=2`）→ `10`（待审）。Chapter 由 dashboard 审批 `10→11`。

最后汇总：新建/覆盖的 JSON `script_path`、建立的 `contains` 边（scene 顺序）、标记的立绘缺口（stand_id + status=0，待 char-design 推进）。

## 参考文档

- 剧本格式：[00_init/剧本.md](../../../00_init/剧本.md) — JSON 结构、11 指令、跳转寻址、manifest 映射
- 剧本 schema：[99_game/data/剧本.schema.json](../../../99_game/data/剧本.schema.json) — 校验门
- 剧情 Schema：[00_init/Schema/剧情.md](../../../00_init/Schema/剧情.md) — Chapter/Choice 节点、contains/depicts 边
- 叙事基础 Schema：[00_init/Schema/叙事基础.md](../../../00_init/Schema/叙事基础.md) — Character/Event/Location 字段
- 场景美术 Schema：[00_init/Schema/场景美术.md](../../../00_init/Schema/场景美术.md) — Scene 字段
- 角色美术 Schema：[00_init/Schema/角色美术.md](../../../00_init/Schema/角色美术.md) — LanguageStyle/StandingIllustration 字段
