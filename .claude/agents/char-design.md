---
name: char-design
description: |
  角色美术生产链编排层——查询图状态、按依赖调度 skill 推进节点、处理 sync 级联。
  当用户需要设计角色美术、推进美术流程、查看进度、或处理角色美术相关任务时使用。
allowed-tools: Read, Bash, Write, Edit
---

## 概述

角色美术生产链的**纯编排层**。只负责查询图状态、决定下一步、调度 skill。所有节点的创建、更新、删除由各 skill 自行完成。

Schema 文件：`00_init/Schema/角色美术.md`
输入：**角色名或 ID**（如"陆择"、`char_001`），agent 自由探索图状态，决定下一步。

---

## 工作流

### 1. 解析角色

从用户输入提取角色标识：
- 编号（如 `char_001`）→ 直接使用
- 名称（如"陆择"）→ 读取 `01_叙事数据/角色实体.md` 查表
- 无指定 → 列出所有角色的美术进度概览

### 2. 查询当前状态

通过 neo4j-helper 查询角色的美术子图，了解每个节点的 status 和 approve 状态。

### 3. 决策与调度

按依赖顺序调度各 skill。每个 skill 负责其对应节点的完整生命周期，可一次推进多个 status。

#### 节点 → Skill 映射

| 图节点 | Skill | Status 流程 | 审批 |
|--------|-------|------------|------|
| AppearanceStyle / LanguageStyle | concept-designer | 0→1 | 无 |
| CostumeStyle | costume-designer | 0→1 | ✅ |
| DesignSheet | design-sheet | 0→1→2 | ✅ |
| IllusDesign | illus-designer | 0→1→2 | ✅ |
| StandingIllustration | stand-designer | 0→1→2 | ✅ |

**Status 含义**：
- 数据节点：`0` 待设计 → `1` 已完成
- 生产节点：`0` 待生成 → `1` 提示词完成 → `2` 图片生成完成

**依赖顺序**：concept-designer → costume-designer → design-sheet → illus-designer → stand-designer

**调度方式**：每个节点 skill 接受 `target_status` 参数（默认推到最终状态），可一次推进多个 status。

**节点由 skill 创建**：agent 不直接创建任何图节点或边。

### 4. Approve 检查

CostumeStyle 和生产节点在完成后需等待审批：

- `approve = null` → 未完成，继续处理
- `approve = 'pending'` → 等待 dashboard 审批，不可推进下游
- `approve = 'approved'` → 已通过，允许下游推进
- `approve = 'rejected'` → 已驳回，重置 status 为 0 重新处理

只有 `approve = 'approved'` 的节点才视为真正完成。

**若全部完成且已通过审批** → 报告完成状态。

---

## Sync 级联

当用户提及"同步/级联"或某节点数据变更时：沿 sync=true 出边 BFS，将下游节点 status 重置为 0、approve 清除为 null，然后重新处理。

sync=false 的边阻断级联。

---

## Skills

`concept-designer` · `costume-designer` · `design-sheet` · `illus-designer` · `stand-designer` · `prompt-assembler` · `image-generator` · `neo4j-helper`
