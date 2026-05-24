---
name: 流程管理
description: "开发流程中央调度器。管理工作流配置、待办队列、执行历史和任务反馈。触发条件：(1) 需要初始化工作流 (2) 查看当前进度 (3) 处理反馈更新待办 (4) 执行下一个任务"
allowed-tools: Read, Bash, Write, Edit
---

# 流程管理

开发流程的中央调度器，协调所有其他 skill 的执行。

## 命令

| 命令 | 功能 |
|------|------|
| `/流程管理 init` | 从 README 解析 mermaid → 生成全部数据文件 |
| `/流程管理 review` | 处理 feedback → 更新 workflow 状态和待办队列 |
| `/流程管理 run` | 取待办任务 → 调用 skill → 记录 history |
| `/流程管理 status` | 状态检查 → 重建待办 → 压缩历史 → 输出报告 |

## 数据文件

所有数据位于 `99_流程管理/` 目录下，共 4 个文件：

| 文件 | 职责 |
|------|------|
| `workflow.yaml` | 节点配置 + 状态（唯一数据源） |
| `backlog.yaml` | ready 节点的待办队列，按拓扑序排列 |
| `feedback.yaml` | skill 执行后的结果摘要（由 skill 写入） |
| `history.yaml` | 执行历史 + 归档 |

Schema 详见 [workflow-schema.md](references/workflow-schema.md)。

---

## init - 工作流初始化

从 README.md 的 mermaid flowchart 解析生成全部数据文件。

**执行流程**：
1. 读取 README.md 中 `flowchart TB` 代码块（忽略 sequenceDiagram）
2. 提取子图（阶段）为 workflow 节点，内部产出物写入 description
3. 提取连接线 → predecessors/successors
4. 提取样式类 → execution_type
   - 解析规则详见 [mermaid-parsing-guide.md](references/mermaid-parsing-guide.md)
5. 生成 `workflow.yaml`（节点配置 + 初始状态）
6. 初始化空的 `backlog.yaml`、`feedback.yaml`、`history.yaml`
7. 将所有 ready 节点按拓扑序写入 `backlog.yaml`

---

## review - 处理反馈，更新待办

读取 skill 执行后写入的 feedback，更新工作流状态和待办队列。

**执行流程**：
1. 读取 `feedback.yaml` 中最新的 entry
2. 按类型处理：
   - **processed**：workflow 节点 → completed，级联更新下游
   - **unprocessed**：保留在 backlog
   - **unable_to_process**：节点 → blocked
3. 更新 `backlog.yaml`
4. 清理已处理的 feedback 条目

---

## run - 唤起 skill，记录结果

从待办队列取任务，调用对应 skill 执行，并记录执行历史。

**执行流程**：
1. 从 `backlog.yaml` 取第一个待办任务
2. 从 `workflow.yaml` 读取该任务的 skill 名称
3. 更新该节点 status: in_progress
4. 调用 `/{skill_name}`，传入 **task_name**
5. skill 自行管理输入输出，执行完成后自行写入 `feedback.yaml`
6. 读取 feedback，在 `history.yaml` 追加执行记录：
   ```yaml
   history:
     - task_name: 角色设计
       skill: 角色设计
       status: completed       # completed | partial | failed
       started_at: "2026-04-02T12:00:00"
       completed_at: "2026-04-02T12:35:00"
       summary: "完成角色美术设定和语言风格"
   ```

---

## status - 状态检查与数据维护

三步维护 + 输出报告。

### 1. 更新 workflow

遍历所有节点，根据依赖关系和 feedback 更新状态：

| 状态 | 条件 |
|------|------|
| completed | feedback 中有 processed 记录 |
| ready | 所有前置任务 completed |
| pending | 前置任务未全部完成 |
| blocked | feedback 中有 unable_to_process 记录 |

### 2. 重建 backlog

收集 status=ready 的节点 → 拓扑排序 → 覆盖写入 `backlog.yaml`

### 3. 压缩 history

保留最近 10 条详细记录，更早记录压缩为 archived 摘要。

### 4. 输出状态报告

```
节点状态: completed 5 | ready 3 | pending 8 | blocked 1
待办队列: 角色设计 → 场景设计 → 美术提示词
最近反馈: 角色设计 完成角色美术设定和语言风格
```

---

## 与其他 Skill 的集成

**调用接口**：`run` 只传入 `task_name`，skill 完全自治——自行决定输入来源、输出目录和执行内容。

**职责划分**：

| 流程管理 | Skill |
|---------|-------|
| 传入 task_name | 确定输入数据来源和输出目录 |
| 读取 feedback.yaml | 执行任务并产出文件 |
| 更新 workflow/history | 写入 feedback.yaml（processed / unprocessed / unable_to_process） |
