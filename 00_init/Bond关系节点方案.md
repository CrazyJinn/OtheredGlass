# 把「人物关系」提升为 Bond 节点

> ⚠️ **本方案已废弃**：方向调整为 galgame「选择分叉」建模（Choice 节点），而非「人物关系」。
> 新方案见 [Schema/剧情.md](Schema/剧情.md) 的 **Choice 选择点**：`Event -[presents]-> Choice -[option]-> Event`。
> 本文档仅作思路演变存档，**未执行**，不代表当前 schema。

## Context（为什么做）

当前人物关系是 **5 条直连边** `Character -[relation]-> Character`，属性单薄（只有 `type`/`detail`，仅 1 条带 `start_time`），存在两个硬伤：

1. **挂不了事件**——关系演变（告白/确立/分手/3选1的选择）无法落到图上。
2. **表达不了分支**——「男主 × 3 个女主 3 选 1」这种互斥分支关系无处安放。

目标：把 `relation` 这条边**实体化为节点 `Bond`（羁绊）**，承载属性 + 生命周期 + 关联事件，原生支持分支。已与用户确认的决策：

- 新节点标签 = **Bond**
- 现有 5 条 relation 边 → **迁移成 Bond 后删除原边**
- Bond 加 **state（潜在/进行/结束）+ branch（分支标识）** 属性

---

## 一、数据模型变更

### 1. 新增节点：Bond（羁绊）

> 最小粒度：两个或多个角色之间的一段关系。同一对角色可有多段（既是同事又是前任 → 多个 Bond）。

| 字段 | 中文 | 类型 | 必填 | 说明 / 示例 |
|------|------|------|------|------|
| id | 编号 | string | 是 | snowflake Base62 |
| name | 名称 | string | 否 | 分支线建议命名，如 `陆择×女A 恋爱线`；普通关系可留空 |
| type | 关系类型 | string | 是 | `恋爱` / `同事` / `前任` / `客户` / `招募` / `一夜情` |
| detail | 详情 | string | 否 | `队长与经理` / `已分手` |
| start_time | 开始时间 | Date | 否 | 关系建立时间 |
| end_time | 结束时间 | Date | 否 | 关系结束时间（空=持续中） |
| state | 状态 | enum | 否 | `潜在` / `进行` / `结束` |
| branch | 分支标识 | string | 否 | `A` / `B` / `C`；非分支关系留空 |

**state 枚举**：`潜在`=未成立/候选项（3选1 待选）｜`进行`=当前有效｜`结束`=曾成立后终止。三者正交，**不引入第 4 个「落选」值**——落选分支保持 `潜在`，由 milestone 事件标记「未被选中」。

**branch**：开放字符串（非枚举），同 branch 组内的多个 Bond 为「N 选 1」语义，支持多组并行分支。

### 2. 边替换：删除 `relation`，新增 `party` + `milestone`

**`party` — 角色参与羁绊 `N:N`，方向 `Character → Bond`**

| 属性 | 中文 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| role | 角色 | string | 是 | 该角色在 Bond 中的定位：`追求者`/`被追求者`/`招募者`/`被招募者`/`客户`/`服务方`/`同事`/`前任`/`当事人` |
| detail | 详情 | string | 否 | |
| sync | 同步 | boolean | 否 | 默认 `false` |

> 方向论证：Bond 由角色构成，角色是源头（上游）、Bond 是组合产物（下游），与 `involved`(Character→Event) 同构。原直连边 `a→b` 的「发起方/承受方」方向语义，改由 `party.role` 表达（对等关系两端 role 相同）。

**`milestone` — 羁绊关联事件 `N:N`，方向 `Bond → Event`**

| 属性 | 中文 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| role | 意义 | string | 是 | 该事件在 Bond 演变中的意义：`确立`/`告白`/`危机`/`分手`/`选择`/`复合` |
| detail | 详情 | string | 否 | |
| sync | 同步 | boolean | 否 | 默认 `false` |

> 方向论证：Bond 是因/源头，里程碑事件是关系结出的果（下游），与 `evt_relation`(前因→后果) 一致。**与 evt_relation 不重叠**：evt_relation 管「事件↔事件」的因果时序，milestone 管「关系→其里程碑事件」，两者正交协作。

**3选1 落地**：陆择×女A / B / C 各为一个 Bond（state=潜在, branch=A/B/C），各自 `milestone` 关联「选择A/B/C交往」事件；玩家选 A → A 的 Bond state→进行，B/C 保持潜在。`sync` 均为 `false`（对齐叙事基础层约定）。**不新增 Event.type 枚举**——「选择」是关系维度语义，归 `milestone.role`，Event.type 保持客观性质。

### 3. 方向验证表更新（叙事基础.md 末尾）

| from | 允许的边 | to |
|------|---------|-----|
| Character | **party**, at, involved, link | **Bond** / Location / Event / Info |
| **Bond** | **milestone** | Event |
| Event | occurred_at, evt_relation, link | Location / Event / Info |
| Location | link, has_scene | Info / Scene |
| Info | link | Info |

---

## 二、迁移：5 条 relation 边 → Bond

**迁移数据（端点用 name 匹配，属性来自实测）**：

| # | from | to | type | detail | start_time | 推断 state | from.role | to.role |
|---|------|-----|------|--------|-----------|-----------|-----------|---------|
| 1 | 顾盈 | 陆择 | 一夜情 | 陆择与顾盈的一夜情 | — | 结束 | 当事人 | 当事人 |
| 2 | 温蔓青 | 陈默 | 前任 | 已分手 | — | 结束 | 前任 | 前任 |
| 3 | 林梦 | 陈默 | 客户 | 代练客户兼小迷妹 | — | 进行 | 客户 | 服务方 |
| 4 | 沈暮雪 | 陈默 | 招募 | 经理招募选手 | Day 5 | 进行 | 招募者 | 被招募者 |
| 5 | 江烈 | 沈暮雪 | 同事 | 队长与经理 | — | 进行 | 同事 | 同事 |

> end_time 当前一律留空（原边未记录结束时间，不编造）；后续若有「分手事件」milestone，再从 Event.time 反推回填。

### 步骤

**① 生成 5 个 Bond.id**
```bash
python .claude/scripts/snowflake_base62.py -n 5 -q
```

**② 写迁移文件** `00_init/migration/relation_to_bond.cypher`（实施时新建目录），把上一步的 5 个 id 填入 `<B1>`…`<B5>` 占位符。**端点用 `name` 匹配**（健壮），Bond 用 `MERGE {id}` 幂等：

```cypher
// ===== Bond 节点 =====
MERGE (b1:Bond {id:'<B1>'}) SET b1.type='一夜情', b1.detail='陆择与顾盈的一夜情', b1.state='结束', b1.branch='';
MERGE (b2:Bond {id:'<B2>'}) SET b2.type='前任', b2.detail='已分手', b2.state='结束', b2.branch='';
MERGE (b3:Bond {id:'<B3>'}) SET b3.type='客户', b3.detail='代练客户兼小迷妹', b3.state='进行', b3.branch='';
MERGE (b4:Bond {id:'<B4>'}) SET b4.type='招募', b4.detail='经理招募选手', b4.start_time='Day 5', b4.state='进行', b4.branch='';
MERGE (b5:Bond {id:'<B5>'}) SET b5.type='同事', b5.detail='队长与经理', b5.state='进行', b5.branch='';
// ===== party 边（角色用 name 匹配，方向 Character→Bond）=====
MATCH (c1:Character {name:'顾盈'}),    (c2:Character {name:'陆择'}),   (x1:Bond {id:'<B1>'})
MERGE (c1)-[:party {role:'当事人',  sync:false}]->(x1)
MERGE (c2)-[:party {role:'当事人',  sync:false}]->(x1);
MATCH (c1:Character {name:'温蔓青'}),  (c2:Character {name:'陈默'}),   (x2:Bond {id:'<B2>'})
MERGE (c1)-[:party {role:'前任',    sync:false}]->(x2)
MERGE (c2)-[:party {role:'前任',    sync:false}]->(x2);
MATCH (c1:Character {name:'林梦'}),    (c2:Character {name:'陈默'}),   (x3:Bond {id:'<B3>'})
MERGE (c1)-[:party {role:'客户',    sync:false}]->(x3)
MERGE (c2)-[:party {role:'服务方',  sync:false}]->(x3);
MATCH (c1:Character {name:'沈暮雪'}),  (c2:Character {name:'陈默'}),   (x4:Bond {id:'<B4>'})
MERGE (c1)-[:party {role:'招募者',  sync:false}]->(x4)
MERGE (c2)-[:party {role:'被招募者',sync:false}]->(x4);
MATCH (c1:Character {name:'江烈'}),    (c2:Character {name:'沈暮雪'}), (x5:Bond {id:'<B5>'})
MERGE (c1)-[:party {role:'同事',    sync:false}]->(x5)
MERGE (c2)-[:party {role:'同事',    sync:false}]->(x5);
```

**③ 执行 A（建 Bond + party）**，单事务、幂等可重跑：
```bash
python .claude/scripts/cypher_exec.py -f 00_init/migration/relation_to_bond.cypher --multi --json
```

**④ 验证**（见第四节）确认 Bond=5、party=10 后，再执行 **⑤ 删原边**：
```bash
python .claude/scripts/cypher_exec.py -c "MATCH ()-[r:relation]->() DELETE r" --json
```
> 分两步：A 失败时 relation 边仍在，可回滚；DELETE 重跑无匹配即无副作用。

**幂等性**：Bond `MERGE {id}`、party `MERGE 端点` 均幂等；契约是 5 个 id 字面量——归档进 `relation_to_bond.cypher` 不再改动，重跑安全。

---

## 三、文档改动

### `00_init/Schema/叙事基础.md`
- **节点**：在「事件」后新增「### 羁绊（Bond）」小节（用上面第一节的属性表 + state/branch 枚举）。
- **边**：把「### relation — 人物关系」整段**替换**为「### party — 角色参与羁绊」+「### milestone — 羁绊关联事件」两个小节（含方向论证）。原「关系演变建多条 relation 边」的提示改写移到 Bond 小节：「关系演变由多个 Bond 或 Bond→Event 的 milestone 表达」。
- **方向验证表**：按第一节第 3 点更新（Character 行 `relation`→`party`、新增 Bond 行）。
- **ID 规则**：引用模板追加 `MATCH (b:Bond) WHERE b.name='羁绊名称' RETURN b.id AS id`。

### `00_init/Schema总览.md`
- **全节点速查表**（Info 行后）加：`| Bond | snowflake Base62 | 两个或多个角色之间的一段关系（含分支） |`
- **全局边速查表**：删 `relation` 行，加 `party`(Character→Bond, N:N, ❌) 和 `milestone`(Bond→Event, N:N, ❌) 两行。
- **mermaid 结构图**：叙事基础 subgraph 内加 `Bond["Bond"]`，加 `Character -->|"party ❌ N:N"| Bond` 和 `Bond -->|"milestone ❌ N:N"| Event`。

---

## 四、验证（end-to-end）

迁移后依次跑（全部只读）：
```cypher
MATCH (b:Bond) RETURN count(b) AS bond_count;              -- 期望 5
MATCH ()-[r:party]->() RETURN count(r) AS party_count;     -- 期望 10
MATCH ()-[r:relation]->() RETURN count(r) AS relation_count; -- 期望 0（删边后）
-- 全量核对
MATCH (a:Character)-[:party]->(b:Bond)<-[:party]-(c:Character)
WHERE a.name < c.name
RETURN b.type AS type, b.state AS state, a.name AS 角色1, c.name AS 角色2
ORDER BY b.type;
```

业务查询样例（确认新模型可用）：
```cypher
-- 陆择当前进行中的恋爱线
MATCH (:Character {name:'陆择'})-[:party]->(b:Bond)<-[:party]-(o:Character)
WHERE b.state='进行' AND b.type CONTAINS '恋爱' RETURN b.name, o.name, b.branch;
-- 某 Bond 关联的事件（按时间）
MATCH (b:Bond {id:'<id>'})-[m:milestone]->(e:Event)
RETURN e.time, e.title, m.role ORDER BY e.time;
```

---

## 五、关键文件

- `00_init/Schema/叙事基础.md` — 新增 Bond 节点、替换 relation 为 party/milestone、更新方向验证表
- `00_init/Schema总览.md` — 节点/边速查表 + mermaid 结构图
- `00_init/migration/relation_to_bond.cypher` — **新建**，归档迁移脚本（固化 5 个 Bond.id 作为幂等契约）
- `.claude/scripts/snowflake_base62.py` — 生成 Bond.id
- `.claude/scripts/cypher_exec.py` — 执行迁移与验证

## 六、边界与风险

- **历史关系**（前任/一夜情）→ state=结束，自洽；end_time 留空（不编造）。
- **同对角色多 Bond**（同事+前任）：天然支持，按 Bond.type/state/id 区分，无需去重。
- **3选1 落选**：B/C 保持 state=潜在，由 milestone(role=选择) 标记，不新增枚举。
- **不碰 evt_relation**：事件因果时序仍归 evt_relation；milestone 只管「关系→里程碑事件」。
- **风险**：迁移 id 字面量不可被外部改动（否则重跑会建重复 Bond）→ 靠归档脚本固化。
