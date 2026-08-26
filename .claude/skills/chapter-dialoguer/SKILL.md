---
name: chapter-dialoguer
description: |
  推进 Section 图节点的定稿段：读 structurer 的章级设计简报 + outliner 的本节提纲 outline.md → 创作逐句对话 → 产出节级 台词.md（自然语言 Markdown：说话行「角色名:台词」、旁白行「旁白:叙述」、场景二级标题分隔、选择/分支/结局自然语言记录）→ 兜底建 SecScript 产物节点（SecOutline-[:produces]->SecScript）写 script_path + status=10（定稿待审，直写不经 submit；md 为自然语言格式，暂不跑 schema 校验）。
  前驱 SecOutline.status=1（提纲就绪）。创作中若发现 outline 戏剧性破碎（分支无本质差异/scene 无情绪推进），产出「结构性问题报告」回退 outliner，不写 status。场景段查 Scene-has_bgm->BgmTrack，缺口兜底建 BgmTrack(status=0)。台词.md 为实验格式——配音（section-voice-publisher）与发布（chapter-publisher）链当前仍以 台词.jsonl 为输入。
argument-hint: <section_id> [target_status]
arguments:
  - section_id
  - target_status
allowed-tools: Read, Bash, Write, Edit
---

> **status=-1 = 作废重做**：当本节 SecScript 节点被重置为 `status=-1` 时（如 SecOutline/Section/Chapter 属性变更沿 produces/has_outline/has_section 级联），即使 `台词.md` 已落盘，也**必须重新创作并覆盖**（重走 0→10）。`-1` 明确表示有旧产物要覆盖，**禁止因文件已存在而跳过，也禁止读旧台词内容**，直接以当前图节点数据 + 本节 outline.md + 章级设计简报为唯一来源重新创作。重做时 has_bgm 边 MERGE 幂等，不主动删。

# 节细节对话（SecScript 定稿段 · status 0→10）

剧情创作流程的**第三段**（节级）。读 `chapter-structurer` 的**章级设计简报**（情感弧/戏剧意图）+ `chapter-outliner` 的**本节提纲 outline.md**，创作逐句对话，产出节级 **`台词.md`**——自然语言 Markdown 对话文本（**实验格式**：下游配音/发布链仍以 `台词.jsonl` 为输入，md 定稿暂不进入下游）。落盘 `25_剧本/`（**创作/审阅区，非运行时**）。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| section_id | Section 节点 ID（snowflake） | 必传 |
| target_status | `10`（定稿→定稿待审）或 `1`（仅草稿，产出未提审；重跑本 skill 提审） | `10` |

## 流程（三段式：查状态 → 完成任务 → 保存结果）

> 本 skill 是 SecScript 产物节点的创建点 + 定稿段 status 的唯一写入点；台词.md 由本 skill 直接创作产出。编剧是高自由度创作任务，**无纯产出子 skill**——创作与写图都在本 skill 内完成。

### 1. 查询目标节点状态

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查询。

#### 1a. 解析 Section + SecOutline + SecScript + 前驱校验

```cypher
MATCH (ch:Chapter)-[:has_section]->(sec:Section {id:'<input>'})
OPTIONAL MATCH (sec)-[:has_outline]->(ol:SecOutline)
OPTIONAL MATCH (ol)-[:produces]->(sc:SecScript)
RETURN sec.id AS id, sec.section_no AS section_no, sec.title AS title,
       ol.outline_path AS outline_path, ol.status AS ol_status,
       sc.id AS sc_id, sc.script_path AS script_path, sc.status AS sc_status,
       ch.chapter_no AS chapter_no
LIMIT 1
```

**前驱校验**：`ol_status = 1`（提纲就绪，`outline_path` 非空），否则停止并提示先完成本节提纲段（`chapter-outliner`）。`sc_status` 为 `10/11` → 定稿已待审/已批，停止并提示。

#### 1b. 读设计简报 + 本节提纲 + 查创作上下文

**先读两份创作依据**：
- Read `25_剧本/chapter<NN>_<章概述>/设计简报.md`（NN = chapter_no 零填充，<章概述> 取章 title）——取出情感弧线 / 戏剧意图 / 设计支柱（本节在弧线中的位置靠分节规划定位），本节对话的情感基调全靠它。
- Read **本节** `outline.md`（`SecOutline.outline_path`）——场景分段（Scene 名/时段）、分支拓扑（choice/label/jump/ending）必须如实体现到台词.md（见格式规范）；`authoring` 散文（方向/情感弧/约束/职责/节拍/母题锚点/衔接）是创作指引，不进台词；「BGM 倾向」是散文参考（供 3b 兜底建 BgmTrack 命名参考）。

任一缺失则停止并提示先跑上游（structurer / outliner）。

再查图：

```cypher
// 出场角色 + 语言习惯（创作对话的核心依据）
MATCH (char:Character) WHERE char.name IN ['<角色名1>','<角色名2>']
OPTIONAL MATCH (char)-[:has_voice_style]->(voice:LanguageStyle)
RETURN char.name AS name, char.description AS description, char.character_tags AS tags,
       voice.vocabulary AS vocabulary, voice.rhythm AS rhythm,
       voice.habits AS habits, voice.emotion_patterns AS emotion_patterns,
       voice.description AS voice_desc
LIMIT 20
```

### 2. 完成任务（创作细节对话）

读本节 outline.md 逐场景段，据章级设计简报（情感弧/戏剧意图）+ 角色 LanguageStyle，创作逐句对话写入 `台词.md`。

#### 台词.md 格式规范

```markdown
# <节标题>

## <Scene 名>（<时段>）

旁白:<叙述文本，一行一句>
<角色名>:<台词>
<角色名>:<台词>

**选择**
- <选项文本> → <去向：label 名 / 结局>
- <选项文本> → <去向>

**分支:<label 名 或 选项文本>**

<角色名>:<台词>
旁白:<叙述>

**结局**:<BE|TE|HE|NE>——<落点一句话>
```

1. **说话行**：`角色名:台词`——一行一句，冒号用半角，角色名用 Character.name 原名。
2. **旁白行**：`旁白:叙述`——一行一句，承载环境/动作/心理等非台词叙述。
3. **场景分隔**：`## <Scene 名>（<时段>）` 二级标题——按 outline 场景段顺序，Scene 名/时段照搬提纲契约值（BGM 兜底按 Scene 名查图）。
4. **选择/分支/结局**：`**选择**` 小节列各选项及去向；各分支正文以 `**分支:<名>**` 加粗行开头；`**结局**:<kind>——<落点>`。拓扑去向按 outline 如实记录，不改动分支结构。
5. **覆盖完整**：提纲全部场景段、分支、结局都要写，不得增删场景/分支。
6. **情感递进**：每个场景内部情绪有起伏（不是平铺），对齐设计简报情感弧线的该段位置。
7. **Write 落盘**：`25_剧本/chapter<NN>_<章概述>/sec<MM>_<节概述>/台词.md`（与该节 outline.md 同目录）。`SecScript.script_path` 指向此 `.md` 路径。Write 自动创建章/节目录。

#### 创作质量自检（发现 outline 破碎 → FAIL 报告）

创作完成后自检，若发现**根本问题在 outline 而非台词**——即 outline 戏剧性破碎，再怎么写也写不出合格对话：
- 分支 options 无戏剧本质差异（outliner 的本质差异门控漏过的 flavor 级分支）
- scene 间无情绪推进（提纲本身平铺，无 turning point/climax）
- 拓扑死胡同或 ending 缺落点

→ **触发创作质量 FAIL**：**不落盘定稿、不写 SecScript status**，产出「结构性问题报告」返回，列出破碎点（哪个 choice/scene/拓扑 + 为什么写不出合格对话）。由 plot-design 接住后把 `SecOutline.status` 归 `0`（待提纲），重调 `chapter-outliner` 重做本节提纲。**与 outliner 素材不足报告对称**——不硬凑烂对话交付。

> 通过自检才进段 3 写图。

### 3. 保存结果（写图 + BGM 缺口兜底）

#### 3a. 写图（MERGE 兜底建 SecScript + produces 边 + 写 script_path/status）

> `台词.md` 为自然语言格式，**暂不跑 schema 校验**（validate_chapter.py 只吃 JSONL/JSON）。

`--multi` 单事务；`sc_id` 用 `snowflake_base62.py` 新生成（已存在 SecScript 时复用其 id）：

```cypher
// 1. MERGE 兜底建 SecScript 产物节点
MERGE (sc:SecScript {id:'<sc_id>'})
SET sc.name = '<节标题>定稿',
    sc.script_path = '<script_path>',   // 25_剧本/.../台词.md
    sc.status = <1 | 10>;      // target_status=10 → 10（定稿待审，直写不经 submit）；草稿 → 1

// 2. 兜底建 produces 边（SecOutline→SecScript，sync=true：改提纲级联作废定稿/配音）
MATCH (ol:SecOutline {id:'<ol_id>'}), (sc:SecScript {id:'<sc_id>'})
MERGE (ol)-[r:produces]->(sc) SET r.sync = true;
```

#### 3b. BGM 缺口兜底（副作用——对本节每个场景段的 Scene）

查 `Scene-has_bgm->BgmTrack`；**无关联或 `bgm_status=0`** 时兜底建（`bgm_id` 用 `snowflake_base62.py -n 1 -q` 新生成；name 按提纲「BGM 倾向」与场景情绪起一个短名如「晨离」，即 manifest 键/章 JSON track 名）：

```cypher
// 查询：该 Scene 是否已关联 BgmTrack
MATCH (s:Scene {name:'<scene_name>'})
OPTIONAL MATCH (s)-[:has_bgm]->(b:BgmTrack)
RETURN b.id AS bgm_id, b.status AS bgm_status;

// 兜底建（缺关联或 status=0 时；sync=false——BGM 独立资产不随场景编辑级联）
MERGE (b:BgmTrack {id:'<bgm_id>'})
  ON CREATE SET b.status = 0
SET b.name = '<track 名>';
MATCH (s:Scene {name:'<scene_name>'}), (b:BgmTrack {id:'<bgm_id>'})
MERGE (s)-[r:has_bgm]->(b) SET r.sync = false;
```

> BgmTrack 推进（prompt 生成 → 用户手动产 wav → status=2）由**用户直接触发 `bgm-designer`**，不进 plot-design 编排。

**status 写入**：定稿 → `SecScript.status=10`（定稿待审，等 dashboard `approve`→`11`）；草稿 → `1`；创作质量 FAIL → 不写 status（见段 2 末尾）。

最后汇总：定稿 `SecScript.script_path`、`SecScript.status=10`、兜底建的 BgmTrack 缺口（若有）。若触发创作质量 FAIL，汇总「结构性问题报告」而非定稿路径。

## 参考文档

- 剧情 Schema：[00_init/Schema/剧情.md](../../../00_init/Schema/剧情.md) — Section/产物链（SecOutline/SecScript/LineAudio）/contains 边
- 上游：[chapter-structurer](../chapter-structurer/SKILL.md)（章级设计简报）/ [chapter-outliner](../chapter-outliner/SKILL.md)（本节提纲 → SecOutline status=1）
- 下游：plot-design agent（本节定稿审 status=11）；配音（section-voice-publisher）与发布（chapter-publisher）链当前仍以 台词.jsonl 为输入，md 定稿暂不进入下游
