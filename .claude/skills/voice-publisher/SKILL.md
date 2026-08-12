---
name: voice-publisher
description: |
  把已发布章节（99_game/data/chapters/<stem>.json，由 chapter-publisher 产）的所有 say 台词批量克隆 TTS 语音并绑定到运行时：
  按角色 VoiceProfile（图 Character→has_voice_profile→VoiceProfile，status=1）：Qwen VoiceDesign 出 ref_audio（系统 python，voice_clone_runner.py ensure-ref）→ CosyVoice3 inference_instruct2（venv python D:/cosyvoice_env，cosyvoice_runner.py publish，按 say.emotion 映射 instruct 控情绪）逐句克隆 → wav 落 99_game/assets/voices/<char>-<stem>-<scene_id>-<line_idx>.wav；voice_bundler.py inject 给 chapter JSON 每个 say 注入 voice 字段 + manifest 写 voices 段 + chapter_packs.voices（三处同源对齐，键由 make_voice_key 单一生成）。
  生产时序位于 chapter-publisher 之后（dialoguer → publisher → voice-publisher）。在全章已发布、各角色基线声音就绪、需要全章配音时使用。
argument-hint: <chapter_id>
arguments:
  - chapter_id
allowed-tools: Read, Bash, Write, Edit
---

# 章节配音发布（Chapter → 99_game voice 绑定）

把已发布的章 JSON 的**所有 say 台词**批量克隆出 TTS 语音，绑定到运行时：
按角色 `VoiceProfile`（图 `Character→has_voice_profile→VoiceProfile`）载入可复用 clone prompt，用 [voice_clone_runner.py](../../../15_声音/voice_clone_runner.py) 逐句克隆 wav → `99_game/assets/voices/`，再用 [voice_bundler.py](../../../99_game/tools/voice_bundler.py) 给 chapter JSON 每个 say 注入 `voice` 字段、更新 `manifest.voices` 与 `chapter_packs.voices`。

**voice 与 portrait 同构**（字符串键 → manifest → res:// 路径），三处对齐契约同立绘 guid 整键：wav 文件名 == `manifest.voices` 键 == chapter JSON `say.voice`，单一来源 [voice_bundler.make_voice_key](../../../99_game/tools/voice_bundler.py)：`<char>-<stem>-<scene_id>-<line_idx>`。

## 参数

| 参数 | 说明 |
|------|------|
| chapter_id | Chapter 节点 ID（snowflake）。用于查 chapter_no/title 构造 stem + 查各角色 VoiceProfile |

## 前置条件

- 章 JSON 已发布到 `99_game/data/chapters/<stem>.json`（由 chapter-publisher 跑过）；未发布则停止，提示先调 chapter-publisher。
- 至少一个出场角色的 `VoiceProfile.status=1`（instruct/ref_text 已写）；未就绪角色**警告跳过**（该角色台词无 voice，运行时静默不播），不阻断整章配音。

## 流程

### 1. 查章 + 各角色 VoiceProfile

```cypher
// (1) Chapter 本体 → stem
MATCH (ch:Chapter {id:'<chapter_id>'})
RETURN ch.title AS title, ch.chapter_no AS no;
// (2) 各出场角色 VoiceProfile（characters 取自 chapter JSON 的 meta.requires.characters）
MATCH (c:Character)-[:has_voice_profile]->(v:VoiceProfile)
WHERE c.name IN ['陆择','顾盈','伊芙','小夏']
RETURN c.name AS char, v.status AS vstatus, v.instruct AS instruct,
       v.ref_text AS ref_text, v.ref_audio_path AS ref_audio_path,
       v.clone_prompt_path AS clone_prompt_path;
```

**stem 构造**：`chapter<NN>_<章概述>`（NN=`chapter_no` 零填充，章概述取 title 核心主题清洗 Windows 非法字符），与 chapter-publisher 产出的 JSON 文件名一致。章 JSON 路径 `99_game/data/chapters/<stem>.json`。

### 2. 构造 profiles.json + tasks.json

把第 1 步查到的各角色 VoiceProfile（仅 instruct/ref_text/ref_audio_path/clone_prompt_path 四字段）写成 `99_game/data/.cache/voice-profiles-<stem>.json`，格式 `{char: {instruct, ref_text, ref_audio_path, clone_prompt_path}}`。

```bash
# 按 chapter JSON 的 say 行算任务清单（{char: [{key,text,scene_id,line_idx}]}）
python 99_game/tools/voice_bundler.py tasks '99_game/data/chapters/<stem>.json' \
  -o '99_game/data/.cache/voice-tasks-<stem>.json'
```

### 3. 批量克隆 wav（双环境：Qwen design ref 系统 python + CosyVoice clone venv）

> CosyVoice 要 `transformers==4.51`，与 Qwen3-TTS（4.57）冲突，故两套 python 分离：
> 系统 Python 3.14（Qwen VoiceDesign 出 ref）+ venv `D:/cosyvoice_env`（Python 3.10 + CosyVoice3 clone）。
> CosyVoice 按 `say.emotion` 映射 instruct 控情绪（emotion → instruct 映射见 [15_声音/emotion_instruct.json](../../../15_声音/emotion_instruct.json)）。

#### 3a. Qwen VoiceDesign 出 ref_audio（系统 python 3.14）

复用已有 ref_audio 或首次 VoiceDesign 合成（按 VoiceProfile.instruct）：

```bash
python 15_声音/voice_clone_runner.py ensure-ref \
  --profiles '99_game/data/.cache/voice-profiles-<stem>.json'
```

`voice_clone_runner.ensure_refs`：对每个角色，`ref_audio_path` 文件存在则复用，否则 VoiceDesign 合成写盘（`15_声音/output/<char>_ref.wav`，24kHz）。跳过缺 instruct/ref_text 的角色。

#### 3b. CosyVoice3 clone（venv python，按 emotion instruct）

```bash
D:/cosyvoice_env/Scripts/python.exe 15_声音/cosyvoice_runner.py publish \
  '99_game/data/.cache/voice-tasks-<stem>.json' \
  --profiles '99_game/data/.cache/voice-profiles-<stem>.json' \
  --out-dir '99_game/assets/voices'
```

`cosyvoice_runner.publish`：加载 CosyVoice3 一次（`D:/model/Fun-CosyVoice3-0.5B`）；每角色用 3a 的 ref_audio（内部转 16k）；逐句按 `task.emotion` 映射 instruct（`You are a helpful assistant. 用XX语气说。<|endofprompt|>`）→ `inference_instruct2` → `99_game/assets/voices/<key>.wav`。跳过无 ref 的角色。voice key 同 `make_voice_key`（三处对齐不变）。

### 4. 绑定 voice 字段 + 更新 manifest + chapter_packs

```bash
# (a) 给 chapter JSON 每个 say 注入 voice=<key>（幂等，已绑则按当前 line_idx 重算覆盖）
python 99_game/tools/voice_bundler.py inject '99_game/data/chapters/<stem>.json'

# (b) 推导 manifest.voices 段并合并写入（--ext wav；ogg 见「Web 发布前」）
python 99_game/tools/voice_bundler.py manifest '99_game/data/chapters/<stem>.json' --ext wav

# (c) chapter_packs.voices（Web 分包；chapter_packs_updater 需支持 --voices，见下）
python 99_game/tools/voice_bundler.py list '99_game/data/chapters/<stem>.json' > /tmp/voices.txt
python 99_game/tools/chapter_packs_updater.py '<stem>' --voices "$(cat /tmp/voices.txt)"
```

> **三处对齐**：wav 文件名（第 3 步）/ `manifest.voices` 键（第 4b 步）/ chapter JSON `say.voice`（第 4a 步）都从 `voice_bundler.make_voice_key` 流出，对齐成本为零。voice_clone_runner.publish 用 tasks.json 里的现成 key 作 wav 文件名，与 inject 算的 say.voice 天然一致。

### 5. 汇报

列出：配音的章 stem、各角色产出的 wav 数（`{char: N}`）、跳过的角色（无 VoiceProfile 或未就绪）、.pt 固化情况（首次合成 / 复用）、chapter JSON 绑定的 say 数、manifest.voices 条数、chapter_packs.voices 条数、缺失/跳过警告。
附运行时提示：Godot F5 进章即可逐句播音；点 next / Auto / Skip / Ctrl 自动停旧播新（`AudioManager.play_voice` 自覆盖 + 4 处显式 `stop_voice`）。

## Web 发布前的额外步骤（导出阶段，非本 skill）

**wav→ogg 转码**（Web 端体积 1/10，Godot 流式加载；桌面开发期可只用 wav）：

```bash
pip install pydub   # 已随 qwen-tts 装好；另需 ffmpeg binary（当前环境未装）
python -c "
from pathlib import Path; from pydub import AudioSegment
d = Path('99_game/assets/voices')
for w in d.glob('*.wav'):
    AudioSegment.from_wav(w).export(d / (w.stem + '.ogg'), format='ogg')
"
# manifest 改用 ogg 扩展
python 99_game/tools/voice_bundler.py manifest '99_game/data/chapters/<stem>.json' --ext ogg
```

> wav 母带保留（15_声音/output/ 与 assets/voices/ 双份），用于后续重转码；ogg 是有损发布产物。

## 参考文档

- 剧本 voice 字段与 manifest 映射：[00_init/剧本.md](../../../00_init/剧本.md)（say.voice + voice 机制 callout）
- 基线音色 Schema：[00_init/Schema/声音.md](../../../00_init/Schema/声音.md)（VoiceProfile 节点 + has_voice_profile 边）
- voice 键生成与绑定：[99_game/tools/voice_bundler.py](../../../99_game/tools/voice_bundler.py)（make_voice_key / inject / manifest / list / tasks）
- 批量克隆执行：[15_声音/voice_clone_runner.py](../../../15_声音/voice_clone_runner.py)（.pt 持久化 / publish）
- 运行时播放：[99_game/scripts/autoload/AudioManager.gd](../../../99_game/scripts/autoload/AudioManager.gd)（play_voice / stop_voice）
- 立绘同构参照：[99_game/tools/portrait_key.py](../../../99_game/tools/portrait_key.py)（三处对齐契约的设计源）
