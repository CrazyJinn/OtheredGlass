---
name: chapter-dialoguer
description: |
  推进 Chapter 图节点的定稿段：读 structurer 的设计简报 + outliner 的提纲 → 三轮打磨（功能→声音→精简）创作逐句对话填入骨架 → 跑 validate 校验 → 写定稿 script_path + status=30（定稿待审）。
  前驱 status=20（提纲就绪）。创作中若发现 outline 戏剧性破碎（分支无本质差异/scene 无情绪推进），产出「结构性问题报告」回退 outliner，不写 status。立绘缺口兜底建 depicts 节点为副作用（交 plot-design 推进）。
argument-hint: <chapter_id_or_title> [target_status]
arguments:
  - chapter_id_or_title
  - target_status
allowed-tools: Read, Bash, Write, Edit
---

> **status=-1 = 作废重做**：当 Chapter 被重置为 `status=-1` 时，即使定稿 `.yaml` 已落盘，也**必须重新创作并覆盖**（重走 20→30）。`-1` 明确表示有旧产物要覆盖，**禁止因文件已存在而跳过，也禁止读旧剧本内容**，直接以当前图节点数据 + outline.yaml + 设计简报为唯一来源重新创作。重做时 depicts 边 MERGE 幂等，不主动删。

# 章节细节对话（Chapter 定稿段 · status 20→30）

剧情创作三段式的**第三段**。读 `chapter-structurer` 的设计简报（情感弧/戏剧意图）+ `chapter-outliner` 的提纲 YAML，用**三轮打磨**（功能→声音→精简）创作逐句对话填入骨架，产出完整剧本 **YAML**（schema 子集 1:1，格式见 [00_init/剧本.md](../../../00_init/剧本.md)），落盘 `25_剧本/`（**创作/审阅区，非运行时**；定稿审通过后由 `chapter-publisher` 转成 JSON 发布到 `99_game/`）。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| chapter_id_or_title | Chapter 节点 ID（snowflake）或 title 或 chapter_no | 必传 |
| target_status | `30`（定稿+校验→提交定稿审）或 `20`（仅草稿，回退提纲就绪） | `30` |

## 流程（三段式：查状态 → 完成任务 → 保存结果）

> 本 skill 是 Chapter 定稿段 status 的唯一写入点；剧本 YAML 由本 skill 直接创作产出。编剧是高自由度创作任务，**无纯产出子 skill**——创作与写图都在本 skill 内完成。

### 1. 查询目标节点状态

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查询。

#### 1a. 解析 Chapter + 前驱校验

```cypher
MATCH (ch:Chapter) WHERE ch.id='<input>' OR ch.title='<input>' OR ch.chapter_no=<input>
RETURN ch.id AS id, ch.outline_path AS outline_path, ch.script_path AS script_path, ch.status AS status
LIMIT 1
```

**前驱校验**：`ch.status = 20`（提纲就绪，`outline_path` 非空），否则停止并提示先完成提纲段（`chapter-outliner`）。

#### 1b. 读设计简报 + 提纲 + 查创作上下文

**先读两份创作依据**：
- Read `25_剧本/chapter<NN>_设计简报.md`（NN = chapter_no 零填充）——取出情感弧线 / 戏剧意图 / 设计支柱，本章对话的情感基调全靠它。
- Read `outline.yaml`（拓扑骨架 + `authoring` 引导块）。**区分**：拓扑骨架字段（meta/scenes/lines）必须原样搬到定稿；`authoring` 块（direction/beats/constraints 等）是创作指引，**不进定稿**。

任一缺失则停止并提示先跑上游（structurer / outliner）。

再查图：

```cypher
// (1) 出场角色 + 语言习惯（创作对话的核心依据——声音回检用它）
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

### 2. 完成任务（三轮打磨创作细节对话）

读 outline.yaml 每个 scene 骨架，**以 `authoring.beats` 为节拍依据**（beats 是引导不是约束），据设计简报（情感弧/戏剧意图）+ 角色 LanguageStyle，**三轮打磨**创作逐句 `lines` 填入（覆盖空的 lines 数组，保留提纲里的 choice/jump/ending 拓扑）。三轮打磨与声音标准详见 [references/对话写作方法论.md](references/对话写作方法论.md)——创作前读它。

#### 第一轮·功能（戏剧职责）

每段 lines 完成明确的叙事职责——揭示信息 / 建立关系 / 制造压力 / 传递后果。对齐 outline 拓扑 + 设计简报情感弧：这段在情感弧线上的哪个位置？要推进什么情绪？无戏剧功能的台词删掉。

#### 第二轮·声音（像角色说话）

每句台词符合角色 LanguageStyle（`vocabulary`/`rhythm`/`habits`/`emotion_patterns`），通过**"真人会这样说话吗？"测试**：

- **避免"你也知道"式对话**——角色间不为让玩家了解情况而互相解释已知事实。
- **避免 on-the-nose 说明文伪装成对话**——角色不直白说出自己的动机/情绪（用潜台词、行为、反应传达）。
- **声音支柱一致性回检**：对照 1b 查到的 LanguageStyle 字段，检查产出 lines 是否真的用了该角色的 `vocabulary`（词汇偏好）/ `rhythm`（句式节奏）/ `habits`（口头禅）/ `emotion_patterns`（情绪模式）。不符则改。

> 声音标准与声音支柱模板详见 [references/对话写作方法论.md](references/对话写作方法论.md)。
> 句子层面是否**真的像角色在说话、有无机械感**（句长均匀 / 价值拔高 / 假口语化 / 心理判断腔等），按 [references/日常对白自然度技巧.md](references/日常对白自然度技巧.md) 的反模式清单自查。**反模式服从角色声音支柱**——命中角色 LanguageStyle 的说法不算机械。

#### 第三轮·精简（删多余的词）

删每个不值得存在的词。旁白不啰嗦、台词不留水分。精简后每条 say/narrate 都有其存在的必要。

精简收尾做两遍回读：保真回读（忠于 outline / 声音一致 / 潜台词没被说破）+ 残留味回读（句长过匀 / narrator 残留 / 价值拔高收尾等 5 类）。见 [references/日常对白自然度技巧.md](references/日常对白自然度技巧.md) 第 5 章。

#### 创作技术要求（格式正确性）

1. **lines 指令**：用 11 条指令（`say`/`narrate`/`show`/`hide`/`bg`/`bgm`/`sfx`/`choice`/`label`/`jump`/`ending`）。每条 `say` 必带 `who`/`portrait`/`pos`/`text` 全四字段，`pos` ∈ `left`/`center`/`right`。
2. **情感递进**：每个 scene 内部情绪有起伏（不是平铺），对齐设计简报情感弧线的该段位置。
3. **变体选用规则**：
   - 优先用 `status=11` 的已有变体。
   - 剧情需要某个不存在/未批准的变体（如「陈默.沉重」），仍写入 `portrait` 字段，并记录为「缺口」——段 3c 兜底建 `StandingIllustration(status=0)` + `depicts` 边，交 `plot-design` 推进。
4. **分支与结局**：`choice.options[]` 每项含 `label` + `to`/`scene`/`file` 至少其一；结局用 `ending{kind:BE/TE/HE/NE}`，对齐 `Event.ending_kind` 与 `option.leads_to_ending`。
5. **Write 落盘**：`25_剧本/chapter<NN>_<概述>.yaml`（定稿 YAML，命名同提纲文件名主体）。`Chapter.script_path` 指向此 `.yaml` 路径。
6. **YAML 写作规则**（严格 schema 子集 1:1）：所有 string 双引号；多行文本用双引号 + `\n`，禁块标量；bool 小写 `true/false`；字段顺序对齐 schema properties；**不加任何额外字段**（schema `additionalProperties:false`，`authoring` 块绝不搬进定稿）；`meta.requires.portraits` 在定稿段补齐（提纲段无）。

> 格式细节、11 指令字段、跳转寻址——严格按 [00_init/剧本.md](../../../00_init/剧本.md) 与 [99_game/data/剧本.schema.json](../../../99_game/data/剧本.schema.json)。

#### 创作质量自检（发现 outline 破碎 → FAIL 报告）

三轮打磨后，若发现**根本问题在 outline 而非台词**——即 outline 戏剧性破碎，再怎么打磨也写不出合格对话：
- 分支 options 无戏剧本质差异（outliner 的本质差异门控漏过的 flavor 级分支）
- scene 间无情绪推进（提纲本身平铺，无 turning point/climax）
- 拓扑死胡同或 ending 缺落点

→ **触发创作质量 FAIL**：**不落盘定稿、不写 status**，产出「结构性问题报告」返回，列出破碎点（哪个 choice/scene/拓扑 + 为什么写不出合格对话）。由 plot-design 接住后清 `outline_path` + 回 status=11，重调 `chapter-outliner` 重做提纲。**与 outliner 素材不足报告对称**——不硬凑烂对话交付。

> 通过自检（台词合格、问题只在格式）才进段 3 跑 schema 校验。

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

#### 3c. 立绘缺口兜底（副作用——对每个「缺口」变体 `<char_name>.<variant_label>`）

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

> `expands_to`/`ref_style` 边 `sync=true`（上游更新会级联重置该立绘）；`depicts` 边 `sync=false`（编排引用，不级联）。这些 `status=0` 的立绘缺口节点是 **plot-design 后续按 depicts 直调 `char-stand-designer <stand_id>` 推进**的输入。

**status 写入**：定稿+校验通过 → `30`（定稿待审，等 dashboard 终审 `approve`→`31`）；schema 失败/草稿 → `20`；创作质量 FAIL → 不写 status（见段 2 末尾）。

最后汇总：定稿 `script_path`、Chapter `status=30`、标记的立绘缺口（stand_id + status=0，待 plot-design 推进）。若触发创作质量 FAIL，汇总「结构性问题报告」而非定稿路径。

## 参考文档

- 创作方法论：[references/对话写作方法论.md](references/对话写作方法论.md) — 写作标准/声音支柱/三轮打磨/潜台词
- 自然度技巧：[references/日常对白自然度技巧.md](references/日常对白自然度技巧.md) — 句子层面去机械感/反模式清单/回读检查（第二轮声音、第三轮精简时查）
- 剧本格式：[00_init/剧本.md](../../../00_init/剧本.md) — YAML/JSON 结构、11 指令、跳转寻址（创作区 YAML / 运行时 JSON）
- 剧本 schema：[99_game/data/剧本.schema.json](../../../99_game/data/剧本.schema.json) — 校验门
- 剧情 Schema：[00_init/Schema/剧情.md](../../../00_init/Schema/剧情.md) — Chapter/depicts 边
- 角色美术 Schema：[00_init/Schema/角色美术.md](../../../00_init/Schema/角色美术.md) — StandingIllustration 字段
- 上游：[chapter-structurer](../chapter-structurer/SKILL.md)（产设计简报）/ [chapter-outliner](../chapter-outliner/SKILL.md)（产提纲 → status=20）
- 下游：plot-design agent（定稿审 status=31 后，按 depicts 推进立绘 + chapter-publisher 发布）
