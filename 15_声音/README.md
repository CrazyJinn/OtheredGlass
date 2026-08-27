# 15_声音 — 角色配音 clone 母带（Qwen3 单引擎：VoiceDesign 设计 + Base Voice Clone 配音）

「Qwen VoiceDesign 设计音色（[14_声音设计](../14_声音设计/)）→ Qwen3 Base Voice Clone 逐句配音（母带在本目录）」单引擎两段式。
基线音色由图 VoiceDesign 治理（1:1 per 角色，status=11 已批才可供配音）；每句情绪由配音期的 `tts_text` 变体承载。

## 产物目录（声音链两阶段，均按角色名整理、gitignore）

| 目录 | 内容 | 生产者 |
|---|---|---|
| `14_声音设计/<角色名>/candidates/` | **多候选临时夹**（dashboard 采用后整夹删除）：`<char>_c1..c3_ref.wav`（3 候选，24kHz）+ `<char>_cN_平静/高兴/愤怒.wav`（9 情绪试听，Qwen3 Base clone）+ `candidates.json`（manifest） | char-voice-design（voice_clone_runner design-candidates + audition，均在 env/.venv-qwen） |
| `14_声音设计/<角色名>/` | 设计母带：`<char>_ref.wav`（正式 ref，24kHz，dashboard 采用候选后固化；下游 publish 直接消费，无重采样副产物） | char-voice-design（采用固化） |
| `15_声音/<角色名>/` | clone 母带：`<char>-<chapter_stem>-<scene_block_id>-<行节点id>.wav` 逐句配音（24kHz 原生） | section-voice-publisher（voice_clone_runner publish） |
| `99_game/assets/voices/` | 运行时副本（扁平 `<key>.wav`，manifest 键指向此处） | `voice_bundler.py sync` 幂等拷贝（母带先行，运行时副本是部署产物） |

> **试听与下游配音同引擎**（Qwen3 Base Voice Clone，配音期情绪由 tts_text 变体承载）——试听即成品引擎的真实预览。

## 谁负责什么

| 环节 | 职责 |
|---|---|
| **char-voice-design**（声音设计） | 读 Character+LanguageStyle+Info+Event 生成 VoiceDesign（instruct/统一长句 ref_text）+ 先合成 3 候选 ref（同一 instruct × 3 采样，Qwen VoiceDesign）+ 每候选 3 情绪试听（Qwen3 Base clone）落盘再写图（status=10 候选待选，写 candidates_path）；dashboard 审批中心逐候选试听「采用」（固化为 `<char>_ref.wav`、status 仍 10）→ 二审 10→11；`char-design` 管 |
| **section-voice-publisher**（节级配音） | 单节定稿已批（SecScript=11）后拆分进图 + Qwen3 Base Voice Clone 逐句 clone（`env/.venv-qwen`）→ bind-graph 写行节点（voice_key/emotion/tts_text/status=10 待审）；`plot-design` 管 |
| VoiceDesign（图） | 角色基线音色设计（instruct / ref_text / ref_audio_path） |

## venv（项目内，uv 管理）

单一声音链 venv（项目内，gitignore）：

| venv | Python | 用途 | 锁文件 |
|---|---|---|---|
| `env/.venv-qwen` | 3.14 | Qwen3 全家：VoiceDesign 出候选 ref + Base Voice Clone 出情绪试听与逐句配音 | [requirements/qwen.txt](requirements/qwen.txt) |

**建 venv**（uv）：
```bash
uv venv --python 3.14 env/.venv-qwen
uv pip install --python env/.venv-qwen/Scripts/python.exe -r 15_声音/requirements/qwen.txt
```

## 路径配置（paths.py）

模型路径统一在 [paths.py](../.claude/scripts/voice/paths.py)：读 `settings.json` 的 `voice` 节（`model_dir`）+ env，模型目录**无默认值（未配置即报错），不硬编码 D:/**。

- **模型权重**：settings.json `voice.model_dir`（外部共享，gitignore；下有 `Qwen3-TTS-12Hz-1.7B-VoiceDesign` / `Qwen3-TTS-12Hz-1.7B-Base`）
- **venv 路径不入 settings**：`env/.venv-qwen` 是项目内 gitignore 产物、位置恒定（uv 按仓库约定创建），调用命令直接写项目根相对路径；settings 只放机器外部可迁移路径（model_dir）

迁机器：改 settings.json `voice.model_dir` + 建 venv（requirements 锁）。

## 工具（脚本统一在 `.claude/scripts/voice/`，本目录只留母带/依赖：requirements/）

| 文件 | 用途 | venv |
|---|---|---|
| [voice_clone_runner.py](../.claude/scripts/voice/voice_clone_runner.py) | Qwen3 全家：`ensure-ref`（下游配音单 ref 复用）/ `design-candidates`（同一 instruct × N 采样出候选 ref 24k + manifest，多候选流程第一步）/ `audition`（Qwen3 Base Voice Clone 按 manifest 每候选出 3 情绪试听，第二步）/ `publish`（逐句配音母带 → 本目录 <char>/，输入 tts_text 变体承载情绪） | `env/.venv-qwen` |
| [voice_bundler.py](../.claude/scripts/voice/voice_bundler.py) | voice 键生成 + 图挑行/写回 + 母带→运行时同步（make_voice_key / tasks-from-graph / bind-graph / sync / manifest / list / chapter_stem_from_meta） | 系统 python |
| [paths.py](../.claude/scripts/voice/paths.py) | 路径配置（模型路径，读 settings.json） | — |

## emotion（每句情绪）

- 由 **section-voice-publisher** 配音期逐句判别（12 词表：平静/高兴/悲伤/愤怒/震惊/无奈/调侃/温柔/冷漠/紧张/恐惧/坚定）
- 仅作**图标注与 dashboard 筛选展示，不进合成参数**（Qwen3 Base clone 无 instruct 通道）——情绪演绎全部由 `tts_text` 变体承载（配音期 LLM 由原文产，**仅标点/停顿级修饰、禁增删改汉字**：字幕显示原文，变体发声须与字幕字面一致；语气词诉求写进台词.md 原文层）

## 配音（生产）

- **节级配音**（主线，plot-design 单节聚焦触发）：`section-voice-publisher <section_id>`——单节定稿已批（SecScript=11）即拆分进图 + 逐句 clone，行节点 status=10 待审，dashboard 逐句音频审 0→10→11。

章级 chapter-publisher 合并时 voice_key 随图投影进章 JSON，末尾补 manifest.voices / chapter_packs.voices。

## 运行时

Godot `AudioManager.play_voice(key)` 播音；运行时只看 `voice_key` → manifest → wav，**对合成引擎无感**，换引擎零运行时改动。

## 迁移备注（CosyVoice 废弃）

逐句配音后端已从 CosyVoice3 `inference_instruct2` 全面迁移到 Qwen3 Base Voice Clone（`cosyvoice_runner.py` / `emotion_instruct.json` / `requirements/cosyvoice.txt` 已删除）。本地 gitignored 残留可自行清理：

- `env/.venv-cosyvoice/`、`env/vendor/CosyVoice/`（含 Matcha-TTS）
- settings.json 的 `voice.cosyvoice_repo` 键（若曾配置）
- `14_声音设计/<char>/<char>_ref_16k.wav`（CosyVoice 16k 重采样副产物）

## 参考

- 基线音色 Schema：[00_init/Schema/声音.md](../00_init/Schema/声音.md)
- 逐句行字段（emotion/tts_text/voice_key）：[00_init/Schema/剧情.md](../00_init/Schema/剧情.md)
- voice 键三处对齐：[voice_bundler.py](../.claude/scripts/voice/voice_bundler.py)
- Qwen3 design & clone 官方流程：qwen-tts README「Voice Design then Clone」（`create_voice_clone_prompt` + `generate_voice_clone`）
