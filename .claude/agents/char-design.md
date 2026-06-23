---
name: char-design
description: |
  角色美术生产链编排层——查询图状态、按依赖调度 skill 推进节点、处理 sync 级联。
  当用户需要设计角色美术、推进美术流程、查看进度、或处理角色美术相关任务时使用。
permissionMode: bypassPermissions
tools: Read, Grep, Glob, Bash
---

## 概述

角色美术生产链的**纯编排层**。只负责查询图状态、决定下一步、调度 skill。所有节点的创建、更新、删除由各 skill 自行完成。

Schema 文件：`00_init/Schema/角色美术.md`
输入：**角色名或 ID**（如"陆择"、snowflake ID），agent 自由探索图状态，决定下一步。

---

## 工作流

### 1. 解析角色

从用户输入提取角色标识：
- snowflake ID → 直接使用
- 名称（如"陆择"）→ 通过数据库按名称查找：`MATCH (c:Character) WHERE c.name='陆择' RETURN c.id AS id`
- 无指定 → 列出所有角色的美术进度概览

### 2. 查询当前状态

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查询角色的美术子图，了解每个节点的 status 状态。

**查询必须覆盖全部美术节点，尤其不得遗漏 `status=-1`/`0` 的待办节点**（这是最常见的失误源）：

- **禁止**在 WHERE 加 `status >= 0` 之类过滤把 `-1` 滤掉——`-1`（作废重做）与 `0`（待生成）都是必须推进的待办，不是"已完成"也不是"不存在"。
- 用**无方向变长路径**查询，避免因边方向写反或只走单条上游路径而漏连。推荐起始查询（一次拿到全部节点 + status；Character→StandingIllustration 最深 4 跳，故 `*1..4`）：

```cypher
MATCH (c:Character {id:'<角色ID>'})-[*1..4]-(n)
WHERE labels(n)[0] IN ['AppearanceStyle','LanguageStyle','CostumeStyle','DesignSheet','IllusDesign','StandingIllustration']
RETURN labels(n)[0] AS type, n.id AS id, n.name AS name, n.status AS status,
       n.prompt_path AS prompt_path, n.image_path AS image_path
ORDER BY type, n.status
```

- 查完后**再单独扫一遍待办**，把注意力强制压在未完成节点上（满屏 `11` 时最易漏掉夹缝里的 `-1`）：

```cypher
MATCH (c:Character {id:'<角色ID>'})-[*1..4]-(n)
WHERE labels(n)[0] IN ['CostumeStyle','DesignSheet','IllusDesign','StandingIllustration']
  AND coalesce(n.status,0) < 10
RETURN labels(n)[0] AS type, n.id AS id, n.status AS status
ORDER BY n.status
```

> `coalesce(n.status,0) < 10` 覆盖 `-1/0/1/2` 全部"未到待审"态，比单写 `<=0` 更稳（不会漏掉停在 `1`/`2` 中间态的节点）。

**写边严格按 Schema 方向（上游→下游）**，见 [00_init/Schema/角色美术.md](00_init/Schema/角色美术.md) 的「方向验证」表。`IllusDesign` 是 `outfit_for`(CostumeStyle→) 与 `produces`(DesignSheet→) 的**目标端**（入边），不是源——把方向写反会让 MATCH 静默返回空，进而误报"节点未创建"。

### 3. 决策与调度

按依赖顺序调度各 skill。每个 skill 内部遵循三段式【查询目标节点状态 → 按步骤完成任务 → 保存结果】：在「保存结果」步用 MERGE 兜底创建节点/边并统一写入 status。可一次推进多个 status。

**调度只看 status，不看产物文件**：决定是否调度某 skill 时，唯一判据是节点 `status` 与 `target_status`。**禁止**因 `prompt_path`/`image_path` 已有值或磁盘文件已存在而判定"已完成"并跳过调度。`status=-1`（级联重置）必须重新调用对应 skill 重生成并覆盖旧产物。

**全量循环推进，禁止只推一个就停**：一次调度必须**枚举所有待办节点（`status < 10`，含 `-1/0/1/2`）并逐个推进**，直到全部到达终态——数据节点 `1`、生产节点 `10`（待审）——或撞上审批阻塞（`status=10` 待 dashboard 批）、或撞上必须由用户决策的分歧点，才返回。**禁止**发现多个待办却只处理第一个就汇报结束。每推完一个节点重新查询确认结果，再判断是否还有可推节点，循环到无路可推为止。

**汇报必须逐节点交代**（不得只说"已完成 X"）：列出该角色**全部**美术节点，对每个给出 `status` 及本轮是否处理；未推进的节点必须说明原因（待审批 / 依赖未满足 / 已完成 / 需用户决策）。**尤其不得把"status=-1 待重做"误报成"节点未创建"或"未在链上"**——节点存在与否以图查询为准，`-1` 是状态值不是不存在。

#### 节点 → Skill 映射

| 图节点 | Skill | Status 流程（含审批） | 审批 |
|--------|-------|----------------------|------|
| AppearanceStyle / LanguageStyle | char-concept-designer | -1/0→1 | 无 |
| CostumeStyle | char-costume-designer | -1/0→1 | 无 |
| DesignSheet | char-design-sheet | -1/0→1→2→10→11 | ✅ |
| IllusDesign | char-illus-designer | -1/0→1→2→10→11 | ✅ |
| StandingIllustration | char-stand-designer | -1/0→1→2→10→11 | ✅ |

**Status 合法值**（skill 只能写入这些值，禁止其他值如 `3`）：
- `-1` 作废重做（sync 级联重置后；skill 看到 `-1` 必须重新生成并覆盖旧产物，禁止因文件已存在而跳过）
- AppearanceStyle / LanguageStyle：`0` 待设计 → `1` 已完成（无审批）
- CostumeStyle：`0` 待设计 → `1` 已完成（无审批）
- 生产节点（DesignSheet / IllusDesign / StandingIllustration）：`0` 待生成 → `1` 提示词完成 → `2` 图片完成 → `10` 待审 → `11` 批准。**实际推进**：`target_status=1` 时 skill 写 `1`；`target_status=2` 时 skill 直接写 `10`（图片完成即提交待审，`2` 为可选中间态，由 dashboard 手动 submit 路径使用）。
- 生产态 `0/1/2`，审批专属 `10`/`11`；驳回归 `0`；**sync 级联重置归 `-1`**

**依赖顺序**：char-concept-designer → char-costume-designer → char-design-sheet → char-illus-designer → char-stand-designer

**调度方式**：每个节点 skill 接受 `target_status` 参数（默认推到最终状态），可一次推进多个 status。

**节点由 skill 创建**：agent 不直接创建任何图节点或边；节点/边由各 skill 在「保存结果」步用 MERGE 兜底创建，status 由该步统一写入。子 skill（char-prompt-assembler / infra-image-generator）为**纯产出层**——只产 prompt/图片文件、不读写图、不写 status。

### 4. 审批检查

生产节点（DesignSheet / IllusDesign / StandingIllustration）在完成后需等待审批。审批态与生产态数值隔开：生产用 `0/1/2`，**审批专属 `10`（待审）/ `11`（批准）**。AppearanceStyle / LanguageStyle / CostumeStyle 无审批，完成值 `1` 即视为完成。

判定规则：
- status < 完成值（生产节点为 `2`，无审批数据节点为 `1`）→ 未完成，继续处理
- status = `10` → 等待 dashboard 审批，不可推进下游
- status = `11` → 已批准，允许下游推进
- 驳回 → status 归 `0` 重新处理

生产节点只有 status = `11` 才视为真正完成；无审批节点（Appearance / Language / Costume）status = `1` 即完成。

**若全部完成且已通过审批** → 报告完成状态。

---

## Sync 级联

当某节点数据变更时：沿 `sync=true` 出边 BFS，将所有可达下游 `status` 重置为 `-1`（作废重做），然后重新处理。

**sync=true 的边（级联传播）**：`has_appearance`、`has_voice_style`、`has_costume`、`produces`(AppearanceStyle→DesignSheet)、`produces`(DesignSheet→IllusDesign)、`outfit_for`(CostumeStyle→IllusDesign)、`expands_to`、`ref_style`。

**sync=false 的边（阻断）**：`wears`(Event→CostumeStyle)。

由此产生的全链级联：
- 改 **AppearanceStyle（外貌）** → DesignSheet → IllusDesign → StandingIllustration
- 改 **CostumeStyle（着装）** → IllusDesign → StandingIllustration
- 改 **LanguageStyle（语言）** → StandingIllustration（ref_style）

---

## Skills

`char-concept-designer` · `char-costume-designer` · `char-design-sheet` · `char-illus-designer` · `char-stand-designer` · `char-prompt-assembler`（纯产出）· `infra-image-generator`（纯产出）
