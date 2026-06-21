---
name: char-prompt-assembler
description: |
  从调用方传入的节点数据（设计元素 tags + 自由文本）组装图片生成提示词，派生为 prompt 文件并返回其路径。
  三种模式：DesignSheet（文生图）、IllusDesign（图生图）、StandingIllustration（图生图）。
  纯产出层：不读写图数据库、不写 status，所有数据由调用方通过 data 参数提供。
  在需要为美术节点组装提示词或被其他 skill 调用时使用。
argument-hint: <mode> <data_json>
arguments:
  - mode
  - data
allowed-tools: Read, Bash, Write, Edit
---

> **纯产出层**：本 skill 只负责组装 prompt 文件并**返回文件路径**，**不读写图数据库、不写 status**。节点 `prompt_path` 字段与 `status` 由调用方（生产 skill）在「保存结果」步统一写入。`status=-1`（作废重做）时调用方会再次调用本 skill 覆盖旧 prompt 文件——本 skill 每次被调用都重新组装并覆盖。

# 提示词组装

从调用方传入的**设计元素 tags + 自由文本**组装图片生成提示词，派生为 **prompt 文件**并返回文件路径。不读写图数据库——所有数据由调用方通过 `data` 参数传入。

## 核心转换：tags → 自然语言

数据节点的可枚举维度以**标签**形式存储（分号 `;` 分隔，受控词表见 `55_dashboard/config/标签库.json`）。组装时将每个标签展开为**自然语言描述句**，与自由文本字段一起，按 reference 模板的 markdown 结构组织成完整 prompt。

**复合字段**（eye/hair/garment）的值已是**合成组合描述**（如 `琥珀色上挑眼`、`深棕色大波浪长发`、`棉衬衫`），直接作为该维度的自然语言使用，无需再展开子维度。

- 标签 `hair_color=黑;挑染银` → "黑色长发，发丝间挑染银色"
- 标签 `garment="棉白衬衫"` → "白色棉质衬衫"
- 标签 `hand=叉腰` + `foot=前后开立` → "一手叉腰，双脚前后开立"

## 编写原则

- **标签展开为完整描述句**：转为自然语言（写"黑色长发"而非"hair_color:黑"）
- **主体 → 细节 → 风格**：先写主体，再补细节，画风放末尾
- **中文提示词**，按 reference 模板的 markdown 结构（标题/编号）组织
- **只提取不创作**：内容来自 data 参数（tags + 自由文本）和 `00_init/美术风格.md`，不臆造
- **去重不矛盾**：同维度的信息只在 tags 中表达一次（服装款式/颜色/材质统一在 `garment` 标签），避免提示词出现重复或矛盾描述

## 输出流程（三种模式通用）

1. 解析 data，提取 tags（分号分隔串，需 split）、自由文本字段，以及 `character.name` 与 `node.id`
2. 从 `00_init/美术风格.md` 读取全局风格参数（背景色、线条、上色、色调等）
3. 按模式规则组装 markdown prompt（见下方各模式 + reference 模板的维度结构）
4. 用 **Write 工具**写 prompt 文件到 `06_角色美术/<char_name>/prompts/<node_id>.md`（不经 shell，markdown 无损；目录不存在时 Write 自动创建）
5. **返回 prompt 文件路径**给调用方（由调用方写入节点 `prompt_path` 字段）

> prompt 文件按节点 id 命名（`prompts/<node_id>.md`），每个节点独立，避免同一角色多个节点互相覆盖。

## 模式A：DesignSheet（文生图）

为三视图设计稿组装提示词。聚焦角色外貌，不涉及衣着——角色统一穿着深色基础衣物（黑色贴身背心+深色短裤），与肤色形成高对比。详细维度映射见 [references/template-设计图提示词.md](references/template-设计图提示词.md)。

**data 参数结构**：
```json
{
  "appearance": {
    "tags": {"shape_language":"...","age_impression":"...","body_type":"...","skin_tone":"...","hair":"...","eye":"...","lip_shape":"...","marks":"..."},
    "appearance":"...(自由文本:综合气质/身高)","visual_tone":"...","first_impression":"..."
  },
  "character": {"id":"<char_id>","name":"...","color_direction":"...(自由文本:配色逻辑)"},
  "node": {"id":"<designsheet_node_id>"}
}
```

组装：从 `appearance.tags` 展开各维度（体态/肤色/发长发型发色/眼型瞳色/唇形/特殊标记）为自然语言，结合 `appearance` 自由文本（综合气质、身高）与 `character.color_direction`（配色逻辑），加贴身基础衣物说明，画风放末尾。

## 模式B：IllusDesign（图生图）

为着装适配立绘设计图组装提示词。聚焦着装描述，不重复角色外貌（图生图以 DesignSheet 为参考底图，外貌已在底图）。详细维度映射见 [references/template-着装提示词.md](references/template-着装提示词.md)。

**data 参数结构**：
```json
{
  "costume": {
    "tags": {"outfit_style":"...","garment":"...","footwear":"...","accessory_type":"..."}
  },
  "illus": {"adaptation_notes":"...(可选)"},
  "character": {"id":"<char_id>","name":"..."},
  "node": {"id":"<illusdesign_node_id>"}
}
```

组装：从 `costume.tags` 展开着装（风格/材质+颜色+类型/鞋/配饰）为自然语言，加 `adaptation_notes` 适配补充（无则跳过），画风放末尾。

## 模式C：StandingIllustration（图生图）

为立绘表情变体组装提示词。描述全身立绘的表情与动作。详细规则见 [references/template-立绘提示词.md](references/template-立绘提示词.md)。

**data 参数结构**：
```json
{
  "stand": {
    "tags": {"variant_label":"...","eye":"...","brow":"...","mouth":"...","head_angle":"...","hand":"...","foot":"..."}
  },
  "voice": {"emotion_patterns":"...","description":"..."},
  "character": {"id":"<char_id>","name":"..."},
  "node": {"id":"<standing_node_id>"}
}
```

组装：固定前缀 `[角色名]立绘，[背景色]背景，全身像，`，从 `stand.tags` 展开表情（eye/brow/mouth/head_angle）与动作（hand/foot）为自然语言，结合 `voice.emotion_patterns` 补充情绪，画风放末尾。

## 参考文档

- [设计图提示词模板](references/template-设计图提示词.md) — 维度结构与编写要点（模式A）
- [着装提示词模板](references/template-着装提示词.md) — 维度结构与编写要点（模式B）
- [立绘提示词模板](references/template-立绘提示词.md) — 表情+动作要素与变体规则（模式C）

> 模板文件的**维度结构**有效，但数据源以本文件各模式的 data 结构（tags + 自由文本）为准。
