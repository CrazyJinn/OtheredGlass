---
name: section-voice-publisher
description: |
  把单节定稿（SecScript.status=11）的台词 JSONL 逐句克隆 TTS 语音：
  按本节出场角色 VoiceDesign（图 Character→has_voice_design→VoiceDesign，status=11 已批准）：
  tasks-from-section --only 挑行（missing/rejected/stale——驳回重生成与台词改动只重做需重配的句，未变句的 wav 与 approved 状态原样复用）→ **LLM 逐句判别 emotion**（12 词表，按台词上下文）→ Qwen VoiceDesign ensure-ref（env/.venv-qwen，voice_clone_runner.py）→ CosyVoice3 inference_instruct2（env/.venv-cosyvoice，cosyvoice_runner.py publish，按判别 emotion 映射 instruct）逐句克隆 → 母带落 15_声音/<char>/<key>.wav → voice_bundler.py sync 拷贝运行时副本到 99_game/assets/voices/ + bind-audio 写回 台词.jsonl say 行 audio{key,emotion,status:pending,attempts,text_sha1}。
  voice key = <char>-<chapter_stem>-<scene_id>-<line_id>（行 id 稳定寻址，插入/删除行不漂移）。兜底建 LineAudio 产物节点（SecScript-[:produces]->LineAudio）写 status=10（逐句音频审）。在单节定稿已批、需要配音或重配被驳回/已改句时使用（由 plot-design 单节聚焦触发）。
argument-hint: <section_id>
arguments:
  - section_id
allowed-tools: Read, Bash, Write, Edit
---

# 节级配音发布（SecScript 定稿 → 台词 JSONL 行级 audio 绑定）

把**单节 `台词.jsonl`** 的 say 行按需克隆出 TTS 语音，行级结果写回 JSONL 的 `audio` 对象：
按本节出场角色 `VoiceDesign`，用 [voice_clone_runner.py](../../../.claude/scripts/voice/voice_clone_runner.py) ensure-ref 出/复用 ref_audio → [cosyvoice_runner.py](../../../.claude/scripts/voice/cosyvoice_runner.py) 按判别 emotion 逐句 clone → 母带落 `15_声音/<角色名>/`，`sync` 拷贝运行时副本到 `99_game/assets/voices/`，再用 [voice_bundler.py](../../../.claude/scripts/voice/voice_bundler.py) `bind-audio` 给每个（重）生成 say 行写 `audio`（`status:"pending"` 待审）。

> **按需挑行**：`tasks-from-section --only missing,rejected,stale` 只把「未配音 / 被驳回 / 台词已改（text_sha1 不匹配）」的句生成任务——**approved 且未改的句不重配**（wav 与行状态原样复用）。首次配音时全部 say 行都是 missing，等价全量。
> **voice key 行 id 寻址**：`<char>-<chapter_stem>-<scene_id>-<line_id>`，line_id 是台词行稳定 id（节内递增永不复用）——插入/删除/移动行不改变其他行的 key，旧 wav 不成孤儿。

## 参数

| 参数 | 说明 |
|------|------|
| section_id | Section 节点 ID（snowflake）。用于沿产物链查 SecScript.script_path + 所属 Chapter（算 stem） |

## 前置条件

- 本节 `SecScript.status=11`（定稿已批）；否则停止，提示先走 chapter-dialoguer + 定稿审。
- 所属 `Chapter.status=11`（结构已批）。
- 本节出场角色的 `VoiceDesign.status=11`（声音已批）。未就绪（无 VoiceDesign 或 status≠11）角色**警告跳过**（该角色台词行保持 missing，运行时静默不播），提示先经 `char-design` 跑 `char-voice-design` 并审批，不阻断其他角色配音。

## 流程

### 1. 查 Section 产物链 + 所属 Chapter + 本节角色 VoiceDesign

```cypher
// (1) Section → SecOutline → SecScript（沿产物链取定稿）+ 所属 Chapter（算 stem）
MATCH (ch:Chapter)-[:has_section]->(sec:Section {id:'<section_id>'})-[:has_outline]->(:SecOutline)-[:produces]->(sc:SecScript)
RETURN sc.script_path AS script_path, sc.status AS sc_status, sc.id AS sc_id,
       ch.chapter_no AS no, ch.title AS title, ch.status AS ch_status;
```

读台词 JSONL `<script_path>` 的 meta 行取 `requires.characters`（本节出场角色名列表），再查其 VoiceDesign：

```cypher
// (2) 本节出场角色 VoiceDesign
MATCH (c:Character)-[:has_voice_design]->(v:VoiceDesign)
WHERE c.name IN ['<角色1>','<角色2>']
RETURN c.name AS char, v.status AS vstatus, v.instruct AS instruct,
       v.ref_text AS ref_text, v.ref_audio_path AS ref_audio_path;
```

- `vstatus≠11` 的角色警告跳过（不写进 profiles）。
- **stem 构造**：由 `voice_bundler.chapter_stem_from_meta(no, title)` 算（`chapter<NN>_<title>`，NN=chapter_no 零填充），与 chapter-publisher 产出的章 JSON 文件名一致——本 skill 与 chapter-publisher 共用此函数，杜绝 stem 漂移。

### 2. 算 tasks（挑行 → LLM 判别 emotion → 写 tasks JSON）

#### 2a. 挑行算任务

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_bundler.py" tasks-from-section '<script_path>' \
  --chapter-no <no> --chapter-title '<title>' \
  --only 'missing,rejected,stale' \
  -o '99_game/data/.cache/voice-tasks-<stem>-sec<MM>.json'
```

`tasks-from-section`：读台词 JSONL，只挑行状态 ∈ `--only` 的 say 行（stale = `audio.text_sha1 ≠ sha1(当前 text)`），产出 `{char: [{key, text, scene_id, line_id}]}`——**不含 emotion**（下一步判别）。key 与章级推导同源（行 id 寻址）。

#### 2b. LLM 逐句判别 emotion（本 skill 的核心判断步骤）

**读本节台词 JSONL 全文**（对话上下文），对 tasks 里的每个任务句，从 12 情绪词表选一个：

`平静` / `高兴` / `悲伤` / `愤怒` / `震惊` / `无奈` / `调侃` / `温柔` / `冷漠` / `紧张` / `恐惧` / `坚定`

判别依据：该句台词文本 + 前后对话语境 + 该角色在此刻的情绪走向（台词文件无 emotion 字段——情绪判断完全在本步骤做）。**编辑 tasks JSON** 给每个任务项写入 `"emotion": "<词表项>"`（Edit 工具改第 2a 产出的文件）。词表即 [emotion_instruct.json](../../../.claude/scripts/voice/emotion_instruct.json) 的键（未映射词 publish 兜底"用自然的语气说"）。

> 重生成（rejected/stale）句也要重判——驳回往往因为语气不对。

### 3. 构造单节 profiles.json

把第 1 步查到的就绪角色 VoiceDesign（`instruct/ref_text/ref_audio_path` 三字段）写成 `99_game/data/.cache/voice-profiles-<stem>-sec<MM>.json`，格式 `{char: {instruct, ref_text, ref_audio_path}}`。

### 4. 批量克隆 wav（双 venv）

> CosyVoice 要 `transformers==4.51`，与 Qwen3-TTS（4.57）冲突，故两套 python 分离（见 [15_声音/README.md](../../../15_声音/README.md)）：`env/.venv-qwen`（Python 3.14，VoiceDesign 出 ref）+ `env/.venv-cosyvoice`（Python 3.10，CosyVoice3 clone）。

#### 4a. Qwen VoiceDesign ensure-ref（env/.venv-qwen）

```bash
env/.venv-qwen/Scripts/python.exe "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_clone_runner.py" ensure-ref \
  --profiles '99_game/data/.cache/voice-profiles-<stem>-sec<MM>.json'
```

`ref_audio_path` 文件存在则复用，否则 Qwen VoiceDesign 合成（`14_声音设计/<char>/<char>_ref.wav`，24kHz）。正常情况下 ref_audio 已由 char-voice-design 在设计阶段合成，此处多为 [reuse]。

#### 4b. CosyVoice3 clone（env/.venv-cosyvoice，按判别 emotion instruct）

```bash
PYTHONPATH="$(python "${CLAUDE_SKILL_DIR}/../../scripts/voice/paths.py" --pythonpath)" \
  env/.venv-cosyvoice/Scripts/python.exe "${CLAUDE_SKILL_DIR}/../../scripts/voice/cosyvoice_runner.py" publish \
  '99_game/data/.cache/voice-tasks-<stem>-sec<MM>.json' \
  --profiles '99_game/data/.cache/voice-profiles-<stem>-sec<MM>.json' \
  --out-dir '15_声音'   # 母带 <out-dir>/<角色名>/<key>.wav
```

逐句 try/except：单句失败记入 failed 列表（退出码 1 + stderr 逐条列出）——**失败句不 bind**（保持 missing/rejected 下轮重挑），成功句正常。汇报必须包含 failed 清单。

#### 4c. 同步运行时副本（母带 → 99_game/assets/voices/，dashboard 逐句审在此试听）

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_bundler.py" sync
```

### 5. 行级结果写回台词 JSONL（bind-audio）

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_bundler.py" bind-audio '<script_path>' \
  --tasks '99_game/data/.cache/voice-tasks-<stem>-sec<MM>.json' \
  --keys '<成功句的 key 逗号列表，失败句排除>'
```

`bind-audio`（经 jsonl_script，保行字节稳定——只 diff 被 bind 的行）：给每个成功句的 say 行写
`audio: {key, emotion: <判别值>, status: "pending", attempts: <旧+1，缺省 1>, text_sha1: <当前台词 sha1>}`。
4b 无失败时省略 `--keys`（默认全部）。

> **不碰** manifest.voices / chapter_packs.voices：章 JSON 还没合并，此时写入会污染或残缺。这两处由 chapter-publisher 合并完成后统一补（读合并后章 JSON 推导，覆盖式写入）。

### 6. 写 status（MERGE 兜底建 LineAudio + produces 边 + 写 status=10）

`--multi` 单事务；`vo_id` 用 `snowflake_base62.py` 新生成（已存在 LineAudio 时复用其 id）：

```cypher
// 1. MERGE 兜底建 LineAudio 产物节点
MERGE (vo:LineAudio {id:'<vo_id>'})
SET vo.name = '<节标题>配音',
    vo.status = 10;      // 逐句音频审（直写，不经 submit）

// 2. 兜底建 produces 边（SecScript→LineAudio，sync=true：改定稿级联作废配音）
MATCH (sc:SecScript {id:'<sc_id>'}), (vo:LineAudio {id:'<vo_id>'})
MERGE (sc)-[r:produces]->(vo) SET r.sync = true;
```

status=10 进 dashboard 审批中心「逐句音频审」：每 say 行一张卡（文本 + 判别 emotion 徽章 + wav 试听 + 单句通过/驳回），**节级「通过」gate = 全部含 audio 的 say 行 approved 且无 rejected**。单句驳回 → 行 `status:"rejected"` + 卡片下方出现「重生成」deeplink 唤起 plot-design 单节聚焦重跑本 skill（`--only rejected,stale` 只重做被驳回句）。整节驳回 → 全行归 pending + 节点归 0（重配，不改台词）。

## 重做与对齐

- **行 id 不漂移**：voice key 末段是行 id（非数组下标）——台词 JSONL 插入/删除/移动行不会使其他行的 key 失效，旧 wav 不成孤儿。台词被改的行由 `text_sha1` 判 stale 自动重挑重配；人工微调走 dashboard「重新提交审批」（SecScript 11→10 + LineAudio -1），重配时同样只重做 stale 句。
- **status=-1 级联**：若 LineAudio（或上游）被 sync 级联重置，LineAudio `-1` 直接重跑本 skill（missing/stale 全挑，覆盖 wav）；若 SecScript `-1`，先经 dialoguer 重做定稿升 11，再重跑本 skill。

## 汇报

列出：节 script_path、stem、本轮挑行统计（missing/rejected/stale 各 N 句，approved 复用 M 句）、各角色产出 wav 数（`{char: N}`）、跳过的角色（无 VoiceDesign 或未就绪）、**failed 清单（char/key/错误）**、bind 的行数、LineAudio.status=10。提示用户去 dashboard 审批中心做逐句音频审。

## 参考文档

- 台词 JSONL 与 audio 行级状态：[jsonl_script.py](../../../.claude/scripts/jsonl_script.py)（load/save/needs_regen/set_audio——行字节稳定与 stale 判定的唯一实现）
- voice 键生成与绑定：[voice_bundler.py](../../../.claude/scripts/voice/voice_bundler.py)（make_voice_key / tasks-from-section --only / bind-audio）
- 基线音色设计：[char-voice-design](../char-voice-design/SKILL.md)（VoiceDesign 生成）
- 合并衔接：[chapter-publisher](../chapter-publisher/SKILL.md)（audio.key 随投影进章 JSON + 补 manifest/chapter_packs）
- 声音 Schema：[00_init/Schema/声音.md](../../../00_init/Schema/声音.md)（含 BgmTrack）
