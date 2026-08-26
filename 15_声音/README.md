# 15_声音 — 角色配音 clone 母带（Qwen3 design/clone 试听 + CosyVoice3 配音）

「Qwen VoiceDesign 设计音色（[14_声音设计](../14_声音设计/)）→ CosyVoice3 clone（按情绪，母带在本目录）」两段式配音。
基线音色由图 VoiceDesign 治理（1:1 per 角色，status=11 已批才可供配音）；每句情绪（emotion）由 chapter-dialoguer 创作时标注。

## 产物目录（声音链两阶段，均按角色名整理、gitignore）

| 目录 | 内容 | 生产者 |
|---|---|---|
| `14_声音设计/<角色名>/candidates/` | **多候选临时夹**（dashboard 采用后整夹删除）：`<char>_c1..c3_ref.wav`（3 候选，24kHz）+ `<char>_cN_平静/高兴/愤怒.wav`（9 情绪试听，Qwen3 Base clone）+ `candidates.json`（manifest） | char-voice-design（voice_clone_runner design-candidates + audition，均在 env/.venv-qwen） |
| `14_声音设计/<角色名>/` | 设计母带：`<char>_ref.wav`（正式 ref，24kHz，dashboard 采用候选后固化；下游 CosyVoice publish 按需重采样 `<char>_ref_16k.wav`） | char-voice-design（采用固化） |
| `15_声音/<角色名>/` | clone 母带：`<char>-<stem>-<scene_id>-<line_idx>.wav` 逐句配音 | section-voice-publisher（cosyvoice_runner publish） |
| `99_game/assets/voices/` | 运行时副本（扁平 `<key>.wav`，manifest 键指向此处） | `voice_bundler.py sync` 幂等拷贝（母带先行，运行时副本是部署产物） |

> **试听引擎（Qwen3 Base Voice Clone，情绪靠文本语义自适应）≠ 下游配音引擎（CosyVoice3，按 say.emotion 映射 instruct 控情绪）**——试听预览音色与韵律基线，成品情绪表现以配音结果为准。

## 谁负责什么

| 环节 | 职责 |
|---|---|
| **char-voice-design**（声音设计） | 读 Character+LanguageStyle+Info+Event 生成 VoiceDesign（instruct/统一长句 ref_text）+ 先合成 3 候选 ref（同一 instruct × 3 采样，Qwen VoiceDesign）+ 每候选 3 情绪试听（Qwen3 Base clone）落盘再写图（status=10 候选待选，写 candidates_path）；dashboard 审批中心逐候选试听「采用」（固化为 `<char>_ref.wav`、status 仍 10）→ 二审 10→11；`char-design` 管 |
| **chapter-dialoguer**（创作） | 写台词时标 `say.emotion`（每句情绪，词表选）——气氛源头 |
| **section-voice-publisher**（节级配音） | 单节定稿后（sec=31）CosyVoice3 按 emotion clone（`env/.venv-cosyvoice`）→ voice 写回节 YAML（sec→32）；`plot-design` 管 |
| VoiceDesign（图） | 角色基线音色设计（instruct / ref_text / ref_audio_path） |

## 两套 venv（项目内，uv 管理；transformers 冲突 → 隔离）

Qwen 要 `transformers==4.57`，CosyVoice 要 4.51，同环境冲突。两个 venv 隔离（项目内，gitignore）：

| venv | Python | 用途 | 锁文件 |
|---|---|---|---|
| `env/.venv-qwen` | 3.14 | Qwen3 全家：VoiceDesign 出候选 ref + Base Voice Clone 出情绪试听 | [requirements/qwen.txt](requirements/qwen.txt) |
| `env/.venv-cosyvoice` | 3.10 | CosyVoice3 clone（下游配音，按 emotion） | [requirements/cosyvoice.txt](requirements/cosyvoice.txt) |

**建 venv**（uv）：
```bash
uv venv --python 3.14 env/.venv-qwen
uv pip install --python env/.venv-qwen/Scripts/python.exe -r 15_声音/requirements/qwen.txt
# cosyvoice 同（--python 3.10 + requirements/cosyvoice.txt）
```

## 路径配置（paths.py）

模型/仓库路径统一在 [paths.py](../.claude/scripts/voice/paths.py)：读 `settings.json` 的 `voice` 节（`model_dir` / `cosyvoice_repo`）+ env，模型目录**无默认值（未配置即报错），不硬编码 D:/**。cosyvoice_runner 的 CosyVoice/Matcha-TTS import 路径不再走 `sys.path.insert`，改由调用方注入 `PYTHONPATH`（`python paths.py --pythonpath` 输出）。

- **模型权重**：settings.json `voice.model_dir`（外部共享，gitignore；下有 `Qwen3-TTS-12Hz-1.7B-VoiceDesign` / `Qwen3-TTS-12Hz-1.7B-Base` / `Fun-CosyVoice3-0.5B`）
- **CosyVoice 仓库**：`env/vendor/CosyVoice/`（项目根，与 .venv-* 同层；含 Matcha-TTS，gitignore，可用 settings `voice.cosyvoice_repo` 覆盖）
- **venv 路径不入 settings**：`env/.venv-qwen` / `env/.venv-cosyvoice` 是项目内 gitignore 产物、位置恒定（uv 按仓库约定创建），调用命令直接写项目根相对路径；settings 只放机器外部可迁移路径（model_dir / cosyvoice_repo 等）

迁机器：改 settings.json `voice.model_dir` + 建 venv（requirements 锁）+ vendor CosyVoice（见下）。

## vendor CosyVoice（第三方，不入 git）

`env/vendor/CosyVoice/`（项目根，与 `.venv-*` 同属根级第三方环境层）含 cosyvoice 包 + Matcha-TTS（.gitignore `vendor/`）。**venv 与 vendor 不挪窝**：venv 内嵌绝对路径不可移动，重建会丢手工 patch（pyworld/kaldifst 等）。

```bash
git clone https://github.com/FunAudioLLM/CosyVoice.git env/vendor/CosyVoice
cd env/vendor/CosyVoice && git submodule update --init third_party/Matcha-TTS
# 或直接从已 clone 的仓库 cp（含 Matcha-TTS）
```

## 工具（脚本统一在 `.claude/scripts/voice/`，本目录只留母带/依赖：requirements/）

| 文件 | 用途 | venv |
|---|---|---|
| [voice_clone_runner.py](../.claude/scripts/voice/voice_clone_runner.py) | Qwen3 全家：`ensure-ref`（下游配音单 ref 复用）/ `design-candidates`（同一 instruct × N 采样出候选 ref 24k + manifest，多候选流程第一步）/ `audition`（Qwen3 Base Voice Clone 按_manifest_ 每候选出 3 情绪试听，情绪靠试听句语义自适应，第二步） | `env/.venv-qwen` |
| [cosyvoice_runner.py](../.claude/scripts/voice/cosyvoice_runner.py) | CosyVoice3 按 emotion clone：`publish`（下游配音母带 → 本目录 <char>/；ref 按需重采样 16k） | `env/.venv-cosyvoice` |
| [voice_bundler.py](../.claude/scripts/voice/voice_bundler.py) | voice 键生成 + 章/节 YAML 绑定 + 母带→运行时同步（make_voice_key / inject / inject-yaml / tasks / tasks-from-section / sync / chapter_stem_from_meta） | 系统 python |
| [emotion_instruct.json](../.claude/scripts/voice/emotion_instruct.json) | emotion → CosyVoice instruct 映射（下游配音用；试听不消费） | — |
| [paths.py](../.claude/scripts/voice/paths.py) | 路径配置（模型/仓库，读 settings.json） | — |

## emotion（每句情绪）

- 由 **chapter-dialoguer** 标（创作时 say.emotion）
- 词表 + 映射：[emotion_instruct.json](../.claude/scripts/voice/emotion_instruct.json)（**仅下游 CosyVoice 配音消费**；试听阶段 Qwen3 Base 无 instruct 通道，情绪靠文本语义自适应）
- 未映射 → 默认"用自然的语气说"

## 配音（生产）

- **节级配音**（主线，plot-design 单节聚焦触发）：`section-voice-publisher <section_id>`——单节定稿后即配音，sec=31→32，dashboard 声音审 32→33。

章级 chapter-publisher 合并时节 YAML 的 voice 随 pure concat 进章 JSON，末尾补 manifest.voices / chapter_packs.voices。

## 运行时

Godot `AudioManager.play_voice(key)` 播音；运行时只看 `say.voice` → manifest → wav，**对后端（Qwen/CosyVoice）无感**，换后端零运行时改动。

## 参考

- 基线音色 Schema：[00_init/Schema/声音.md](../00_init/Schema/声音.md)
- 剧本 emotion 字段：[剧本.md](../.claude/skills/chapter-dialoguer/references/剧本.md)
- voice 键三处对齐：[voice_bundler.py](../.claude/scripts/voice/voice_bundler.py)
- Qwen3 design & clone 官方流程：qwen-tts README「Voice Design then Clone」（`create_voice_clone_prompt` + `generate_voice_clone`）
