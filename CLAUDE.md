# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这个项目是什么

「他者之镜」（OtheredGlass）是一个**以 Neo4j 图数据库为唯一事实来源、由 Claude Code skills/agents 驱动的 AI 游戏生产流水线**，最终产物是一个 Godot 2D Galgame（`99_game/`）。整条链路把"世界观文字 → 叙事图 → 美术提示词 → 文生图/图生图 → 剧本 JSON → 游戏成品"自动化，人工只在关键节点审批。

项目级文档，动手前按需读：
- [README.md](README.md) — **编排流程视角**：三大编排 Agent（`char-design` / `scene-design` / `plot-design`）的时序图、独立审批流程、全部 Skill 功能概述、项目文件夹结构。
- 节点 status 流转 / 审批规则 / sync 级联的权威源：[55_dashboard/core/status.py](55_dashboard/core/status.py)（`NODE_STATUS`）、[core/cascade.py](55_dashboard/core/cascade.py)、[00_init/Schema/](00_init/Schema/)。**改任何节点/边/status 逻辑前必读。**

子项目各有自己的指南：[55_dashboard/CLAUDE.md](55_dashboard/CLAUDE.md)（人工治理后台）、[99_game/README.md](99_game/README.md)（Godot 工程）。

## 三大子系统

| 子系统 | 位置 | 职责 |
|-------|------|------|
| **Skills + Agents** | `.claude/skills/`、`.claude/agents/` | 自动化生产：组装 prompt、调 OfoxAI 出图、推进节点 `status` |
| **人工治理后台** | [55_dashboard/](55_dashboard/) | Streamlit 应用，浏览/编辑/审批/级联重置，与 skills 共享同一个 Neo4j |
| **游戏运行时** | [99_game/](99_game/) | Godot 4.3+ Galgame，集中式 `ScriptInterpreter` 消费纯 JSON 剧本 |

目录前缀的数字是**流水线阶段编号**（创作输入 `00_` → 叙事数据 `01_` → 剧情数据 `02_` → 美术 `06_/07_` → 声音 `14_/15_` → 后台 `55_` → 成品 `99_`），并非每个阶段都已落地，按编号即可判断某产物在链路中的位置。

## 核心架构（必须跨文件理解的大图）

### 1. Neo4j 是数据脊柱，`cypher_exec.py` 是唯一读写入口

所有 skill / 后台 / 脚本对图数据库的读写都收敛到 [.claude/scripts/cypher_exec.py](.claude/scripts/cypher_exec.py)（后台 `repo/` 层是它在本子项目内的等价物）。它只执行调用方（LLM）即时生成的 Cypher 并结构化返回，本身不含业务逻辑。连接 `bolt://localhost:7687`，user `neo4j`。

```bash
# skills 内部用相对 skill 的路径引用：
python "${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py" -c "MATCH (n:Character) RETURN n.name AS name LIMIT 10" --json
# 项目根等价写法：
python .claude/scripts/cypher_exec.py -c "..." --json          # JSON 输出
python .claude/scripts/cypher_exec.py -f path/import.cypher --multi   # 多语句单事务（导入场景）
python .claude/scripts/cypher_exec.py -c "..." --raw           # 裸标量，供管道取 id
echo "MATCH (n) RETURN count(n) AS c" | python .claude/scripts/cypher_exec.py --stdin --json
```

### 2. Schema 是唯一事实来源

节点/边的英文名、字段、方向、基数、sync 属性全部定义在 [00_init/Schema/](00_init/Schema/)（叙事基础 / 角色美术 / 场景美术 / 剧情 / 声音 五个模块），总览见 [00_init/Schema总览.md](00_init/Schema总览.md)。**写 Cypher 前必须先 Read 对应 Schema**，按其中的英文标签/属性名生成。后台的 [core/schema_loader.py](55_dashboard/core/schema_loader.py) 在启动时解析这些 `.md` 表格驱动 UI 字段——**改 Schema 格式会同时影响 skills 和后台**。

### 3. 生产链 = DAG + status + sync 级联

每条生产链是有向无环图（如角色美术：`Character → AppearanceStyle → DesignSheet → IllusDesign → StandingIllustration`；角色声音设计：`Character →has_voice_design→ VoiceDesign`，由 `char-voice-design` 产、`char-design` 管（status 10 生产完成即待审→11，无 submit 步，下游配音要求 11），下游供 `section-voice-publisher` 节级配音；剧情节级产物链：`Section →has_outline→ SecOutline →produces→ SecScript -[:produces {order}]-> LineAudio(×N 逐句台词行)`，Section 为纯编排容器**无 status**，三产物各用通用 status（SecOutline 0→1 / SecScript 0→1→10→11 / LineAudio 逐句行：say 行 0→10→11 行级音频审、非 say 行拆分即 11），链式 sync 级联——改提纲自动作废定稿+全部行、改定稿自动作废全部行，重拆时 text_sha1 匹配且 wav 在的未变句恢复 10 只重配被改句）。**台词双轨分离**：`台词.md` 是人读/人改的唯一定稿格式（机器可解析，script_splitter.parse_md）；图行是结构化真相——行身份=节点雪花 id（voice key 末段，md 插入/删除行不漂移）、顺序=produces 边 order（大间距 ×1000，句间插入取中点）；`台词.jsonl` 已停产。两个核心机制：

- **`status` 字段**跟踪节点状态，统一语义：`-1` 作废重做 / `0` 待处理 / `1` 已完成 / `2` 图片完成 / `10` 待审 / `11` 批准。规则在 [55_dashboard/core/status.py](55_dashboard/core/status.py) 的 `NODE_STATUS` 显式定义（**刻意不解析 .md**，.md 是散文式说明、格式不稳）。
- **`sync` 边属性**：上游节点属性变更后，沿 `sync=true` 出边 BFS，把可达下游 `status` 重置为 **`-1`**（作废重做）；`sync=false` 阻断（如叙事边 `wears`、`relation`）。级联实现在 [55_dashboard/core/cascade.py](55_dashboard/core/cascade.py)。

### 4. 每个 skill 内部是三段式【查状态 → 完成任务 → 保存结果】

读各 `SKILL.md` 的 frontmatter 与流程节即可。`char-prompt-assembler` / `infra-image-generator` 是**纯产出层**——只产 prompt/图片文件，**不读写图、不写 status**；节点字段与 status 一律由调用方的生产 skill 在「保存结果」步用 MERGE 兜底统一写入。

- **先产出物再写图**：凡产物由外部生成脚本产出（图片/音频/大文件），必须先落盘并校验成功，才允许在「保存结果」步写图与 status；生成失败禁止写 status（避免图与文件系统漂移）。LLM 直产文本（prompt/设计描述）随写图语句内联交付，不受此限。

### 5. 编排 agent 是纯分发层，有铁律

`char-design` / `scene-design` agent 的入口决策**只做**：解析角色/场景 → 只读查 status → 据 status 决策 → 用 `Skill` 工具加载生产 skill → 复查 → 汇报。**严禁**在入口决策阶段：亲自写 Cypher 写入、亲自调生成脚本、绕过生产 skill 直接调用纯产出子 skill（`char-prompt-assembler`/`infra-image-generator`）。**Skill 工具是扁平的**：加载某生产 skill 后，agent 即在该 skill 流程内继续执行其三段式，**包括按其指示调用其声明的子 skill**——这是预期行为，不是越界。真正越界 = ①未先加载生产 skill 就凭空直调子 skill；②调子 skill 产出文件后不走该生产 skill 的「保存结果」步写 status。详见 [.claude/agents/char-design.md](.claude/agents/char-design.md)。

## 写 Cypher 的硬约束

来自 [cypher_exec.py](.claude/scripts/cypher_exec.py) 顶部 docstring，违反会导致静默错误：

1. **先读 Schema** 再写 Cypher，按英文标签/属性名/方向生成。
2. **直接内联值，不用 `$param`**——CLI 下 `$param` 会被 Shell 解析。字符串用单引号、转义内部单引号；长语句用 `-f` 文件或 `--stdin`。
3. **写操作用 `MERGE`** 保证幂等。
4. **必须指定标签**：`MERGE (n:DesignSheet {id:'...'})`，不要裸 `MERGE (n {id:...})`。
5. **属性名严格按 Schema 英文名**：`prompt_path`、`image_path`、`status`、`sync` 等。
6. **查询加 `LIMIT`**，避免全表扫描。
7. **多语句按依赖排序**：先建节点再建边；`--multi` 在单事务内顺序执行。
8. **status 白名单**：仅 `-1/0/1/2/10/11`。

## 容易踩的坑（status / 级联 / 分发）

- **`status=-1` 与 `status=0` 都视为"需生成/需推进"**。查待办时**禁止**在 WHERE 加 `status >= 0` 把 `-1` 滤掉——这是最常见的失误源。调度判据**只看 status，不看产物文件是否存在**；`-1` 必须重新生成并**覆盖**旧产物，禁止因文件已存在而跳过，也禁止读旧 prompt/旧图。
- **判断"节点有无 status"必须用 `is not None`**——`status=0`（待处理）是合法 falsy，真值判断会误隐藏。
- **写边严格按 Schema 方向（上游→下游）**。方向写反会让 MATCH 静默返回空，进而误报"节点未创建"。例如 `IllusDesign` 是 `outfit_for`/`produces` 的**入边目标端**，不是源。
- **级联下游重置为 `-1`**（不是 `0`；design.md 验收标准里写 `0` 是笔误，以代码为准）。

## 凭证（settings.json，已 gitignore）

`settings.json`（项目根，已在 `.gitignore`）持有 `neo4j_password` 与 `ofox_api_key`。密码优先级：`--password` 参数 > `NEO4J_PASSWORD` 环境变量 > 向上搜索到的 `settings.json`。OfoxAI key 由 [infra-image-generator](.claude/skills/infra-image-generator/scripts/ofoxai_api.py) 从同一 `settings.json` 读。改凭证来源时要同步 [55_dashboard/config/settings.py](55_dashboard/config/settings.py)。

## ID 约定

所有节点 ID 用雪花算法 Base62 编码（如 `Nv93TkkkgC`），全局唯一、**无前缀**。生成：

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py" -n 1 -q
```

引用已有叙事节点时通过**名称查 ID**（`MATCH (c:Character {name:'陆择'}) RETURN c.id`），不靠前缀推断。

## 常用命令速查

```bash
# ── 图数据库（需本地 Neo4j 运行于 bolt://localhost:7687）──
python .claude/scripts/cypher_exec.py -c "MATCH (n:Character) RETURN n.name AS name LIMIT 10" --json

# ── 后台（http://localhost:8501，自动检测/安装依赖）──
bash 55_dashboard/run.sh                 # 或 Windows: 55_dashboard/run.bat
cd 55_dashboard && python -m pytest                       # 全部（core 层纯单测，不连真实 Neo4j）
cd 55_dashboard && python -m pytest tests/test_cascade.py::test_xxx -v   # 单用例

# ── Godot 游戏（需 Godot 4.3+）──
#   编辑器导入 99_game/project.godot，F5 从标题→「开始游戏」进 chapter01_新皮肤
cd 99_game/tools && pip install -r requirements.txt       # 数据校验（无需 Godot）
cd 99_game/tools && python validate_chapter.py ../data/chapters/chapter01_新皮肤.json ../data/剧本.schema.json
cd 99_game/tools && python -m pytest test_validate.py -v   # 预期 3 用例通过 + CLI 输出 OK
godot --headless -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit   # GUT 单测（需装 Gut 到 addons/）
```

无全局 lint / formatter；Python 用系统解释器（开发环境 3.14），无 `.venv`。后台测试**必须在 `55_dashboard/` 目录下跑**（`from core import ...` 依赖 cwd 在 `sys.path`）。

## 何时用 skill / agent

- 要推进某角色的整条美术链 → 调 `char-design` agent（传角色名或 ID）。
- 要推进某场景的美术或 BGM → 调 `scene-design` agent（BgmTrack 缺口由其编排 `bgm-designer` 兜底建并产描述；wav 由用户手动生成归档）。
- 要从创作文本提取叙事实体/关系 → `nrt-narrative-extractor`（离线产 CSV + import.cypher）。
- 要手动加节点/边或发现图缺口 → `nrt-graph-builder`。
- 要给叙事图做体检/补全缺口、按角色聚焦多轮增长 → `nrt-narrative-grower`（可选聚焦入参 + 多轮迭代，产 `02_剧情数据/<日期>_round<N>_建议.json`，dashboard 审批写回；范围限定基础节点 Character/Event/Location/Info/Choice）。
