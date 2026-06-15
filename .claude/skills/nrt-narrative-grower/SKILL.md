---
name: nrt-narrative-grower
description: |
  叙事自增长技能。通过图算法发现叙事缺口和增长机会，生成创意草案供人工审核，审核通过后通过 neo4j-helper 写入 Neo4j。
  三种模式：
  - analyze：运行 10 种图算法分析叙事缺口，输出结构化 JSON
  - generate：Claude 读取分析结果，撰写创意草案 .md 文件
  - apply：解析已批准草案，生成 Cypher 并通过 neo4j-helper 导入 Neo4j
  触发条件：
  (1) 用户要求分析叙事图的缺口或增长机会
  (2) 用户提到"叙事增长"、"补剧情"、"填时间线"、"角色弧"、"新事件"、"分析叙事"
  (3) 用户要求将已批准的叙事草案导入图数据库
  (4) Dashboard 审批触发
  前置依赖：Neo4j 服务已启动，neo4j Python 包已安装。
allowed-tools: Read, Bash, Write, Edit, Skill
---

# 叙事自增长

## 连接配置

- URI: `bolt://localhost:7687`
- User: `neo4j`
- Password: `12345678`（或环境变量 `NEO4J_PASSWORD`）

## 脚本位置

```bash
SCRIPT=".claude/skills/nrt-narrative-grower/scripts/narrative_grower.py"

# neo4j-helper 脚本（本项目内，用于 apply 时的写入操作）
NEO4J_HELPER=".claude/skills/infra-neo4j-helper/scripts"

# snowflake ID 生成器
SF_GEN="python .claude/scripts/snowflake_base62.py"
```

## Neo4j 标签约定

> ⚠️ 必须使用与 `01_叙事数据/csv/import.cypher` 一致的英文标签和属性名。

| 节点标签 | ID 属性 | 显示名属性 | 其他属性 |
|---------|---------|-----------|---------|
| `:Character` | `id` | `name` | `gender`, `description`, `birth_year`, `character_tags` |
| `:Event` | `id` | `title` | `time`, `description`, `type` |
| `:Scene` | `id` | `name` | `description` |
| `:Info` | `id` | `title` | `content`, `knowledge_level` |

---

## 模式一：analyze（图算法分析）

### Step 1: 运行分析

```bash
python $SCRIPT analyze --password 12345678
```

输出 JSON，包含 10 种图算法结果和综合增长机会。

### Step 2: 10 种分析算法

| # | 算法 | 检查内容 | 优先级 |
|---|------|---------|--------|
| 1 | 时间缺口分析 | 事件时间线上 >3 天的空缺区间 | 🔴 high |
| 2 | 角色弧追踪 | 角色参与事件的时间分布，检测消失的角色 | 🟡 medium |
| 3 | 隐式关系推断 | 共享事件但无 relation 边的角色对，推断关系类型 | 🔴 high |
| 4 | 事件链强度 | 无 evt_relation 边的事件，按角色重叠建议因果链 | 🟡 medium |
| 5 | 场景利用分析 | 每场景的事件数 + 角色数，标记低利用率场景 | 🟢 low |
| 6 | 信息深度分析 | 每实体各 knowledge_level 的分布，标记缺深层信息 | 🟡 medium |
| 7 | 子图连通性 | 角色参与构建邻接图，发现断连的子图 | 🟡 medium |
| 8 | 关系演化追踪 | relation 边的时间戳，检测应该有变化但静态的关系 | 🟢 low |
| 9 | 桥接场景建议 | 角色访问不同场景对，建议共享场景事件 | 🟢 low |
| 10 | 叙事密度评分 | 按时间段统计事件/角色/信息密度，标记失衡 | 🔴 high |

### Step 3: 理解输出

输出结构：

```json
{
  "analysis_id": "<snowflake_id>",
  "timestamp": "...",
  "summary": {
    "total_opportunities": 8,
    "high": 3, "medium": 3, "low": 2
  },
  "results": {
    "temporal_gaps": {...},
    "character_arcs": [...],
    ...10 个算法结果
  },
  "growth_opportunities": [
    {
      "priority": "high",
      "type": "temporal_gap_fill",
      "description": "Day 22 之后到 Day 30 缺少事件",
      "context": {...}
    }
  ]
}
```

---

## 模式二：generate（创意草案生成）

### Step 1: 读取分析结果

分析完成后，Claude 读取 JSON 输出中的 `growth_opportunities`，理解：
- 哪些时间段缺少事件
- 哪些角色关系缺失或应演化
- 哪些场景利用率低
- 哪些信息深度不足

### Step 2: 撰写创意草案

Claude 基于 `00_init/大纲.md` 中的世界观和角色设定，结合分析发现的缺口，
撰写自然语言的创意叙事草案。

**必须遵守的创作约束**：
- 角色性格与 `大纲.md` 的设定一致
- 事件时间线与已有事件衔接
- 场景选择与故事地理一致
- knowledge_level 判定：默认 2，非必要不升级到 3

### Step 3: 写入草案文件

先为草案和新实体生成 snowflake ID：

```bash
# 生成草案 ID + 事件 ID + 信息 ID（按需调整数量）
$SF_GEN -n 10 -q
```

将草案写入 `01_叙事数据/drafts/draft_<snowflake_id>.md`，格式：

```markdown
---
draft_id: <snowflake_id>
status: pending
created_at: YYYY-MM-DD
analysis_source: <analysis_snowflake_id>
opportunity_type: temporal_gap_fill | implicit_relation | character_revival | ...
priority: high | medium | low
title: "草案标题"
---

# 草案标题 — 叙事补全草案

## 背景
（缺口描述，引用分析结果）

## 建议新增事件
### <event_snowflake_id>: Day XX -- 事件标题

> **时间**：Day XX 时段
> **类型**：行动 / 交流 / 转折 / 状态变化
> **场景**：<scene_name>（从数据库查找 ID）
> **参与角色**：<char_name>（从数据库查找 ID）、<char_name>

（创意叙述内容，1-3 段自然语言描写）

> **叙事意义**：（该事件在整体叙事中的作用）

### <next_event_id>: ...

## 建议新增关系

| 角色A | 角色B | 关系类型 | 详情 | 时间 | 理由 |
|-------|-------|---------|------|------|------|
| <char_name> | <char_name> | 关系类型 | 详情 | 时间 | 基于哪些共享事件推断 |

## 建议新增信息

| ID | 标题 | 内容 | 知识层 | 关联实体 | 理由 |
|----|------|------|--------|---------|------|
| <info_snowflake_id> | 标题 | 内容 | 2 | <entity_name> | 理由 |

## 引用依据
（关联已有图实体的 snowflake ID 因果/时序/角色弧引用）
```

**引用已有实体**时，通过名称从数据库查找 ID：
```cypher
MATCH (c:Character) WHERE c.name='角色名' RETURN c.id AS id
MATCH (s:Scene) WHERE s.name='场景名' RETURN s.id AS id
```

### Step 4: 通知用户

向用户报告：
- 生成了几个草案文件
- 每个草案的主题和优先级
- 提示用户可以在 Dashboard 或直接编辑 .md 文件审核

---

## 模式三：apply（导入 Neo4j）

### 前提

草案必须经过用户审核并批准（status = approved）。

### Step 1: 通过脚本导入

```bash
python $SCRIPT apply --draft 01_叙事数据/drafts/draft_<snowflake_id>.md --password 12345678
```

脚本会：
1. 解析草案 .md 中的 YAML frontmatter（验证 status = approved）
2. 提取"建议新增事件/关系/信息"中的结构化数据
3. 生成 Cypher MERGE 语句（使用正确的英文标签和属性名）
4. 通过 Neo4jClient 事务执行
5. 更新草案 status 为 applied

### Step 2: 通过 neo4j-helper 手动执行（备选）

如果 apply 脚本无法正确解析复杂的草案格式，可以：
1. Claude 直接从草案中提取实体
2. 调用 `/neo4j-helper` skill 执行 Cypher

```bash
python $NEO4J_HELPER/execute_cypher.py --multi --password 12345678 <<EOF
MERGE (e:Event {id: '<snowflake_id>'}) SET e.title = '...', e.time = 'Day 20', e.type = '行动';
MATCH (c:Character {id: '<char_id>'}), (e:Event {id: '<snowflake_id>'})
MERGE (c)-[:involved {role: '当事人'}]->(e);
EOF
```

### Step 3: 报告

报告导入了哪些节点（名称 + snowflake ID）和哪些边（类型 + 方向）。

---

## ID 分配规则

所有节点 ID 使用雪花算法 Base62 编码（如 `Nv93TkkkgC`），全局唯一，无前缀。

生成命令：
```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py" -n 1 -q
```

引用已有实体时，通过名称从数据库查找（不依赖 CSV）：
```cypher
MATCH (c:Character) WHERE c.name='角色名' RETURN c.id AS id
MATCH (e:Event) WHERE e.title='事件标题' RETURN e.id AS id
MATCH (s:Scene) WHERE s.name='场景名' RETURN s.id AS id
MATCH (i:Info) WHERE i.title='信息标题' RETURN i.id AS id
```

---

## 草案管理命令

```bash
# 列出所有草案
python $SCRIPT list-drafts

# 更新草案状态（Dashboard 也会调用）
python $SCRIPT update-draft --draft <path> --status approved
python $SCRIPT update-draft --draft <path> --status rejected
```

---

## 错误处理

- **连接失败**：提示"请先启动 Neo4j 服务"
- **草案状态错误**：apply 时 status 非 approved，提示先审核
- **ID 冲突**：MERGE 幂等处理，已存在则更新
- **解析失败**：apply 无法提取实体时，建议使用 neo4j-helper 手动导入
- **Cypher 执行失败**：回滚整个事务，报告错误 Cypher
