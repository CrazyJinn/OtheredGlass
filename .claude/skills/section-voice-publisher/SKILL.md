---
name: section-voice-publisher
description: |
  把单节已批定稿（SecScript.status=11 的 台词.md）拆分进图并逐句克隆 TTS 语音：
  ① 拆分对齐进图（script_splitter.py：台词.md ↔ 已有 LineAudio 逐句行对齐——新增建节点+produces{order 中点}、修改沿用节点置 0、删除 DETACH DELETE、级联作废未变句恢复，幂等）→
  ② 兜底建立绘缺口（据拆分后图行 (scene, who, portrait) 引用：选定 IllusDesign 建 depicts 边 + 为每个被引用变体建 StandingIllustration(status=0) + expands_to/ref_style 边——台词.md 的 [表情] 标注在此变成图结构）→
  ③ 按本节出场角色 VoiceDesign（图 Character→has_voice_design→VoiceDesign，status=11 已批准）挑行（图查 say 行 status=0——待配/被驳回/stale 均归一于此）→
  ④ LLM 逐句判别 emotion（12 词表）+ 产 tts_text 配音变体（原文加省略号/叹号等语气符号）→
  ⑤ Qwen3 单 venv（env/.venv-qwen，voice_clone_runner.py）：ensure-ref 出/复用 ref → publish 按 Qwen3 Base Voice Clone 逐句克隆（输入 tts_text 变体承载情绪，emotion 仅作图标注）→
  母带落 15_声音/<char>/<key>.wav → voice_bundler.py sync 拷贝运行时副本到 99_game/assets/voices/ + bind-graph 写回图行节点（voice_key/emotion/tts_text/attempts/text_sha1/status=10 待审）。
  voice key = <char>-<chapter_stem>-<scene_block_id>-<行节点id>（节点 id 即行身份，插入/删除行不漂移）。在单节定稿已批、需要拆分/配音或重配被驳回/已改句时使用（由 plot-design 单节聚焦触发）。
argument-hint: <section_id>
arguments:
  - section_id
allowed-tools: Read, Bash, Write, Edit
---

# 节级拆分进图 + 配音发布（SecScript 定稿 → 逐句 LineAudio → 行级 TTS）

把**单节已批定稿**（`SecScript.status=11` 的 `台词.md`）先**拆分对齐进图**（逐句 LineAudio 节点 + `SecScript-[:produces {order}]->LineAudio`），再对图中 say 行按需克隆 TTS 语音，行级结果写回图节点属性：
按本节出场角色 `VoiceDesign`，用 [voice_clone_runner.py](../../../.claude/scripts/voice/voice_clone_runner.py) ensure-ref 出/复用 ref_audio → 同脚本 `publish` 逐句 clone（Qwen3 Base Voice Clone，输入 tts_text 变体承载情绪，均 env/.venv-qwen）→ 母带落 `15_声音/<角色名>/`，`sync` 拷贝运行时副本到 `99_game/assets/voices/`，再用 [voice_bundler.py](../../../.claude/scripts/voice/voice_bundler.py) `bind-graph` 给每个（重）生成行写节点属性（`status=10` 待审）。

> **拆分幂等**（script_splitter.py 对齐算法）：台词.md 与图行按签名（op+who+text）difflib 对齐——未变行原样保留（级联 -1 的未变 say 行且 wav 在 → 恢复 10，**resubmit 微调回路下未变行连 status 都不动**，已批 11 保持）；text 变化行沿用节点置 0（voice key 不变覆盖 wav）；md 新增行建新节点（order 取上下句中点，**单句插入不丢任何行**）；md 删除行 DETACH DELETE。order 中点耗尽时全节重排（order 不进 voice key，安全）。
> **行身份 = 节点雪花 id**（voice key 末段，永不复用）——md 插入/删除/移动行不改变其他行的 key，旧 wav 不成孤儿。

## 参数

| 参数 | 说明 |
|------|------|
| section_id | Section 节点 ID（snowflake）。沿产物链查 SecScript + 所属 Chapter（算 stem）+ 逐句行 |

## 前置条件

- 本节 `SecScript.status=11`（定稿已批）；否则停止，提示先走 chapter-dialoguer + 定稿审。
- 所属 `Chapter.status=11`（结构已批）。
- 本节出场角色的 `VoiceDesign.status=11`（声音已批）。未就绪（无 VoiceDesign 或 status≠11）角色**警告跳过**（该角色 say 行保持 status=0 待配，运行时静默不播），提示先经 `char-design` 跑 `char-voice-design` 并审批，不阻断其他角色配音。

## 流程

### 1. 查 Section 产物链 + 所属 Chapter + 本节角色 VoiceDesign

```cypher
// (1) Section → SecOutline → SecScript（沿产物链取定稿）+ 所属 Chapter（算 stem）
MATCH (ch:Chapter)-[:has_section]->(sec:Section {id:'<section_id>'})-[:has_outline]->(:SecOutline)-[:produces]->(sc:SecScript)
RETURN sc.script_path AS script_path, sc.status AS sc_status, sc.id AS sc_id,
       ch.chapter_no AS no, ch.title AS title, ch.status AS ch_status;
```

- `sc_status≠11` → 停止（先定稿审）。
- 出场角色 = 图行 distinct `who`（首拆图无行时读 `台词.md` 的说话行 `who` 集合）。再查其 VoiceDesign：

```cypher
// (2) 本节出场角色 VoiceDesign
MATCH (c:Character)-[:has_voice_design]->(v:VoiceDesign)
WHERE c.name IN ['<角色1>','<角色2>']
RETURN c.name AS char, v.status AS vstatus, v.instruct AS instruct,
       v.ref_text AS ref_text, v.ref_audio_path AS ref_audio_path;
```

- `vstatus≠11` 的角色警告跳过（不写进 profiles）。
- **stem 构造**：由 `voice_bundler.chapter_stem_from_meta(no, title)` 算（`chapter<NN>_<title>`，NN=chapter_no 零填充），与 chapter-publisher 产出的章 JSON 文件名一致——本 skill 与 chapter-publisher 共用此函数，杜绝 stem 漂移。

### 2. 拆分对齐进图（幂等——每次配音前必跑）

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/script_splitter.py" split \
  --section '<section_id>' \
  --report '99_game/data/.cache/split-<stem>-sec<MM>.json'
```

- 前置：SecScript=11（脚本自校验）。解析失败（md 格式违例）→ 脚本报**行号+原文**，就地修 md 后重跑（**不要**绕过拆分直接配音）。
- 读报告：`created/updated/deleted/restored/reordered` 计数与 warnings（Scene 缺失等）。**首次拆分** = 全部 created；**微调重拆** = 仅 updated（被改句）；**级联重拆** = restored（恢复 10）+ 0（重配）。
- 报告 warnings 里的 Scene 缺失 → 提示用户先跑 scene-designer 建场景（stages 边缺不阻塞配音）。

### 2b. 兜底建立绘缺口（台词.md 的 [表情] 标注 → 图结构）

拆分后图行已带 portrait 引用（`LineAudio.portrait`）。对**本节出现的每个 (scene, who, portrait) 组合**（say 行且 portrait 非空）检查立绘可用性，缺则兜底建——这是台词.md `[表情]` 标注变成图结构的地方（chapter-dialoguer 只写文字不建缺口）：

1. **选定 IllusDesign**（着装决策）：查该角色着装候选——优先场景相关事件着装（`Character-[:involved]->(:Event)-[:wears]->(:CostumeStyle)-[:outfit_for]->(illus)`），兜底角色默认着装（`Character-[:has_costume]->(:CostumeStyle)-[:outfit_for]->(illus)`）。选定一个 IllusDesign 后：

```cypher
// depicts 边（sync=false 引用边；同 Scene 同 IllusDesign 经 MERGE 去重）
MATCH (s:Scene {name:'<scene_name>'}), (i:IllusDesign {id:'<illus_id>'})
MERGE (s)-[r:depicts]->(i) SET r.sync = false;
```

2. **建变体缺口节点**（该 (IllusDesign, portrait) 变体尚不存在时；`stand_id` 用 `snowflake_base62.py -n 1 -q` 新生成）：

```cypher
// 查变体是否已存在（同 IllusDesign 下同 variant_label）
MATCH (i:IllusDesign {id:'<illus_id>'})-[:expands_to]->(stand:StandingIllustration)
WHERE stand.variant_label = '<portrait>'
RETURN stand.id AS id;

// 不存在则兜底建（status=0 待 plot-design 按需出图）+ ref_style 参考边
MERGE (stand:StandingIllustration {id:'<stand_id>'})
SET stand.variant_label = '<portrait>', stand.status = 0;
MATCH (i:IllusDesign {id:'<illus_id>'}), (stand:StandingIllustration {id:'<stand_id>'})
MERGE (i)-[r1:expands_to]->(stand) SET r1.sync = true;
MATCH (char:Character {name:'<who>'})-[:has_voice_style]->(ls:LanguageStyle),
      (stand:StandingIllustration {id:'<stand_id>'})
MERGE (ls)-[r2:ref_style]->(stand) SET r2.sync = true;
```

- 同一 IllusDesign 被多 Scene 引用时变体池共用（出图按 IllusDesign 级一次出多场景用）；已存在的 (IllusDesign, variant) 只补 depicts 边，不重建变体。
- 缺口建立的变体清单进段 7 汇报（plot-design 后续沿 `Scene-depicts->IllusDesign-expands_to->stand` 推进出图）。

### 3. 算 tasks（挑行 → LLM 判 emotion + 产 tts_text 变体 → 写 tasks JSON）

#### 3a. 挑行算任务（图查 say 行 status=0）

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_bundler.py" tasks-from-graph \
  --section '<section_id>' \
  -o '99_game/data/.cache/voice-tasks-<stem>-sec<MM>.json'
```

`tasks-from-graph`：图查 `say 且 status=0` 的行（待配/被驳回/stale 拆分时已归一于此）→ 按 produces.order 遍历切块推导 scene_block_id → 产出 `{char: [{key, text, scene_id, node_id}]}`——**不含 emotion/tts_text**（下一步做）。key = `<char>-<stem>-<scene_block_id>-<节点id>`。`--nodes <id,...>` 可只挑指定行（dashboard 重生成 deeplink 用）。

#### 3b. LLM 逐句判别 emotion + 产 tts_text 配音变体（本 skill 的核心判断步骤）

**读本节 `台词.md` 全文**（对话上下文），对 tasks 里的每个任务句做两件事：

1. **判别 emotion**（12 词表选一）：`平静` / `高兴` / `悲伤` / `愤怒` / `震惊` / `无奈` / `调侃` / `温柔` / `冷漠` / `紧张` / `恐惧` / `坚定`。判别依据：该句台词文本 + 前后对话语境 + 该角色在此刻的情绪走向。
2. **产 tts_text 配音变体**：在台词原文基础上做**仅标点/停顿级修饰**——按情绪加省略号（迟疑/喃喃）、叹号（惊讶/愤怒）、问号强化、破折号拖音、逗号停顿；**禁止增删改任何汉字**（运行时字幕显示原文 text，变体发声必须与字幕字面一致——加字会音字不符出戏）。原文已足够口语化时 `tts_text` 等于原文。强烈语气诉求（语气词/引导词，如「哼」「咦」「你说」）不写在变体里，而是建议作者写进台词.md 原文（text 层改动走 stale 自动重配，字幕同步）。驳回句重配时变体保持原文级（标点至多微调），靠**同文本重采样**的韵律随机性换演绎——仍不满意说明是 ref 音色问题，回 char-voice-design 层调 instruct。

**编辑 tasks JSON**（Edit 工具改第 3a 产出的文件）给每个任务项写入 `"emotion": "<词表项>"` 与 `"tts_text": "<变体>"`。emotion 仅作图标注与 dashboard 筛选展示（Qwen Base clone 无 instruct 通道，不参与合成参数）；**情绪表达全部由 tts_text 变体承载**；缺 tts_text 回落原文。

> 重生成（被驳回/stale）句也要重判重写——驳回往往因为语气不对。

### 4. 构造单节 profiles.json

把第 1 步查到的就绪角色 VoiceDesign（`instruct/ref_text/ref_audio_path` 三字段）写成 `99_game/data/.cache/voice-profiles-<stem>-sec<MM>.json`，格式 `{char: {instruct, ref_text, ref_audio_path}}`。

### 5. 批量克隆 wav（单 venv）

> 两步同 venv `env/.venv-qwen`（Python 3.14 + Qwen3-TTS）——项目唯一声音链 venv（见 [15_声音/README.md](../../../15_声音/README.md)）。

#### 5a. Qwen VoiceDesign ensure-ref（env/.venv-qwen）

```bash
env/.venv-qwen/Scripts/python.exe "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_clone_runner.py" ensure-ref \
  --profiles '99_game/data/.cache/voice-profiles-<stem>-sec<MM>.json'
```

`ref_audio_path` 文件存在则复用，否则 Qwen VoiceDesign 合成（`14_声音设计/<char>/<char>_ref.wav`，24kHz）。正常情况下 ref_audio 已由 char-voice-design 在设计阶段合成，此处多为 [reuse]。

#### 5b. Qwen3 Base Voice Clone 逐句合成（env/.venv-qwen，输入 tts_text 变体承载情绪）

```bash
env/.venv-qwen/Scripts/python.exe "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_clone_runner.py" publish \
  '99_game/data/.cache/voice-tasks-<stem>-sec<MM>.json' \
  --profiles '99_game/data/.cache/voice-profiles-<stem>-sec<MM>.json' \
  --out-dir '15_声音'   # 母带 <out-dir>/<角色名>/<key>.wav（24kHz 原生）
```

逐句 try/except：单句失败记入 failed 列表（退出码 1 + stderr 逐条列出）——**失败句不 bind**（保持 status=0 下轮重挑），成功句正常。汇报必须包含 failed 清单。

#### 5c. 同步运行时副本（母带 → 99_game/assets/voices/，dashboard 逐句审在此试听）

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_bundler.py" sync
```

### 6. 行级结果写回图节点（bind-graph）

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_bundler.py" bind-graph \
  --tasks '99_game/data/.cache/voice-tasks-<stem>-sec<MM>.json' \
  --keys '<成功句的 key 逗号列表，失败句排除>'
```

`bind-graph`（单事务）：给每个成功行节点写 `voice_key / emotion / tts_text / attempts=旧+1 / text_sha1=sha1(原文) / status=10`（配完待审，dashboard 逐句音频审）。5b 无失败时省略 `--keys`（默认全部）。

> **不碰** manifest.voices / chapter_packs.voices：章 JSON 还没合并，此时写入会污染或残缺。这两处由 chapter-publisher 合并完成后统一补（读合并后章 JSON 推导，覆盖式写入）。

### 7. 汇报与审批去向

status=10 的行进 dashboard 审批中心「逐句音频审」（按节分组）：每 say 行一张卡（原文/变体对照 + 判别 emotion 徽章 + wav 试听 + 单句通过=11/驳回=0），**节级「通过」gate = 该节全部行 status=11**。单句驳回 → 行 status=0 + 卡片下方「重生成」deeplink 唤起 plot-design 单节聚焦重跑本 skill（`--nodes <被驳回行id>` 只重做该句）。整节驳回 → 该节 say 行全置 0（重配，台词不变）。

## 重做与对齐

- **行身份不漂移**：voice key 末段是 LineAudio 节点雪花 id——台词.md 插入/删除/移动行不会使其他行的 key 失效，旧 wav 不成孤儿。台词被改的行在重拆时判 stale 置 0 自动重配；人工微调走 dashboard「重新提交审批」（仅 sc→10，**不动行节点**），重批后重拆只重做被改句，未变句审批结果原样保留。
- **status=-1 级联**：SecScript/上游被 sync 级联 → 该节全部行 -1。重跑本 skill：拆分对齐把「text_sha1 匹配且 wav 在」的行恢复 10（音频复用不重配），其余置 0 重配；若 SecScript 本身 -1，先经 dialoguer 重做定稿升 11，再重跑本 skill。

## 汇报

列出：节 script_path、stem、拆分对齐统计（created/updated/deleted/restored/reordered）、本轮挑行统计（待配 N 句，复用保持 M 句）、各角色产出 wav 数（`{char: N}`）、跳过的角色（无 VoiceDesign 或未就绪）、**failed 清单（char/key/错误）**、bind 的行数、行级 status=10 计数。提示用户去 dashboard 审批中心做逐句音频审。

## 参考文档

- 拆分对齐：[script_splitter.py](../../../.claude/scripts/script_splitter.py)（parse_md/align/split——台词.md↔图行对齐与 order 中点的唯一实现）
- 挑行与绑定：[voice_bundler.py](../../../.claude/scripts/voice/voice_bundler.py)（make_voice_key / tasks-from-graph --nodes / bind-graph）
- 基线音色设计：[char-voice-design](../char-voice-design/SKILL.md)（VoiceDesign 生成）
- 合并衔接：[chapter-publisher](../chapter-publisher/SKILL.md)（voice_key 随图投影进章 JSON + 补 manifest/chapter_packs）
- 声音 Schema：[00_init/Schema/声音.md](../../../00_init/Schema/声音.md)（含 BgmTrack）
