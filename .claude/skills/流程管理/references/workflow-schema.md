# 数据文件结构说明

## 目录

- [workflow.yaml](#workflowyaml)
- [backlog.yaml](#backlogyaml)
- [feedback.yaml](#feedbackyaml)
- [history.yaml](#historyyaml)

---

## workflow.yaml

### 顶层结构

```yaml
version: 1.0
generated_at: 2026-04-02T10:00:00
source: ReadMe.md

nodes:
  <node_id>:
    # ... 节点配置
```

### 节点字段

```yaml
叙事设计:
  name: 叙事设计                # 显示名称
  skill: null                   # 对应 skill（人工任务为 null）
  description: "查询关系图/事件链/信息层级/场景序列 → 叙事节奏.md、角色声线.md"
  execution_type: skill         # skill | api | manual | auto
  predecessors: [neo]
  successors: [剧本组装]
  status: pending               # pending | ready | in_progress | completed | blocked
  retry_count: 0
  started_at: null
  completed_at: null
```

### execution_type 执行类型

| 值 | 含义 | 示例 |
|----|------|------|
| `skill` | 调用 Claude skill | 叙事设计、角色设计 |
| `api` | 调用外部 API | 文生图、图生图 |
| `manual` | 需要人工处理 | 游戏组装 |
| `auto` | 自动化脚本 | 装饰裁剪、资源搬运 |

### 状态转换

状态完全由 **依赖关系 + feedback** 驱动，不检查文件是否存在：

```
pending → ready → in_progress → completed
   ↑          ↓         ↓
   │          │         ├─→ blocked (unable_to_process)
   │          │
   └──────────┴──── 依赖更新时重新计算
```

- `completed`: feedback 中有 processed 记录
- `ready`: 所有 predecessors 状态为 completed
- `pending`: predecessors 未全部 completed
- `blocked`: feedback 中有 unable_to_process 记录

---

## backlog.yaml

ready 状态节点的可执行队列，按拓扑序排列。

```yaml
tasks:
  - task_name: 叙事设计
    skill: null
  - task_name: 角色设计
    skill: 角色设计
  - task_name: 美术提示词
    skill: null
```

**生成时机**：
- `init`: 初始化时生成
- `review`: 处理 feedback 后更新
- `status`: 全面重建

---

## feedback.yaml

任务执行摘要，由被调用的 skill 写入（非流程管理写入）。

```yaml
entries:
  - task_name: 角色设计
    skill: 角色设计
    executed_at: "2026-04-02T12:00:00"
    processed:              # 已成功完成
      - "生成角色美术设定.md"
      - "生成角色语言风格.md"
    unprocessed:            # 需后续处理，留在 backlog
      - []
    unable_to_process:      # 无法处理，标记 blocked
      - []
```

**写入职责**：由 `run` 唤起的 skill 在执行完成后写入，流程管理只负责读取和处理。

**三类摘要说明**：

| 类型 | 含义 | 后续动作 |
|------|------|----------|
| processed | 已成功完成 | 节点标记 completed |
| unprocessed | 需要后续处理 | 保留在 backlog |
| unable_to_process | 无法处理，需人工介入 | 节点标记 blocked |

---

## history.yaml

执行历史 + 归档。

```yaml
history:
  - task_name: 角色设计
    skill: 角色设计
    status: completed       # completed | partial | failed
    started_at: "2026-04-02T12:00:00"
    completed_at: "2026-04-02T12:35:00"
    summary: "完成角色美术设定和语言风格"

archived:
  - period: "2026-04-01 ~ 2026-04-02"
    total: 8
    completed: 6
    failed: 2
    tasks: [叙事设计, 角色设计]
```

**压缩规则**：`status` 命令保留最近 10 条详细记录，更早记录压缩到 archived。
