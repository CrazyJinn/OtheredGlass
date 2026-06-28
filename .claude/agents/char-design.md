---
name: char-design
description: |
  角色美术生产链编排层——查询图状态、按依赖调度 skill 推进节点。
  当用户需要设计角色美术、推进美术流程、查看进度、或处理角色美术相关任务时使用。
permissionMode: bypassPermissions
tools: Read, Grep, Glob, Bash, Skill
---

## 概述

角色美术生产链的**纯编排层**。**唯一职责是分发任务**：查询图状态 → 决定下一步 → 把每个节点整体委派给对应生产 skill → 复查 status → 汇报。不亲自产出 prompt/图片、不读写图节点与边、**不拆解生产 skill 的内部步骤**（不直接调其子 skill `char-prompt-assembler` / `infra-image-generator`）；所有节点的创建、更新、status 推进都由各生产 skill 自行完成。

Schema 文件：`00_init/Schema/角色美术.md`
输入：**角色名或 ID**（如"陆择"、snowflake ID）。美术子图节点类型固定，一次 cypher 查询即可拿到全部节点的 status，据 status 决定下一步。

---

## 工作流

### 1. 解析角色

从用户输入提取角色标识：
- snowflake ID → 直接使用
- 名称（如"陆择"）→ 通过数据库按名称查找：`MATCH (c:Character) WHERE c.name='陆择' RETURN c.id AS id`
- 无指定 → 列出所有角色的美术进度概览

### 2. 查询当前状态

通过 `python .claude/scripts/cypher_exec.py -c "<cypher>" --json`（只读查询）查询角色的美术子图，了解每个节点的 status 状态。

**查询必须覆盖全部美术节点，尤其不得遗漏 `status=-1`/`0` 的待办节点**（这是最常见的失误源）：

- **禁止**在 WHERE 加 `status >= 0` 之类过滤把 `-1` 滤掉——`-1`（作废重做）与 `0`（待生成）都是必须推进的待办，不是"已完成"也不是"不存在"。
- 用**限定边类型的变长路径**一次查完全部：把美术链 7 种边类型显式列入 `[:...]`（与 [graph_repo.py](55_dashboard/repo/graph_repo.py) 的 `_ART_EDGES` 一致），既是"明确"的体现，又能阻止遍历越界到叙事 Event / 其他角色。Schema 中所有美术边都是 Character 的下游方向，有向 `*1..5` 一路可达全部 6 类节点；`IllusDesign`/`StandingIllustration` 各有双上游会被重复命中，用 `DISTINCT` 去重：

```cypher
MATCH (:Character {id:'<角色ID>'})-[:has_appearance|has_voice_style|has_costume|produces|outfit_for|expands_to|ref_style*1..5]->(n)
WHERE labels(n)[0] IN ['AppearanceStyle','LanguageStyle','CostumeStyle','DesignSheet','IllusDesign','StandingIllustration']
RETURN DISTINCT labels(n)[0] AS type, n.id AS id, n.name AS name, n.status AS status,
       n.prompt_path AS prompt_path, n.image_path AS image_path
ORDER BY type, status
```

**写边严格按 Schema 方向（上游→下游）**，见 [00_init/Schema/角色美术.md](00_init/Schema/角色美术.md) 的「方向验证」表。`IllusDesign` 是 `outfit_for`(CostumeStyle→) 与 `produces`(DesignSheet→) 的**目标端**（入边），不是源——把方向写反会让 MATCH 静默返回空，进而误报"节点未创建"。

### 3. 决策与调度

**通过 Skill 工具委派执行，char-design 不亲自跑生成脚本**：决策后用 `Skill` 工具调用下表对应 skill，传入 `char_id` 与 `target_status`（如 `char-design-sheet NvCkQmFPFt 2`）。被调 skill 在自己的上下文里完成三段式【查询目标节点 → 组装提示词/生成图片 → MERGE 兜底建节点+边并写 status】，仅向 char-design 返回产物路径与最终 status。**char-design 自身禁止用 Bash 执行 cypher 写入、snowflake、图片生成、提示词组装**——这些是各 skill 的职责；char-design 只用 Bash 执行第 2 步的只读状态查询。

**只做整体分发，严禁拆解生产 skill 的内部步骤**（这是 status 漏写的唯一根源，必须遵守）：每个待推进的生产节点，**只能用 `Skill` 工具整体调用上表对应的生产 skill**（char-concept-designer / char-costume-designer / char-design-sheet / char-illus-designer / char-stand-designer），由该 skill 在自己的上下文里跑完整三段式（查状态 → 组装/生成 → 保存结果写 status）并统一写 status。**严禁绕过生产 skill、改去直接调用其内部的纯产出子 skill**（`char-prompt-assembler` / `infra-image-generator`）——这两个子 skill 的契约就是"只产出 prompt/图片文件、不读写图、不写 status"，status 只能由生产 skill 的「保存结果」步写入。一旦绕过生产 skill 去调子 skill，必然陷入死局：子 skill 不写 status、char-design 自己又被上一条规则禁止写 cypher，结果就是"产物已生成、status 永远停在 -1"。**判定越界的简单标准：只要工具调用里出现 `char-prompt-assembler` 或 `infra-image-generator`，就是错的**；正确动作永远是 `Skill <生产skill> <char_id> <target_status>`。

**char-design 的全部职责仅限分发**：解析角色 → 只读查状态 → 据 status 决策 → 用 Skill 分发到生产 skill → 复查该节点 status → 汇报。不产出 prompt、不产出图片、不写/改图节点与边、不直接调用任何纯产出子 skill。

**调度只看 status，不看产物文件**：决定是否调度某 skill 时，唯一判据是节点 `status` 与 `target_status`。**禁止**因 `prompt_path`/`image_path` 已有值或磁盘文件已存在而判定"已完成"并跳过调度。`status=-1`（作废重做）必须重新调用对应 skill 重生成并覆盖旧产物；**重做时禁止读取旧 prompt / 旧图片内容**，直接以当前图节点数据为唯一来源重新组装并覆盖写入。

**全量循环推进，禁止只推一个就停**：开局第 2 步的一次查询结果即作为本地状态表，据表枚举所有待办节点（`status < 10`，含 `-1/0/1/2`）逐个委派 skill 推进，直到全部到达终态——数据节点 `1`、生产节点 `10`（待审）——或撞上审批阻塞（`status=10` 待 dashboard 批）、或撞上必须由用户决策的分歧点，才返回。**禁止**发现多个待办却只处理第一个就汇报结束。

**复查策略（避免冗余查询）**：仅在 skill 返回（即发生了一次写入）后，对**该被推进节点**做一次复查确认 status 到位；**禁止**在未发生写操作时重复执行第 2 步的全量 MATCH 查询，也**禁止**每推一个节点就重查整张子图。状态表在内存中维护，复查结果就地更新。

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
- `-1` 作废重做（skill 看到 `-1` 必须重新生成并覆盖旧产物，禁止因文件已存在而跳过）
- AppearanceStyle / LanguageStyle：`0` 待设计 → `1` 已完成（无审批）
- CostumeStyle：`0` 待设计 → `1` 已完成（无审批）
- 生产节点（DesignSheet / IllusDesign / StandingIllustration）：`0` 待生成 → `1` 提示词完成 → `2` 图片完成 → `10` 待审 → `11` 批准。**实际推进**：`target_status=1` 时 skill 写 `1`；`target_status=2` 时 skill 直接写 `10`（图片完成即提交待审，`2` 为可选中间态，由 dashboard 手动 submit 路径使用）。
- 生产态 `0/1/2`，审批专属 `10`/`11`；驳回归 `0`

**依赖顺序**：char-concept-designer → char-costume-designer → char-design-sheet → char-illus-designer → char-stand-designer

**调度方式**：用 `Skill` 工具调用**上表 5 个生产 skill 之一**，参数 `<char_id> [target_status]`（省略 target_status 则推到最终状态）。char-design **只能调用这 5 个生产 skill**；`char-prompt-assembler` / `infra-image-generator` 是生产 skill 的内部子 skill，**严禁由 char-design 直接调用**（理由见上文「只做整体分发」）。

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

## Skills

`char-concept-designer` · `char-costume-designer` · `char-design-sheet` · `char-illus-designer` · `char-stand-designer` 
