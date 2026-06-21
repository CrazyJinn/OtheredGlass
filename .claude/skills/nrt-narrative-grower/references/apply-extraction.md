# apply 提取规则

> apply 阶段从已批准草案的 **MD 正文**（`02_剧情数据/<日期_概述>.md`）提取基础节点 + 边，写回叙事基础层。
> **提取规则直接复用** [nrt-narrative-extractor/references/csv-patterns.md](../../nrt-narrative-extractor/references/csv-patterns.md)（4 节点 + 6 边的列定义与内联 MERGE 模板）。本文件只说明 apply 相对 extractor 的**特化点**。

## 与 extractor 的差异

extractor 的输入是外部创作文本，输出是 `import.cypher` 文件（离线）；apply 的输入是**已批准草案 `02_剧情数据/<日期_概述>.md` 的正文**，输出是**直接写库**的 Cypher。提取规则（哪些是节点、哪些是边、属性怎么填）完全一致，差异在：

1. **已有实体按名复用**：草案 MD 正文中提到的、图中**已存在**的实体，按名称 `MATCH` 查 id 复用，**不新建**（避免重复）。仅草案新增的实体才分配新 id。
2. **新增实体用 snowflake**：`python ${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py -n <数量> -q` 批量分配。
3. **边端点先解析为 id**：所有边的两个端点先解析成 id（已有 or 新建），再生成 MERGE 边语句。
4. **原子写入 + frontmatter 回写**：节点/边合并为 `;` 分隔串，`cypher_exec.py --stdin --multi --json` 单事务执行；成功后**用 Edit 工具回写 MD 文件的 frontmatter**（applied_at / applied_node_ids），而非写图节点（与 extractor import.cypher 同模式，**零 LOAD CSV，不含 `//` 注释**）。

## 提取流程

### Step 0：定位并校验 MD 草案

传入参数为文件名 stem（`日期_概述`，支持部分匹配）。用 Glob 工具在 `02_剧情数据/` 下匹配 `*<draft_id>*.md` 定位唯一文件，再 Read 读取，校验 frontmatter：

- `status == 11` 且 `applied_at == null` → 继续。
- 否则（未批准 / 已驳回 / 已应用）→ 停止并提示。
- Glob 命中 0 个或多个 → 停止并提示用户补全文件名。

### Step 1：扫描草案正文，区分已有 vs 新增实体

对草案 **MD 正文**中提到的每个实体（角色/事件/地点/信息），按名称查库判断是否已存在：

```cypher
// 角色
MATCH (c:Character) WHERE c.name IN $names RETURN c.name AS name, c.id AS id
// 事件（按 title）
MATCH (e:Event) WHERE e.title IN $titles RETURN e.title AS title, e.id AS id
// 地点
MATCH (l:Location) WHERE l.name IN $names RETURN l.name AS name, l.id AS id
```

- 命中 → 复用其 id。
- 未命中 → 标记为新增，分配 snowflake id。

> 注意：cypher_exec.py CLI 下用内联值（不用 `$names` 参数，Shell 会解析 `$`）。把名字直接写进 `IN [...]` 列表，或分多次查询。

### Step 2：生成节点 MERGE（仅新增实体）

按 [csv-patterns.md](../../nrt-narrative-extractor/references/csv-patterns.md) 的节点模板，为新增实体生成：

```cypher
MERGE (n:Character {id: '<new_id>'}) SET n.name = '...', n.gender = '...', n.description = '...', n.character_tags = '...';
MERGE (n:Event {id: '<new_id>'}) SET n.title = '...', n.time = '...', n.type = '...', n.description = '...';
MERGE (n:Location {id: '<new_id>'}) SET n.name = '...', n.description = '...';
MERGE (n:Info {id: '<new_id>'}) SET n.title = '...', n.content = '...', n.knowledge_level = '...';
```

字段定义与必填项严格按叙事基础.md / csv-patterns.md。字符串用单引号，内容中的 `'` 转义为 `\'`。

### Step 3：生成边 MERGE

按 csv-patterns.md 的 6 种边模板，端点用 Step 1/2 解析出的 id：

```cypher
MATCH (a:Character {id:'<id_a>'}), (b:Character {id:'<id_b>'})
MERGE (a)-[:relation {type:'...', detail:'...'}]->(b);
MATCH (c:Character {id:'<id_c>'}), (e:Event {id:'<id_e>'})
MERGE (c)-[:involved {role:'...', detail:'...'}]->(e);
MATCH (e:Event {id:'<id_e>'}), (l:Location {id:'<id_l>'})
MERGE (e)-[:occurred_at]->(l);
-- 其余边类型见 csv-patterns.md
```

### Step 4：原子执行 + 回写 MD frontmatter

把所有节点语句（Step 2）+ 边语句（Step 3）合并为 `;` 分隔串，单事务执行：

```bash
cat <<'EOF' | python ${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py --stdin --multi --json
MERGE (n:Character {id: '...'}) SET ...;
MATCH ... MERGE ...;
...
EOF
```

成功后记录写入的节点 id 列表，**用 Edit 工具回写 `02_剧情数据/<draft_id>.md` 的 frontmatter**：

```yaml
applied_at: '<TIMESTAMP>'
applied_node_ids: '<id1;id2;...>'
```

## 幂等与安全

- 全程 `MERGE`：重复 apply 不产生重复节点/边。
- apply 开头（Step 0）校验 frontmatter `status==11 AND applied_at==null`；已应用的草案拒绝二次 apply。
- 单事务（`--multi`）：任一语句失败则整体回滚，不会出现"写了一半"。frontmatter 回写是事务成功后的独立步骤（编辑 MD 文件）——若它失败而基础节点已写，下次 apply 会因 MERGE 幂等 + frontmatter `applied_at` 校验安全重试。
