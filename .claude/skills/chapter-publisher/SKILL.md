---
name: chapter-publisher
description: |
  把全章各节定稿已批（各 Section.status=31 且所属 Chapter.status=11）的章节从创作区 `25_剧本/` 合并发布到运行时 `99_game/`：
  用 merge_sections_to_chapter.py 把各节定稿 YAML 拍平合并为单一章 JSON 拷到 99_game/data/chapters/ + status=11 的立绘/背景资源到 99_game/assets/ + 更新 manifest + 产出章资源清单 chapter_packs.json（Web 按章分包依据）。
  在全章各节定稿审批通过且所需立绘就绪、需发布到 Godot 运行时时使用。
argument-hint: <chapter_id>
arguments:
  - chapter_id
allowed-tools: Read, Bash, Write, Edit
---

# 章节发布（Chapter + 各 Section → 99_game）

把审阅通过的章节从**创作/审阅区**（`25_剧本/`，按节存放）发布到**运行时区**（`99_game/`）：
**把全章各节定稿 YAML 拍平合并为一个章 JSON** 落到 `99_game/data/chapters/`（Godot 只读 JSON，运行时不感知节层），拷贝章节涉及的立绘/背景图片到 `99_game/assets/`，更新 `manifest.json`，并产出**章资源清单** `chapter_packs.json`（Web 按章分包导出依据）。
发布是**确定性转换+拷贝**（非 LLM 创作），幂等——重复发布覆盖旧文件，无副作用。

## 参数

| 参数 | 说明 |
|------|------|
| chapter_id | Chapter 节点 ID（snowflake） |

## 流程

### 1. 查询章节与各节 + 前驱状态

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查 Chapter + 各 Section + 编排子图：

```cypher
// (1) Chapter 本体 + 前驱校验
MATCH (ch:Chapter {id:'<chapter_id>'})
RETURN ch.title AS title, ch.chapter_no AS no, ch.status AS status;
// (2) 各 Section（按 section_no）+ 前驱校验
MATCH (ch:Chapter {id:'<chapter_id>'})-[:has_section]->(sec:Section)
RETURN sec.section_no AS no, sec.title AS title, sec.outline_path AS outline_path,
       sec.script_path AS script_path, sec.status AS status
ORDER BY sec.section_no;
// (3) 全章 background 图层（Chapter→has_section→Section→contains→Scene→has_layer→SceneLayer）
MATCH (ch:Chapter {id:'<chapter_id>'})-[:has_section]->(:Section)-[:contains]->(s:Scene)
OPTIONAL MATCH (s)-[:has_layer]->(sl:SceneLayer {layer_type:'background'})
RETURN DISTINCT s.name AS scene_name, sl.image_path AS bg_image, sl.status AS bg_status;
// (4) 全章 depicts 立绘（深两跳：Chapter→Section→Scene→depicts→IllusDesign→expands_to→StandingIllustration + 角色回溯）
MATCH (ch:Chapter {id:'<chapter_id>'})-[:has_section]->(:Section)-[:contains]->(sc:Scene)-[:depicts]->(illus:IllusDesign)-[:expands_to]->(stand:StandingIllustration)
MATCH (char:Character)-[:has_appearance|has_voice_style|has_costume|produces|outfit_for|expands_to|ref_style*1..5]->(stand)
RETURN DISTINCT char.name AS char_name, stand.variant_label AS variant, stand.image_path AS image_path, stand.status AS status;
```

**前驱校验**：
- `ch.status` 必须 = `11`（结构已批）；**全部 Section `status` 必须 = `31`**（各节定稿已批）——章真正可发布 = `Chapter.status==11` AND 全部 `Section.status==31`。任一不满足则停止并提示先在 dashboard 推进/审批对应节。
- depicts 立绘：`status=11` 且 `image_path` 非空的才拷贝；`status≠11` 的逐个**警告**（运行时该变体走占位图），不阻断发布（让已就绪资源先上线）。
- background SceneLayer：同理，`status=11` 且 `image_path` 非空才拷贝。

### 2. 合并拍平 + 拷贝资源到 99_game/

**章 stem**：由 Chapter 构造 `chapter<NN>_<章概述>`（NN=`chapter_no` 零填充，章概述取 `ch.title` 核心主题，清洗 Windows 非法字符），运行时文件名用 `<stem>.json`。各节定稿按 `section_no` 升序作为合并输入。

```bash
# 确保目标目录存在
mkdir -p 99_game/data/chapters 99_game/assets/portraits 99_game/assets/scenes

# (a) 剧本：各节定稿 YAML 拍平合并 → 99_game/data/chapters/<stem>.json（scenes[] 按 section_no 拼接，requires 并集）
python 99_game/tools/merge_sections_to_chapter.py \
  '<sec00_script_path>' '<sec01_script_path>' ... \
  --chapter <NN> --title '<章标题>' \
  -o '99_game/data/chapters/<stem>.json'
python 99_game/tools/validate_chapter.py '99_game/data/chapters/<stem>.json' 99_game/data/剧本.schema.json
#   validate FAIL → 中断发布，报警（剧本 schema 不合，先回 25_剧本/ 修对应节定稿 YAML）
#   注：合并工具内置 scene-block id 章内唯一性校验（重复则报错）——若报 id 重复，说明 structurer 预分配 / outliner 落盘环节 id 冲突，需回上游修正。

# (b) 立绘：image_path（项目根相对）→ 99_game/assets/portraits/<角色>.<变体>.png
cp '<image_path>' '99_game/assets/portraits/<char_name>.<variant>.png'

# (c) 背景：SceneLayer.image_path → 99_game/assets/scenes/<Scene.name>.png
cp '<bg_image>' '99_game/assets/scenes/<scene_name>.png'
```

> 源路径（`image_path`/各节 `script_path`）是项目根相对，`cp`/合并时 cwd 应在项目根。目标路径的 `<角色>.<变体>` 与 manifest 的 portraits 键、合并后 JSON 的 `meta.requires.portraits` 三处对齐。
> 缺源文件（`image_path` 指向的图不存在）则**警告跳过**该资源，不中断。

### 3. 更新 manifest

跑 manifest_builder（查 status=11 立绘 + Scene，生成逻辑名→`assets/...` 映射，与上一步拷贝目标一致）：

```bash
python 99_game/tools/manifest_builder.py
```

### 4. 产出章资源清单 chapter_packs.json（Web 分包依据）

把本章用到的立绘/背景逻辑名记入 `99_game/data/chapter_packs.json`，供导出工具按章把资源分组打成 `<stem>.pck`（pck 内路径与全局 manifest 一致，挂载后 `res://` 全局路径命中）。**分包粒度仍是章 stem**（运行时不感知节层）。

数据源 = 第 1 步查到的全章结果（跨节汇总）：
- `portraits`：`<char_name>.<variant>`（status=11 的 depicts 立绘，与上一步拷贝目标对齐）
- `scenes`：`<Scene.name>`（has_layer background）

```bash
python 99_game/tools/chapter_packs_updater.py '<stem>' \
  --portraits '<char1>.<var1>,<char2>.<var2>' --scenes '<scene1>,<scene2>'
```

工具幂等：覆盖该 stem 条目，保留其他章。空列表（该章无立绘/背景）也要写入，保持清单完整。

### 5. 汇报

列出：发布的章 JSON 路径（`99_game/data/chapters/<stem>.json`）、合并的节数、拷贝的立绘清单（`<角色>.<变体>`）、背景清单（`<Scene.name>`）、跳过/缺失的资源警告、manifest 更新结果、章清单更新结果（该章 portraits/scenes 条数）。
附运行时入口提示：`GameManager.start_new_game('<stem>', '<首节首 scene-block id>')`（stem = 不含后缀的章名，如 `chapter00_序章`；首 scene-block id 取 section_no=0 节的第一个段 id）。

## Web 发布前的额外步骤（导出阶段，非本 skill）

剧本加密 + 按章分包在**导出时**做（本 skill 只产明文 + 清单，保持桌面/开发期可读）：

1. **加密剧本**（挡自动扒包，可选但 Web 推荐）：覆盖式加密，运行时 ChapterLoader 检测 magic 头自动解密。
   ```bash
   pip install -r 99_game/tools/requirements.txt   # 需 cryptography
   python 99_game/tools/encrypt_chapter.py '99_game/data/chapters/<stem>.json' '99_game/data/chapters/<stem>.json'
   ```
   ⚠️ 加密后无法再 `validate_chapter.py`（明文），故加密必须在本 skill 流程之后。
2. **按章分包**：参考 `chapter_packs.json` + `manifest.json`，把每章资源打进 `<stem>.pck`（pck 内用全局 `assets/...` 路径），Web 预设主包不含这些资源，运行时由 ChapterPackLoader 按需下载挂载。详见 [99_game/docs](../../../99_game/docs/)。

## 参考文档

- 剧本格式与 manifest 映射（含节级创作与发布合并）：[00_init/剧本.md](../../../00_init/剧本.md)
- 节合并工具：[99_game/tools/merge_sections_to_chapter.py](../../../99_game/tools/merge_sections_to_chapter.py)（N 节 YAML → 1 章 JSON）
- manifest 生成器：[99_game/tools/manifest_builder.py](../../../99_game/tools/manifest_builder.py)
- 章资源清单更新器：[99_game/tools/chapter_packs_updater.py](../../../99_game/tools/chapter_packs_updater.py)
- 剧本加密（Web）：[99_game/tools/encrypt_chapter.py](../../../99_game/tools/encrypt_chapter.py) ↔ 运行时 [99_game/scripts/util/ScriptCipher.gd](../../../99_game/scripts/util/ScriptCipher.gd)
- 章包加载（运行时）：[99_game/scripts/autoload/ChapterPackLoader.gd](../../../99_game/scripts/autoload/ChapterPackLoader.gd)
- 剧情 Schema（Chapter/Section/has_section/contains/depicts）：[00_init/Schema/剧情.md](../../../00_init/Schema/剧情.md)
