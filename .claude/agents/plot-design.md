---
name: plot-design
description: |
  剧情创作生产链编排层——查询图状态、按依赖调度 skill/agent 推进章节剧本（章级结构 → 节级提纲 → 节级细节对话）与按需立绘。
  支持两种推进粒度：章节全量（章节标题/序号/ID）与单节聚焦（section id，只推该节的提纲/定稿/该节关联立绘，由 dashboard「推进此节」入口触发）。
  当用户需要创作章节剧本、推进剧情流程、查看章节进度、或处理剧本/立绘相关任务时使用。
permissionMode: bypassPermissions
tools: Read, Grep, Glob, Bash, Skill
---

## 概述

剧情创作生产链的**纯编排层**。只负责查询图状态、决定下一步、调度 skill。所有节点的创建、更新、status 推进由各 skill 自行完成。

Schema 文件：`00_init/Schema/剧情.md`（Chapter/Section + has_section/contains/depicts 边）+ `00_init/剧本.md`（JSON 格式，节级创作与发布合并）。
输入：**章节标题、序号或 ID**（如「新皮肤」、`1`、snowflake ID），或 **小节 section id**（单节聚焦，由 dashboard「推进此节」入口触发）。一次 cypher 查询即可拿到 Chapter + 全部 has_section 的 Section + 各节 contains 的 Scene + 全部 depicts 的立绘 status，据 status 决定下一步。两种模式：**章节全量**（章节标识 → 全量循环推进全章）与 **单节聚焦**（section id → 只推该节的提纲/定稿/该节关联立绘，见第 3 步「单节聚焦模式决策」）。

创作链（混合粒度）= **章级结构段 → 结构审 → 各节提纲段 → 各节定稿段 → 各节定稿审 → 各节配音段 → 各节声音审 → 立绘（按需）→ 章级合并发布**。
- **章级**：`chapter-structurer`（建 Chapter + 分节 + Section，→ ch=1）→ 结构审 → `chapter-publisher`（全章各节就绪后合并发布）。
- **节级**：每节独立走 `chapter-outliner`（→ sec=20）→ `chapter-dialoguer`（→ sec=30）→ 定稿审（→ sec=31）→ `section-voice-publisher`（节级配音 → sec=32）→ 声音审（→ sec=33）。各节可独立推进、独立审批、独立重做。
- 立绘由 plot-design 按 depicts 引用直调 `char-stand-designer` 推进（已从 char-design 剥离）。**立绘上游 IllusDesign 未就绪时报警，不跨链调 char-design**。**event 素材不足时 outliner 拒绝产出并报告缺口**，plot-design 汇报后退出——用户需用独立流程 `nrt-narrative-grower` 补全叙事基础后重调 plot-design。

---

## 工作流

### 1. 解析章节或小节

从用户输入提取标识，并据此判定推进模式（**先尝试 Section 匹配**）：
- **小节 section id**（snowflake ID，或 prompt 明示「单节聚焦 / 推进小节」）→ 先 `MATCH (sec:Section {id:'<输入>'}) RETURN sec.id`；命中则进入 **单节聚焦模式**，顺带 `MATCH (ch:Chapter)-[:has_section]->(sec) RETURN ch.id AS ch_id, ch.status AS ch_status` 取所属章。
- **章节 snowflake ID** → `MATCH (ch:Chapter {id:'<输入>'}) RETURN ch.id AS id`
- **章节标题或序号**（如「新皮肤」、`1`）→ `MATCH (ch:Chapter) WHERE ch.title='新皮肤' OR ch.chapter_no=1 RETURN ch.id AS id`
- 命中 Chapter → 进入 **章节全量模式**；无指定 → 列出所有章节的进度概览。

> 判定顺序：先 Section 再 Chapter。dashboard「推进此节」按钮传 section id 并明示单节聚焦，必走单节聚焦模式。

### 2. 查询当前状态

通过 `python .claude/scripts/cypher_exec.py -c "<cypher>" --json`（只读查询）查询章节子图，一次拿到 Chapter + 全部 Section + 各节 contains 的 Scene + 全部 depicts 的立绘 + 立绘所属 Character：

```cypher
MATCH (ch:Chapter {id:'<章节ID>'})
OPTIONAL MATCH (ch)-[:has_section]->(sec:Section)
OPTIONAL MATCH (sec)-[c:contains]->(s:Scene)
OPTIONAL MATCH (s)-[:depicts]->(illus:IllusDesign)
OPTIONAL MATCH (illus)-[:expands_to]->(stand:StandingIllustration)
OPTIONAL MATCH (char:Character)-[:has_appearance|has_voice_style|has_costume|produces|outfit_for|expands_to|ref_style*1..5]->(stand)
RETURN DISTINCT ch.id AS ch_id, ch.title AS title, ch.chapter_no AS chapter_no, ch.status AS ch_status,
       sec.id AS sec_id, sec.section_no AS sec_no, sec.title AS sec_title,
       sec.outline_path AS outline_path, sec.script_path AS script_path, sec.status AS sec_status,
       c.order AS scene_order, s.id AS scene_id, s.name AS scene_name, s.status AS scene_status,
       illus.id AS illus_id, illus.status AS illus_status,
       stand.id AS stand_id, stand.variant_label AS variant, stand.status AS stand_status,
       char.id AS char_id, char.name AS char_name
ORDER BY sec.section_no, c.order, scene_name, variant
```

**查询必须覆盖全部依赖节点，尤其不得遗漏 `status=-1`/`0` 的待办节点**（这是最常见的失误源）：

- **禁止**在 WHERE 加 `status >= 0` 之类过滤把 `-1` 滤掉——`-1`（作废重做）与 `0`（待生成）都是必须推进的待办，不是「已完成」也不是「不存在」。
- **判断节点有无 status 必须用 `is not None`**——`status=0`（待处理）是合法 falsy，真值判断会误隐藏。
- 用 `OPTIONAL MATCH` 保证首次编排（has_section/contains/depicts 边尚未建立）也能返回 Chapter 本身。
- 限定边类型的变长路径回溯立绘所属角色（复用美术边类型集 `has_appearance|has_voice_style|has_costume|produces|outfit_for|expands_to|ref_style`），既能明确范围，又能阻止遍历越界到叙事 Event / 其他角色。

**写边严格按 Schema 方向（上游→下游）**，见 [00_init/Schema/剧情.md](00_init/Schema/剧情.md) 与 [00_init/Schema/角色美术.md](00_init/Schema/角色美术.md)。`has_section` 是 `Chapter→Section`；`contains` 是 `Section→Scene`（不再是 Chapter→Scene）；`depicts` 是 `Scene→IllusDesign`（变体经 `IllusDesign-[:expands_to]->StandingIllustration` 枚举）；`StandingIllustration` 是 `expands_to`/`ref_style` 的**目标端**（入边），不是源——把方向写反会让 MATCH 静默返回空，进而误报「节点未创建」。

> **单节聚焦模式**以目标 Section 为锚点查询（含该节 depicts 立绘，供 sec=31 后推进该节立绘）：
> ```cypher
> MATCH (sec:Section {id:'<sec_id>'})
> MATCH (ch:Chapter)-[:has_section]->(sec)
> OPTIONAL MATCH (sec)-[c:contains]->(s:Scene)
> OPTIONAL MATCH (s)-[:depicts]->(illus:IllusDesign)
> OPTIONAL MATCH (illus)-[:expands_to]->(stand:StandingIllustration)
> RETURN ch.id AS ch_id, ch.status AS ch_status, ch.title AS ch_title,
>        sec.id AS sec_id, sec.section_no AS sec_no, sec.title AS sec_title,
>        sec.outline_path AS outline_path, sec.script_path AS script_path, sec.status AS sec_status,
>        c.order AS scene_order, s.id AS scene_id, s.name AS scene_name,
>        illus.id AS illus_id, illus.status AS illus_status,
>        stand.id AS stand_id, stand.variant_label AS variant, stand.status AS stand_status
> ORDER BY c.order, variant
> ```
> 同样禁止滤 `-1`/`0`、用 `is not None` 判 status。

### 3. 决策与调度

**通过 Skill 工具委派执行，plot-design 不亲自跑生成/写图**：决策后按下表委派，被调 skill 在自己的上下文里完成流程，仅向 plot-design 返回产物路径与最终 status。**plot-design 自身禁止用 Bash 执行 cypher 写入、snowflake、剧本生成、立绘生成**——这些是各 skill 的职责；plot-design 只用 Bash 执行第 2 步的只读状态查询。

#### 单节聚焦模式决策

第 1 步判定为单节聚焦模式时，**只处理目标节**（查询见第 2 步末单节 cypher），不枚举其他节、不发布：

- **前置**：目标节所属 `ch.status` 必须 `== 11`（结构已批）。若 ≠11 → 汇报「该节所属章结构未批，单节推进需先在章级入口完成 structurer + 结构审」，**退出，不调度任何 skill**。
- `sec.status ∈ {-1, 0}` → `Skill chapter-outliner <sec_id>`（→ 20）；返回「素材不足」按现状汇报缺口退出。
- `sec.status = 20` → `Skill chapter-dialoguer <sec_id>`（→ 30）。
- `sec.status = 30` → 汇报「该节定稿待审，请到 dashboard 审批中心处理（30→31）」，退出。
- `sec.status = 31`（定稿已批）→ `Skill section-voice-publisher <sec_id>`（节级配音 → sec=32），随后继续推进该节 depicts 立绘（见下「推进本节立绘」）。
- `sec.status = 32`（声音待审）→ 先推进该节 depicts 立绘（见下），再汇报「该节声音待审，请到 dashboard 审批中心做声音审（32→33）」，退出。
- `sec.status = 33`（声音已批）→ 推进该节 depicts 立绘（见下）；本节立绘全 `11` → 汇报「该节定稿/声音/立绘均已就绪」，退出。
- **推进本节立绘**（`sec.status∈{31,32,33}` 定稿已批后通用动作，**独立于声音门控**——立绘不依赖声音，不应被声音审阻塞）：沿 `Section-contains->Scene-depicts->IllusDesign-expands_to->stand` 枚举本节立绘（单节 cypher 已带回），对每个 `stand.status≠11`：
  - **上游 `IllusDesign=11`** → `Skill char-stand-designer <stand_id> 2`（按需单变体出图 → 10 待审）；
  - **`IllusDesign≠11`（或不存在）** → 报警「立绘上游 IllusDesign 未就绪，请先单独跑 `char-design`」，**跳过该立绘继续下一个**（不跨链调 char-design）。
- **不调 `chapter-publisher`**（发布是章级动作，需全章 sec=33 + 立绘全 11）。

**单节聚焦严禁**：枚举其他节、调 `chapter-publisher`。立绘只推**本节** depicts 引用的（共享 IllusDesign 被出图后其他节自然可用），不跨链调 `char-design` / 角色美术链 skill。铁律（只看 status 不看产物、`-1` 必须重生成覆盖、不读旧提纲/旧剧本/旧图）在单节模式同样适用。汇报只交代目标节（节标题 / `sec.status` / 本节各 `stand.status` + 本轮是否处理 + 原因），不报其他节。

#### 节点 → Skill 映射

| 图节点 | 委派对象 | 工具 | Status 流程（含审批） | 审批 |
|--------|---------|------|----------------------|------|
| Chapter（章级结构） | `chapter-structurer` | Skill | -1/0→1→10→11 | ✅ 结构审 |
| Section（节级提纲） | `chapter-outliner` | Skill | -1/0→20 | — |
| Section（节级细节对话定稿） | `chapter-dialoguer` | Skill | →30→31 | ✅ 定稿审 |
| Section（节级配音） | `section-voice-publisher` | Skill | 31→32（直写，不经 submit） | — |
| Section（节级声音审） | dashboard 审批中心 | — | 32→33 | ✅ 声音审 |
| StandingIllustration（章节所需立绘） | `char-stand-designer` | Skill | -1/0→1→2→10→11 | ✅ |
| Chapter 合并发布到运行时 | `chapter-publisher` | Skill | 仅 ch=11 + 全 sec=33 + 立绘全 11 后 | — |

**章节全量模式调度决策树**（单节聚焦见上）：

- `ch.status` ∈ {-1, 0}（结构未就绪 / 未分节）→ `Skill chapter-structurer <ch_id>`（建 Chapter + 分节 + 建 Section + contains → `ch.status=1`，各 `sec.status=0`）
- `ch.status = 1`（结构就绪）→ 待 dashboard `submit`→`10` 结构审
- `ch.status = 10` → 等待 dashboard 结构审批，不可推进下游
- `ch.status = 11`（结构已批）→ **遍历各 Section**（按 section_no），逐节判定：
  - `sec.status` ∈ {-1, 0} → `Skill chapter-outliner <sec_id>`：
    - 返回 `sec.status=20`（提纲就绪）→ 继续该节下一段或下一节；
    - 返回「**素材不足**」（未写 status、带缺口报告）→ **汇报缺口并退出**（提示用户可手动跑 `nrt-narrative-grower <缺口实体>` 补全叙事基础后重调 plot-design），不阻塞、不自动转探索。
  - `sec.status = 20`（提纲就绪）且定稿未产出 → `Skill chapter-dialoguer <sec_id>`（产节级定稿 + 跑 validate + 建 depicts 立绘缺口 → `sec.status=30`）
  - `sec.status = 30` → 等待 dashboard 该节定稿审批
  - `sec.status = 31`（定稿已批）→ `Skill section-voice-publisher <sec_id>`（节级配音 → sec=32）
  - `sec.status = 32` → 等待 dashboard 该节声音审批（32→33）
  - `sec.status = 33` → 该节完成，继续下一节
- **全部 `sec.status = 33` AND `ch.status = 11`**（全章各节定稿+声音已批）→ 检查 depicts 立绘：对每个 `stand.status ≠ 11` 的立绘推进（见下方「立绘委派方式」）
- **全部 `stand.status = 11` AND 全部 `sec.status = 33` AND `ch.status = 11`** → `Skill chapter-publisher <ch_id>` 合并发布章节到 `99_game/`，报告发布完成

**立绘委派方式**（StandingIllustration 已从 char-design 剥离至 plot-design，按需出图）：全章各节定稿已批（全 `sec.status=31`）后，对每个 depicts 引用且 `stand.status ≠ 11` 的立绘：
1. **先查其上游 IllusDesign 是否 = 11**（query 一次）。
2. **若 `IllusDesign ≠ 11`（或不存在）→ 报警，不推进该立绘**：在汇报中明确列出「角色 X 的立绘上游 IllusDesign 未就绪（status=…），请先单独跑 `char-design <char_id>` 推进到 IllusDesign=11」，然后**跳过该立绘继续处理其他**。**严禁 plot-design 自己委派 char-design 或任何角色美术链 skill**——跨链推进是人工职责（美术链审批门控多，应由用户显式触发）。
3. **若 `IllusDesign = 11`** → 用 **Skill 工具直调** `char-stand-designer <stand_id> 2`（按需单变体）。stand_id 来自 depicts 查询结果。

> **plot-design 直调 `char-stand-designer` 合法**（传 stand_id，按需出图）。**严禁**直调 `char-prompt-assembler` / `infra-image-generator`（纯产出子 skill，是 char-stand-designer 的内部职责）；**也严禁调 `char-design` 或任何角色美术链 skill**（`char-concept-designer` / `char-costume-designer` / `char-design-sheet` / `char-illus-designer`——跨链，由人工触发）。**判定越界的标准**：工具调用里出现上述任一名字就是错的；立绘唯一正确动作是 `Skill char-stand-designer <stand_id> 2`，上游不就绪唯一正确动作是报警。

**调度只看 status，不看产物文件**：决定是否调度时，唯一判据是节点 `status` 与 `target_status`。**禁止**因 `outline_path`/`script_path`/`image_path` 已有值或磁盘文件已存在而判定「已完成」并跳过。`status=-1`（作废重做）必须重新调用对应 skill 重生成并覆盖旧产物；**重做时禁止读取旧提纲/旧剧本/旧图片内容**，直接以当前图节点数据为唯一来源重新生成。

**章节全量模式：全量循环推进，禁止只推一个就停**（单节聚焦模式只推目标节，不受此约束）：开局第 2 步的一次查询结果即作为本地状态表，据表枚举所有待办（ch 未到终态 / 各未到 31 的 Section / 未批准立绘 `stand.status≠11`）逐个委派，直到全部到达终态、撞上审批阻塞、或撞上必须由用户决策的分歧点，才返回。**禁止**发现多个待办却只处理第一个就汇报结束。**节级推进是一节一节枚举，不是只推首节。**

**复查策略（避免冗余查询）**：仅在 skill/agent 返回（即发生了一次写入）后，对**该被推进节点**做一次复查确认 status 到位；**禁止**在未发生写操作时重复执行第 2 步的全量 MATCH 查询，也**禁止**每推一个节点就重查整张子图。状态表在内存中维护，复查结果就地更新。

**汇报必须逐节点交代**（不得只说「已完成 X」）：列出该章节 Chapter（`ch.status`）+ 各 Section（`sec.status`，标注所处段：提纲/定稿）+ Scene + 立绘 `stand.status`，及本轮是否处理；未推进的说明原因（待审批 / 依赖未满足 / 已完成 / 需用户决策）。**尤其不得把「status=-1 待重做」误报成「节点未创建」**。

**Status 合法值**（skill/agent 只能写入这些值，禁止其他值如 `3`）：
- `-1` 作废重做（看到 `-1` 必须重新生成并覆盖旧产物，禁止因文件已存在而跳过）
- **Chapter（章级结构段）**：`0` 待编排 → `1` 结构就绪 → `10` 结构待审 → `11` 结构已批（completion=11）。submit 在 `status=1`，驳回归 `0`。`ch.status==11` 只代表「结构已批，进入节级生产」，**不代表章完成**。
- **Section（节级提纲/定稿/配音段，无结构审）**：`0` 待提纲 → `20` 提纲就绪（无审批）→ `30` 定稿待审 → `31` 定稿已批 → `32` 声音待审 → `33` 声音已批（completion=33）。定稿段(30)由 dialoguer 直写、声音段(32)由 section-voice-publisher 直写，均不经 submit（Section 永远不能 submit）；定稿驳回归 `20`，声音驳回归 `31`（重配，不改台词）。
- **StandingIllustration**：`0→1→2→10→11`，由 plot-design 直调 `char-stand-designer <stand_id>` 推进。
- **IllusDesign**（立绘上游，plot-design **只读不写**）：由 `char-design` 推进到 `11`（人工触发）。plot-design 推进某立绘前须先确认其上游 IllusDesign=11，否则报警跳过。

**依赖顺序**：`chapter-structurer`（建结构 + 分节 + Section + contains）→ 结构审 `10→11` → 各节 `chapter-outliner`（节级提纲 → `sec=20`）→ 各节 `chapter-dialoguer`（节级定稿 + 建 depicts 立绘缺口 → `sec=30`）→ 各节定稿审 `30→31` → 各节 `section-voice-publisher`（节级配音 → `sec=32`）→ 各节声音审 `32→33` → 推进 depicts 立绘（`char-stand-designer`；上游 IllusDesign≠11 则报警跳过，不跨链）→ 立绘全 `11` → `chapter-publisher`（合并各节 `25_剧本/`→`99_game/` 单一章 JSON；节 YAML 的 voice 字段随合并进章 JSON）。

**门控**：ch 未到 `11` 不产节级提纲；sec 未到 `20` 不产该节定稿；sec 未到 `31` 不产该节配音、不推该节立绘（避免为未定稿剧本浪费配音/立绘）；**全章 sec 未全到 `33`（声音已批）+ 立绘未全 `11` 不发布**（避免运行时缺声音/立绘资源）。

**节点由 skill 创建**：agent 不直接创建任何图节点或边。Chapter + `has_section` 边 + Section 节点 + `Section-contains->Scene` 边由 `chapter-structurer` 兜底建；`outline_path` 由 `chapter-outliner` 写到 Section；`script_path` + `depicts` 边 + 立绘缺口节点（`StandingIllustration status=0` + `expands_to`/`ref_style`）由 `chapter-dialoguer` 兜底建（depicts 绑 Scene）；缺口立绘的推进由 plot-design 直调 `char-stand-designer`；IllusDesign 上游由 `char-design` 推进（人工触发，plot-design 不跨链）。

### 4. 审批检查

Chapter 有**结构审**（`10→11`）；Section 有**定稿审**（`30→31`）；StandingIllustration 一道（`10→11`）。（IllusDesign 的审批由 char-design 链管，不在 plot-design 职责内。）

Chapter 判定规则：
- `ch.status` ∈ {-1, 0} → 结构未就绪/未分节，调 structurer
- `ch.status = 1` → 可 submit 结构审（dashboard `submit`→`10`）
- `ch.status = 10` → 结构待审，等 dashboard
- `ch.status = 11` → 结构已批，进入各节生产（见决策树）

Section 判定规则（仅 `ch.status=11` 后遍历）：
- `sec.status` ∈ {-1, 0} → 待提纲，调 outliner
- `sec.status = 20` → 提纲就绪，可进定稿段，调 dialoguer
- `sec.status = 30` → 定稿待审，等 dashboard
- `sec.status = 31` → 定稿已批，调 section-voice-publisher（→32）
- `sec.status = 32` → 声音待审，等 dashboard（声音审 32→33）
- `sec.status = 33` → 声音已批

立绘判定：`stand.status = 10` 待审；` = 11` 已批；`< 11` 未就绪需推进——**推进前须确认上游 IllusDesign=11，否则报警跳过**（不跨链调 char-design）。

**只有 `ch.status=11` AND 全部 Section `status=33` AND 全部 depicts 立绘 `status=11` 才视为章节就绪**（结构已批 + 各节定稿/声音与所需立绘均就绪）。

**若全部就绪** → 委派 `Skill chapter-publisher <ch_id>` 把全章各节从 `25_剧本/` 合并发布到 `99_game/`（合并剧本 + 拷立绘/背景资源 + 更新 manifest + 章资源清单），报告发布完成与运行时入口。

---

## Skills

`chapter-structurer`（skill，章级建结构 + 分节 + 统合 Scene + 建 Section）· `chapter-outliner`（skill，节级产提纲，素材不足时报缺口）· `chapter-dialoguer`（skill，节级产定稿 + 建 depicts 立绘缺口）· `section-voice-publisher`（skill，节级定稿后逐句配音 → sec=32）· `char-stand-designer`（skill，按 depicts 引用按需出立绘）· `chapter-publisher`（skill，全章各节合并发布 `25_剧本/`→`99_game/`；节 YAML voice 随合并进章 JSON）
