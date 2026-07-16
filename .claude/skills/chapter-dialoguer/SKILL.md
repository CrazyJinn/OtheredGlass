---
name: chapter-dialoguer
description: |
  推进 Chapter 图节点的定稿段：读提纲 JSON → 创作逐句对话填入骨架 → 跑 validate 校验 → 写定稿 script_path + status=30（定稿待审）+ 兜底建 depicts 立绘缺口节点（status=0，交 plot-design 推进）。
  前驱：Chapter status=20（提纲就绪）。在提纲就绪、需要创作细节对话定稿时使用。
argument-hint: <chapter_id_or_title> [target_status]
arguments:
  - chapter_id_or_title
  - target_status
allowed-tools: Read, Bash, Write, Edit
---

> **status=-1 = 作废重做**：当 Chapter 被重置为 `status=-1` 时，即使定稿 JSON 已落盘，也**必须重新创作并覆盖**（重走 20→30）。`-1` 明确表示有旧产物要覆盖，**禁止因文件已存在而跳过，也禁止读旧剧本内容**，直接以当前图节点数据 + outline.json 为唯一来源重新创作。重做时 depicts 边 MERGE 幂等，不主动删。

# 章节细节对话（Chapter 定稿段 · status 20→30）

剧情创作三段式的**第三段**。读 `chapter-outliner` 产出的提纲 JSON，创作逐句对话填入骨架，产出完整剧本 JSON（格式见 [00_init/剧本.md](../../../00_init/剧本.md)），落盘 `25_剧本/`（**创作/审阅区，非运行时**；定稿审通过后由 `chapter-publisher` 发布到 `99_game/`）。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| chapter_id_or_title | Chapter 节点 ID（snowflake）或 title 或 chapter_no | 必传 |
| target_status | `30`（定稿+校验→提交定稿审）或 `20`（仅草稿，回退提纲就绪） | `30` |

## 流程（三段式：查状态 → 完成任务 → 保存结果）

> 本 skill 是 Chapter 定稿段 status 的唯一写入点；剧本 JSON 由本 skill 直接创作产出。编剧是高自由度创作任务，**无纯产出子 skill**——创作与写图都在本 skill 内完成。

### 1. 查询目标节点状态

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查询。

#### 1a. 解析 Chapter + 前驱校验

```cypher
MATCH (ch:Chapter) WHERE ch.id='<input>' OR ch.title='<input>' OR ch.chapter_no=<input>
RETURN ch.id AS id, ch.outline_path AS outline_path, ch.script_path AS script_path, ch.status AS status
LIMIT 1
```

**前驱校验**：`ch.status = 20`（提纲就绪，`outline_path` 非空），否则停止并提示先完成提纲段（`chapter-outliner`）。

#### 1b. 查创作上下文

读 `outline.json`（meta + scenes 骨架 + 分支拓扑）。再查：

```cypher
// (1) 出场角色 + 语言习惯（创作对话的核心依据）
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
// (2) 各角色现有立绘变体（供 portrait 选用；status=11 可直接用，<11 标注为缺口）
MATCH (char:Character) WHERE char.name IN ['<角色名>']
MATCH (char)-[:has_appearance]->(:AppearanceStyle)-[:produces]->(:DesignSheet)-[:produces]->(illus:IllusDesign)
MATCH (illus)-[:expands_to]->(stand:StandingIllustration)
RETURN char.name AS char_name, stand.id AS stand_id, stand.variant_label AS variant,
       stand.status AS status, illus.id AS illus_id
ORDER BY char_name, variant LIMIT 200
```

### 2. 完成任务（创作细节对话，填入提纲骨架）

读 `outline.json` 每个 scene 骨架，据角色性格/语言习惯（`vocabulary`/`rhythm`/`habits`/`emotion_patterns`）、场景氛围、分支拓扑，创作逐句 `lines` 填入（覆盖空的 lines 数组，保留提纲里的 choice/jump/ending 拓扑）：

1. **lines**：用 11 条指令（`say`/`narrate`/`show`/`hide`/`bg`/`bgm`/`sfx`/`choice`/`label`/`jump`/`ending`）。每条 `say` 必带 `who`/`portrait`/`pos`/`text` 全四字段，`pos` ∈ `left`/`center`/`right`。台词风格严格遵循角色 LanguageStyle。
2. **变体选用规则**：
   - 优先用 `status=11` 的已有变体。
   - 剧情需要某个不存在/未批准的变体（如「陈默.沉重」），仍写入 `portrait` 字段，并记录为「缺口」——段 3c 兜底建 `StandingIllustration(status=0)` + `depicts` 边，交 `plot-design` 推进。
3. **分支与结局**：`choice.options[]` 每项含 `label` + `to`/`scene`/`file` 至少其一；结局用 `ending{kind:BE/TE/HE/NE}`，对齐 `Event.ending_kind` 与 `option.leads_to_ending`。
4. **Write 落盘**：`25_剧本/chapter<NN>_<概述>.json`（定稿，命名同提纲文件名主体）。**这是创作/审阅区，非运行时**——`Chapter.script_path` 指向此路径。

> 格式细节、11 指令字段、跳转寻址——严格按 [00_init/剧本.md](../../../00_init/剧本.md) 与 [99_game/data/剧本.schema.json](../../../99_game/data/剧本.schema.json)。生成后必须通过 schema 校验（段 3a）才交付。

### 3. 保存结果（校验 + 写图 + 立绘缺口兜底）

#### 3a. 跑 validate 校验

```bash
python 99_game/tools/validate_chapter.py '<script_path>' 99_game/data/剧本.schema.json
```

- 打印 `OK` → 通过，继续 3b 写 `status=30`（`target_status=30` 时）。
- 打印 `FAIL` → 报告错误列表，**写 `status=20`**（回提纲就绪，提示修复后重跑）。

#### 3b. 写图（script_path + status）

```cypher
MATCH (ch:Chapter {id:'<chapter_id>'})
SET ch.script_path = '<script_path>',
    ch.status = <20 | 30>;     // target_status=30 且校验通过 → 30（定稿待审）；失败/草稿 → 20
```

#### 3c. 立绘缺口兜底（对每个「缺口」变体 `<char_name>.<variant_label>`）

**① 选 IllusDesign**（多着装歧义处理：优先场景事件 wears 指定的着装，兜底取默认着装）：

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

- 查不到任何 IllusDesign → 角色美术链未就绪，报告「需先推进 char-design 到 IllusDesign」，该变体 portrait 仍写入 JSON（运行时占位图兜底），但跳过建节点。

**② 兜底建 StandingIllustration(status=0) + expands_to + ref_style + depicts**（生成新 stand_id：`snowflake_base62.py -n 1 -q`）：

```cypher
MERGE (stand:StandingIllustration {id:'<stand_id>'})
  ON CREATE SET stand.status = 0, stand.variant_label = '<variant_label>';
MATCH (illus:IllusDesign {id:'<illus_id>'}), (stand:StandingIllustration {id:'<stand_id>'})
MERGE (illus)-[r:expands_to]->(stand) SET r.sync = true, r.variant_label = '<variant_label>';
MATCH (voice:LanguageStyle {id:'<voice_id>'}), (stand:StandingIllustration {id:'<stand_id>'})
MERGE (voice)-[r:ref_style]->(stand) SET r.sync = true;
MATCH (s:Scene {name:'<scene_name>'}), (stand:StandingIllustration {id:'<stand_id>'})
MERGE (s)-[r:depicts]->(stand) SET r.sync = false;
```

> `expands_to`/`ref_style` 边 `sync=true`（上游 IllusDesign/LanguageStyle 更新会级联重置该立绘）；`depicts` 边 `sync=false`（编排引用，不级联）。这些 `status=0` 的立绘缺口节点是 **plot-design 后续按 depicts 直调 `char-stand-designer <stand_id>` 推进**的输入。`illus.status<11` 不阻断建节点——plot-design 推进立绘前会先确保上游 IllusDesign=11（必要时委派 char-design）。

**status 写入**：定稿+校验通过 → `30`（定稿待审，等 dashboard 终审 `approve`→`31`）；失败/草稿 → `20`。

最后汇总：定稿 `script_path`、Chapter `status=30`、标记的立绘缺口（stand_id + status=0，待 plot-design 推进）。

## 参考文档

- 剧本格式：[00_init/剧本.md](../../../00_init/剧本.md) — JSON 结构、11 指令、跳转寻址
- 剧本 schema：[99_game/data/剧本.schema.json](../../../99_game/data/剧本.schema.json) — 校验门
- 剧情 Schema：[00_init/Schema/剧情.md](../../../00_init/Schema/剧情.md) — Chapter/depicts 边
- 角色美术 Schema：[00_init/Schema/角色美术.md](../../../00_init/Schema/角色美术.md) — StandingIllustration 字段
- 上游：[chapter-outliner](../chapter-outliner/SKILL.md)（产提纲 → status=20）
- 下游：plot-design agent（定稿审 status=31 后，按 depicts 推进立绘 + chapter-publisher 发布）
