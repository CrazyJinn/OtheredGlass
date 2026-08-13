---
name: section-voice-publisher
description: |
  把单节定稿（Section.status=31）的逐句台词克隆 TTS 语音并绑定回节 YAML：
  按本节出场角色 VoiceProfile（图 Character→has_voice_profile→VoiceProfile，status=1）：Qwen VoiceDesign ensure-ref（.venv-qwen，voice_clone_runner.py）→ CosyVoice3 inference_instruct2（.venv-cosyvoice，cosyvoice_runner.py publish，按 say.emotion 映射 instruct 控情绪）逐句克隆 → wav 落 99_game/assets/voices/<char>-<stem>-<scene_id>-<line_idx>.wav；voice_bundler.py inject-yaml 给节 YAML 每个 say 注入 voice 字段。
  节级产物与章级 voice-publisher 的 key 单一源对齐（同 make_voice_key），章合并（chapter-publisher）时 voice 字段随 pure concat 自动进章 JSON。不碰 manifest.voices / chapter_packs.voices（章未合并，留给 chapter-publisher）。Section.status=31→32（声音待审）。在单节定稿已批、需要立即给该节配音时使用（由 plot-design 单节聚焦触发）。
argument-hint: <section_id>
arguments:
  - section_id
allowed-tools: Read, Bash, Write, Edit
---

# 节级配音发布（Section 定稿 → 节 YAML voice 绑定）

把**单节定稿 YAML** 的所有 say 台词克隆出 TTS 语音，绑定回节 YAML（不碰章级 manifest）：
按本节出场角色 `VoiceProfile`，用 [voice_clone_runner.py](../../../.claude/scripts/voice/voice_clone_runner.py) ensure-ref 出/复用 ref_audio → [cosyvoice_runner.py](../../../.claude/scripts/voice/cosyvoice_runner.py) 按 `say.emotion` 逐句 clone → wav 落 `99_game/assets/voices/`，再用 [voice_bundler.py](../../../.claude/scripts/voice/voice_bundler.py) `inject-yaml` 给节 YAML 每个 say 注入 `voice` 字段。

> **与章级 voice-publisher 的关系**：本 skill 是 voice-publisher 的**节级前置**——在章 JSON 合并前（Section.status=31）就给该节配音。voice key 四组成分（char/chapter_stem/scene_id/line_idx）都能在节级单节 YAML 上算出，且与合并后章 JSON 逐位一致（`line_idx` 是 scene-block 内 lines 数组下标，merge 是 pure concat 不改写）。章合并时 voice 字段自动进章 JSON，章级仅需补 manifest/chapter_packs（由 chapter-publisher 末尾完成）。

## 参数

| 参数 | 说明 |
|------|------|
| section_id | Section 节点 ID（snowflake）。用于查 script_path + 所属 Chapter（算 stem） |

## 前置条件

- `Section.status=31`（定稿已批）；否则停止，提示先走 chapter-dialoguer + 定稿审。
- 所属 `Chapter.status=11`（结构已批）。
- 本节出场角色的 `VoiceProfile.status=1`（instruct/ref_text/ref_audio 就绪）。未就绪角色**警告跳过**（该角色台词无 voice，运行时静默不播），提示先经 `char-design` 跑 `char-voice-design`，不阻断其他角色配音。

## 流程

### 1. 查 Section + 所属 Chapter + 本节角色 VoiceProfile

```cypher
// (1) Section 本体 + 所属 Chapter（算 stem）
MATCH (ch:Chapter)-[:has_section]->(sec:Section {id:'<section_id>'})
RETURN sec.script_path AS script_path, sec.status AS sec_status,
       ch.chapter_no AS no, ch.title AS title, ch.status AS ch_status;
```

读节 YAML `<script_path>` 取 `meta.requires.characters`（本节出场角色名列表），再查其 VoiceProfile：

```cypher
// (2) 本节出场角色 VoiceProfile
MATCH (c:Character)-[:has_voice_profile]->(v:VoiceProfile)
WHERE c.name IN ['<角色1>','<角色2>']
RETURN c.name AS char, v.status AS vstatus, v.instruct AS instruct,
       v.ref_text AS ref_text, v.ref_audio_path AS ref_audio_path;
```

- `vstatus≠1` 的角色警告跳过（不写进 profiles）。
- **stem 构造**：由 `voice_bundler.chapter_stem_from_meta(no, title)` 算（`chapter<NN>_<title>`，NN=chapter_no 零填充），与 chapter-publisher 产出的章 JSON 文件名一致——本 skill 与 chapter-publisher 共用此函数，杜绝 stem 漂移。

### 2. 算 tasks（节 YAML → 按角色分组任务清单）

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_bundler.py" tasks-from-section '<script_path>' \
  --chapter-no <no> --chapter-title '<title>' \
  -o '99_game/data/.cache/voice-tasks-<stem>-sec<MM>.json'
```

`tasks-from-section`：读节 YAML（`{meta, scenes}`），按 `iter_say_lines` 遍历 say 行，用 `chapter_stem_from_meta` 算 stem，产出 `{char: [{key, text, scene_id, line_idx, emotion}]}`。key 与章级 `voice_bundler tasks` 算法同源。

### 3. 构造单节 profiles.json

把第 1 步查到的就绪角色 VoiceProfile（`instruct/ref_text/ref_audio_path` 三字段）写成 `99_game/data/.cache/voice-profiles-<stem>-sec<MM>.json`，格式 `{char: {instruct, ref_text, ref_audio_path}}`。

### 4. 批量克隆 wav（双 venv）

> CosyVoice 要 `transformers==4.51`，与 Qwen3-TTS（4.57）冲突，故两套 python 分离（见 [15_声音/README.md](../../../15_声音/README.md)）：`.venv-qwen`（Python 3.14，VoiceDesign 出 ref）+ `.venv-cosyvoice`（Python 3.10，CosyVoice3 clone）。

#### 4a. Qwen VoiceDesign ensure-ref（.venv-qwen）

复用已有 ref_audio 或首次合成：

```bash
.venv-qwen/Scripts/python.exe "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_clone_runner.py" ensure-ref \
  --profiles '99_game/data/.cache/voice-profiles-<stem>-sec<MM>.json'
```

`ref_audio_path` 文件存在则复用，否则 VoiceDesign 合成（`15_声音/output/<char>_ref.wav`，24kHz）。正常情况下 ref_audio 已由 char-voice-design 在设计阶段合成，此处多为 [reuse]。

#### 4b. CosyVoice3 clone（.venv-cosyvoice，按 emotion instruct）

```bash
.venv-cosyvoice/Scripts/python.exe "${CLAUDE_SKILL_DIR}/../../scripts/voice/cosyvoice_runner.py" publish \
  '99_game/data/.cache/voice-tasks-<stem>-sec<MM>.json' \
  --profiles '99_game/data/.cache/voice-profiles-<stem>-sec<MM>.json' \
  --out-dir '99_game/assets/voices'
```

wav 直接落正式目录 `99_game/assets/voices/<key>.wav`（key 已与章级对齐，覆盖写幂等——重跑同节不冲突）。跳过无 ref 的角色。

### 5. voice 字段写回节 YAML

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_bundler.py" inject-yaml '<script_path>' \
  --chapter-no <no> --chapter-title '<title>'
```

`inject-yaml`：按 `iter_say_lines` 遍历节 YAML 的 say 行，给每条写 `voice = make_voice_key(who, stem, scene_id, idx)`（幂等：已有则按当前 line_idx 重算覆盖）。

> **不碰** manifest.voices / chapter_packs.voices：章 JSON 还没合并，此时写入会污染或残缺。这两处由 chapter-publisher 合并完成后统一补（读合并后章 JSON 推导，覆盖式写入）。

### 6. 写 status

```cypher
MATCH (sec:Section {id:'<section_id>'})
SET sec.status = 32;  // 声音待审（直写，不经 submit；Section 永远不能 submit）
```

status=32 进 dashboard 审批中心「声音审」，逐句审听 wav + emotion 徽章：通过 → 33（声音已批，章发布前置）；驳回 → 31（重配，不改台词，重跑本 skill 覆盖 wav）。

## 重做与对齐

- **line_idx 漂移**：若该节被 chapter-dialoguer 重写（status 回 20 再升 31），lines 顺序变 → 旧 voice key 失效。chapter-dialoguer 重做产出的新 YAML **不含 voice 字段**（它只写 schema 子集，voice 由本 skill 后注入）；本 skill 对 status=31 重跑会按新 line_idx 生成新 key wav + 注入新 voice。旧 key 的 wav 成孤儿（残留磁盘、不再被引用），不影响运行时（manifest / 章 JSON 只引用当前 key）；可选手动清理 `99_game/assets/voices/` 下孤儿。
- **status=-1 级联**：若 Section 被 sync 级联重置，先经 dialoguer 重做定稿回到 31，再重跑本 skill。

## 汇报

列出：节 script_path、stem、各角色产出 wav 数（`{char: N}`）、跳过的角色（无 VoiceProfile 或未就绪）、节 YAML 绑定的 say 数、Section.status=32。提示用户去 dashboard 审批中心做声音审。

## 参考文档

- 章级配音（全量后处理）：[voice-publisher](../voice-publisher/SKILL.md)
- voice 键生成与绑定：[voice_bundler.py](../../../.claude/scripts/voice/voice_bundler.py)（make_voice_key / chapter_stem_from_meta / tasks-from-section / inject-yaml）
- 基线音色设计：[char-voice-design](../char-voice-design/SKILL.md)（VoiceProfile 生成）
- 合并衔接：[chapter-publisher](../chapter-publisher/SKILL.md)（pure concat 带 voice 进章 JSON + 补 manifest/chapter_packs）
- 声音 Schema：[00_init/Schema/声音.md](../../../00_init/Schema/声音.md)
