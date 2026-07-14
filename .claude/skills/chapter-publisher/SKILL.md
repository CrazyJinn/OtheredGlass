---
name: chapter-publisher
description: |
  把审阅通过（status=11）的 Chapter 从创作区 `25_剧本/` 发布到运行时 `99_game/`：
  拷贝剧本 JSON + status=11 的立绘/背景资源到 99_game/assets/ + 更新 manifest。
  在 Chapter 已审批且所需立绘就绪、需发布到 Godot 运行时时使用。
argument-hint: <chapter_id>
arguments:
  - chapter_id
allowed-tools: Read, Bash, Write, Edit
---

# 章节发布（Chapter → 99_game）

把审阅通过的章节从**创作/审阅区**（`25_剧本/`）发布到**运行时区**（`99_game/`）：
拷贝剧本 JSON + 章节涉及的立绘/背景图片到 `99_game/assets/`，并更新 `manifest.json`。
发布是**确定性拷贝**（非 LLM 创作），幂等——重复发布覆盖旧文件，无副作用。

## 参数

| 参数 | 说明 |
|------|------|
| chapter_id | Chapter 节点 ID（snowflake） |

## 流程

### 1. 查询章节与前驱状态

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查 Chapter + 编排子图：

```cypher
// (1) Chapter 本体 + 前驱校验
MATCH (ch:Chapter {id:'<chapter_id>'})
RETURN ch.title AS title, ch.chapter_no AS no, ch.script_path AS script_path, ch.status AS status;
// (2) contains 的 Scene + 其 background 图层
MATCH (ch:Chapter {id:'<chapter_id>'})-[:contains]->(s:Scene)
OPTIONAL MATCH (s)-[:has_layer]->(sl:SceneLayer {layer_type:'background'})
RETURN s.name AS scene_name, sl.image_path AS bg_image, sl.status AS bg_status;
// (3) depicts 的立绘（status + image_path + 所属角色 + 变体）
MATCH (ch:Chapter {id:'<chapter_id>'})-[:contains]->(sc:Scene)-[:depicts]->(stand:StandingIllustration)
MATCH (char:Character)-[:has_appearance|has_voice_style|has_costume|produces|outfit_for|expands_to|ref_style*1..5]->(stand)
RETURN DISTINCT char.name AS char_name, stand.variant_label AS variant, stand.image_path AS image_path, stand.status AS status;
```

**前驱校验**：
- `ch.status` 必须 = `11`（剧本已审批）。否则停止并提示先在 dashboard 审批。
- depicts 立绘：`status=11` 且 `image_path` 非空的才拷贝；`status≠11` 的逐个**警告**（运行时该变体走占位图），不阻断发布（让已就绪资源先上线）。
- background SceneLayer：同理，`status=11` 且 `image_path` 非空才拷贝。

### 2. 拷贝资源到 99_game/

剧本文件名取自 `script_path` 的 basename（如 `chapter00_序章.json`）。资源目标路径用逻辑名（与 manifest 一致）。

```bash
# 确保目标目录存在
mkdir -p 99_game/data/chapters 99_game/assets/portraits 99_game/assets/scenes

# (a) 剧本：25_剧本/ → 99_game/data/chapters/
cp '<script_path>' '99_game/data/chapters/<basename>'

# (b) 立绘：image_path（项目根相对）→ 99_game/assets/portraits/<角色>.<变体>.png
cp '<image_path>' '99_game/assets/portraits/<char_name>.<variant>.png'

# (c) 背景：SceneLayer.image_path → 99_game/assets/scenes/<Scene.name>.png
cp '<bg_image>' '99_game/assets/scenes/<scene_name>.png'
```

> 源路径（`image_path`/`script_path`）是项目根相对，`cp` 时 cwd 应在项目根。目标路径的 `<角色>.<变体>` 与 manifest 的 portraits 键、剧本 `meta.requires.portraits` 三处对齐。
> 缺源文件（`image_path` 指向的图不存在）则**警告跳过**该资源，不中断。

### 3. 更新 manifest

跑 manifest_builder（查 status=11 立绘 + Scene，生成逻辑名→`assets/...` 映射，与上一步拷贝目标一致）：

```bash
python 99_game/tools/manifest_builder.py
```

### 4. 汇报

列出：发布的剧本路径（`99_game/data/chapters/<basename>`）、拷贝的立绘清单（`<角色>.<变体>`）、背景清单（`<Scene.name>`）、跳过/缺失的资源警告、manifest 更新结果。
附运行时入口提示：`GameManager.start_new_game('<basename 不含 .json>', '<首场景段 id>')`。

## 参考文档

- 剧本格式与 manifest 映射：[00_init/剧本.md](../../../00_init/剧本.md)
- manifest 生成器：[99_game/tools/manifest_builder.py](../../../99_game/tools/manifest_builder.py)
- 剧情 Schema（Chapter/contains/depicts）：[00_init/Schema/剧情.md](../../../00_init/Schema/剧情.md)
