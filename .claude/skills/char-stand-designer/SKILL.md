---
name: char-stand-designer
description: |
  推进 StandingIllustration 图节点：查询状态 → 组装提示词/生成图片 → 保存结果（MERGE 兜底建节点+边，写产物与 status）。
  两种入参模式：(A) char_id——对该角色每个 IllusDesign 按优先级（P0/P1/P2）批量拓展表情变体；(B) stand_id——只推进指定单个变体（供 plot-design 按 depicts 引用按需出图）。
argument-hint: <char_id|stand_id> [target_status]
arguments:
  - char_id_or_stand_id
  - target_status
allowed-tools: Read, Bash, Write, Edit
---

> **status=-1 = 作废重做**：当 StandingIllustration 被 sync 级联重置为 `status=-1` 时，即使 `prompt_path`/`image_path` 已存在，也**必须重新生成并覆盖**（重走 0→1→2）。`-1` 与 `0` 都视为"需生成"起点；`-1` 明确表示有旧产物要覆盖，**禁止因文件已存在而跳过**。

# 立绘变体（StandingIllustration）

从 IllusDesign 拓展出不同表情、动作的单张立绘，表情和动作参考 LanguageStyle 生成。支持两种调用模式：

- **模式 A（char_id）**：角色级全量。对该角色每个 IllusDesign，按角色优先级（P0/P1/P2）批量补全变体到目标数量。
- **模式 B（stand_id）**：单变体按需。只推进指定的那一个 StandingIllustration（通常由 `chapter-dialoguer` 兜底建的 `status=0` 缺口节点，经 `plot-design` 按 depicts 引用触发）。避免为未被剧情引用的变体浪费出图 API。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| char_id 或 stand_id | 角色 ID（模式 A，按 priority 批量）或单个立绘变体 ID（模式 B，按需单个）。按输入节点的 label 自动判定。 | 必传 |
| target_status | 推进目标：`1`（仅提示词）或 `2`（到图片） | `2` |

## 流程（三段式：查状态 → 完成任务 → 保存结果）

> 本 skill 是 status 的唯一写入点；提示词与图片由子 skill 纯产出，本 skill 在「保存结果」步统一写入图。

### 1. 查询目标节点状态

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查询。

#### 1a. 判定模式

```cypher
MATCH (n) WHERE n.id='<input>' RETURN labels(n)[0] AS label
```

- `Character` → **模式 A**（char_id，角色级全量，转 1b-A）。
- `StandingIllustration` → **模式 B**（stand_id，单变体按需，转 1b-B）。

#### 1b-A. 模式 A：查角色全量变体（char_id）

```cypher
MATCH (ch:Character {id:'<char_id>'})
MATCH (ch)-[:has_voice_style]->(voice:LanguageStyle)
MATCH (ch)-[:has_appearance]->(:AppearanceStyle)-[:produces]->(:DesignSheet)-[:produces]->(illus:IllusDesign)
OPTIONAL MATCH (illus)-[:outfit_for]->(cos:CostumeStyle)
OPTIONAL MATCH (illus)-[:expands_to]->(stand:StandingIllustration)
RETURN ch.name AS char_name, ch.priority AS priority,
       voice.id AS voice_id, voice.emotion_patterns AS emotion_patterns,
       illus.id AS illus_id, illus.image_path AS illus_image, cos.name AS cos_name,
       collect(stand) AS stands
```

- **前驱校验**：`illus` 的 status = `11`（IllusDesign 已批准），否则停止并提示先推进/审批上游。
- **变体数量**（按角色优先级）：

  | 角色优先级 | 变体数量 | 示例变体标签 |
  |-----------|---------|------------|
  | P0（主角） | 10 | 默认、微笑、生气、悲伤、惊讶、思考、坚定、恐惧、战斗姿态、受伤 |
  | P1（核心 NPC） | 6 | 按角色定制 |
  | P2（一般 NPC） | 2 | 默认、微笑 |

- **目标节点判定**：对每个 IllusDesign 比对应有变体数与目标数量；为缺失的变体生成新 snowflake id（批量）：
  ```bash
  python "${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py" -n <缺几个> -q
  ```
  已有变体按 status 决定推进起点。各变体的表情/动作标签按变体语义推导。

#### 1b-B. 模式 B：查单个变体 + 上游（stand_id）

```cypher
MATCH (stand:StandingIllustration {id:'<stand_id>'})
MATCH (illus:IllusDesign)-[:expands_to]->(stand)
MATCH (voice:LanguageStyle)-[:ref_style]->(stand)
MATCH (ch:Character)-[:has_voice_style]->(voice)
OPTIONAL MATCH (illus)-[:outfit_for]->(cos:CostumeStyle)
RETURN ch.name AS char_name, ch.id AS char_id,
       voice.id AS voice_id, voice.emotion_patterns AS emotion_patterns,
       illus.id AS illus_id, illus.image_path AS illus_image, illus.status AS illus_status,
       cos.name AS cos_name,
       stand.id AS stand_id, stand.variant_label AS variant_label, stand.status AS status,
       stand.eye AS eye, stand.brow AS brow, stand.mouth AS mouth,
       stand.head_angle AS head_angle, stand.hand AS hand, stand.foot AS foot
```

- **前驱校验**：`illus_status = 11`（IllusDesign 已批准），否则停止并提示上游未就绪（由 `plot-design` 委派 `char-design` 推进 IllusDesign 后再来）。
- **节点已存在**（通常由 `chapter-dialoguer` 兜底建为 `status=0`）：直接按 status 决定推进起点。`variant_label` 已在节点上；若 `eye`/`brow`/`mouth`/`head_angle`/`hand`/`foot` 标签缺失，按 `variant_label` 语义推导并在保存步补写。
- 模式 B **只处理这一个 stand**，不枚举其他变体、不走 priority 补全。

> 查不到（stand_id 不存在 / 缺上游 `expands_to` 或 `ref_style`）→ 报告并停止。

### 2. 完成任务

对（模式 A 的每个待推进变体 / 模式 B 的单个变体）推进：

#### 推进到提示词（status → 1）

使用 Skill 工具调用 `char-prompt-assembler`，参数 `StandingIllustration '<data_json>'`：

```json
{
  "stand": { "tags": {"variant_label":"...","eye":"...","brow":"...","mouth":"...","head_angle":"...","hand":"...","foot":"..."} },
  "voice": { "emotion_patterns":"...", "description":"..." },
  "character": { "id":"<char_id>", "name":"<char_name>" },
  "node": { "id":"<stand_id>" }
}
```

char-prompt-assembler 组装 prompt 文件到 `06_角色美术/<char_name>/prompts/<stand_id>.md` 并返回路径 `PROMPT_PATH`。

#### 推进到图片（status → 2，仅 target_status=2）

使用 Skill 工具调用 `infra-image-generator`，参数 `<PROMPT_PATH> <OUTPUT_PATH> <illus_image>`（图生图，以 IllusDesign 图片为参考）：

`OUTPUT_PATH = 06_角色美术/<char_name>/<cos_name>/<variant_label>立绘.png`。infra-image-generator 返回路径 `IMAGE_PATH`。

### 3. 保存结果（MERGE 兜底 + 写产物 + 推进 status）

对每个变体一次性写入（节点不存在则兜底创建；模式 B 节点通常已存在，MERGE 幂等）：

```cypher
MERGE (stand:StandingIllustration {id: '<stand_id>'})
  ON CREATE SET stand.status = 0, stand.variant_label = '<variant_label>',
                stand.eye = '<...>', stand.brow = '<...>', stand.mouth = '<...>',
                stand.head_angle = '<...>', stand.hand = '<...>', stand.foot = '<...>';
MATCH (illus:IllusDesign {id: '<illus_id>'}), (stand:StandingIllustration {id: '<stand_id>'})
MERGE (illus)-[r:expands_to]->(stand) SET r.sync = true, r.variant_label = '<variant_label>';
MATCH (voice:LanguageStyle {id: '<voice_id>'}), (stand:StandingIllustration {id: '<stand_id>'})
MERGE (voice)-[r:ref_style]->(stand) SET r.sync = true;
MATCH (stand:StandingIllustration {id: '<stand_id>'})
SET stand.prompt_path = '<PROMPT_PATH>',
    stand.image_path  = '<IMAGE_PATH>',     // 仅 target_status=2 时
    stand.status = <1 | 10>;                // target_status=1 → 1；target_status=2 → 10（待审）
```

**status 写入**：仅提示词 → `1`；到图片 → `10`（待审）。StandingIllustration 是终端节点，无下游。

## 参考文档

- 提示词组装：[char-prompt-assembler](../char-prompt-assembler/SKILL.md) Mode C
- 图片生成：[infra-image-generator](../infra-image-generator/SKILL.md)
- 按需触发方：[plot-design](../../agents/plot-design.md) agent（模式 B，按 depicts 引用传 stand_id）
