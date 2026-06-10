---
name: char-prompt-assembler
description: |
  从调用方传入的节点数据组装图片生成提示词，写入节点 prompt 字段。
  三种模式：DesignSheet（文生图）、IllusDesign（图生图）、StandingIllustration（图生图）。
  不读取图数据库，所有数据由调用方通过 data 参数提供。
  在需要为美术节点组装提示词或被其他 skill 调用时使用。
argument-hint: <node_id> <mode> <data_json>
arguments:
  - node_id
  - mode
  - data
allowed-tools: Read, Bash, Write, Edit
---

# 提示词组装

按模板规则组装图片生成提示词，写入节点 `prompt` 字段。**不读取图数据库**——所有数据由调用方通过 `data` 参数传入。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| node_id | 目标节点 ID（如 `design_001`、`illus_001`、`stand_001`） | 必传 |
| mode | 模式：`DesignSheet`、`IllusDesign`、`StandingIllustration`。不传则根据 node_id 自动判断 | 自动 |
| data | JSON 字符串，包含调用方查询到的节点属性数据 | 必传 |

## 编写原则

- **自然语言优先**：用完整描述性语句，不用逗号分隔关键词
- **主体 → 细节 → 风格**：先写主体，再补细节，风格放末尾
- **不使用负面提示词**
- **中文提示词**
- **只提取不创作**：所有内容来自 data 参数和风格文件，不臆造

## 模式A：DesignSheet（status 0→1，文生图提示词）

为三视图设计稿组装提示词。**聚焦角色外貌，不涉及衣着设计**——角色统一穿着深色基础衣物（如黑色贴身背心+深色短裤），与肤色形成高对比，衣着由后续 IllusDesign（模式B）专门处理。详细提取映射和模板见 [references/template-设计图提示词.md](references/template-设计图提示词.md)。

**data 参数结构**：
```json
{
  "appearance": { "appearance": "...", "color_direction": "...", "shape_language": "...", "visual_tone": "...", "first_impression": "...", "memory_points": "..." },
  "character": { "id": "char_NNN", "name": "..." }
}
```

1. 解析 data 参数，提取 appearance 和 character 数据
2. 从 `00_init/美术风格.md` 读取全局风格参数
3. 前置检查：AppearanceStyle.status ≥ 1
4. 按 **主体→细节→风格** 组装提示词：
   - 开头声明：角色设计图，[从美术风格.md 读取背景色]背景，全身三视图（正面、侧面、背面）
   - 体型：从 appearance.appearance 提取
   - 面部：从 appearance.appearance 提取
   - 发型：从 appearance.appearance 提取
   - 贴身基础衣物：统一穿着深色基础衣物（如黑色贴身背心+深色短裤），与肤色形成高对比，不涉及服装设计细节
   - 配色：从 appearance.color_direction 提取（仅用于发色、瞳色、肤色等外貌配色）
   - 特殊标记：从 appearance.appearance 提取（疤痕、纹身、胎记等身体标记）
   - 记忆点：从 appearance.memory_points 强调
   - 风格标签：从 美术风格.md 提取，放末尾
5. 通过 neo4j-helper 更新 DesignSheet 节点：`prompt = <提示词>`，`status = 1`

## 模式B：IllusDesign（status 0→1，图生图提示词）

为着装适配立绘设计图组装提示词。**聚焦着装描述，不重复角色外貌**（图生图以 DesignSheet 为参考底图，外貌已在底图中）。详细提取映射和模板见 [references/template-着装提示词.md](references/template-着装提示词.md)。

**data 参数结构**：
```json
{
  "costume": { "default_outfit": "...", "material_direction": "...", "posture": "...", "accessories": "..." },
  "illus": { "adaptation_notes": "..." },
  "character": { "id": "char_NNN", "name": "..." }
}
```

1. 解析 data 参数，提取 costume、illus 和 character 数据
2. 从 `00_init/美术风格.md` 读取全局风格参数
3. 前置检查：DesignSheet.status ≥ 1（提示词已就绪）
4. 组装提示词：
   - 着装描述：从 costume.default_outfit 提取款式层次+剪裁+面料+细节，从 accessories 提取配饰，从 material_direction 提取材质方向
   - 适配说明：从 illus.adaptation_notes 提取着装补充（由 char-illus-designer skill 在创建节点时填写，可选，如无则跳过）
   - 风格标签：从 美术风格.md 提取，放末尾
5. 通过 neo4j-helper 更新 IllusDesign 节点：`prompt = <提示词>`，`status = 1`

## 模式C：StandingIllustration（status 0→1，图生图提示词）

为立绘表情变体组装提示词。提示词描述全身立绘，包含表情、手部动作和脚部动作。详细描述规则见 [references/template-立绘提示词.md](references/template-立绘提示词.md)。

**data 参数结构**：
```json
{
  "stand": { "variant_label": "..." },
  "voice": { "emotion_patterns": "...", "description": "..." },
  "character": { "id": "char_NNN", "name": "..." }
}
```

1. 解析 data 参数，提取 stand、voice 和 character 数据
2. 从 `00_init/美术风格.md` 读取全局风格参数
3. 前置检查：IllusDesign.status ≥ 1
4. 组装提示词：
   - 固定格式：`[角色名]立绘，[从美术风格.md 读取背景色]背景，全身像，`
   - 表情：提取面部表情描述（眼部、眉毛、嘴部、面部肌肉、头部角度）
   - 手部动作：根据变体类型推导手部姿态（如双手叉腰、单手持物、握拳、自然垂放等）
   - 脚部动作：根据变体类型推导脚部姿态（如双脚并拢、前后开立、单脚微抬等）
   - 情绪参考：从 voice.emotion_patterns 补充情绪表达
   - 风格标签：从 美术风格.md 读取
5. 通过 neo4j-helper 更新 StandingIllustration 节点：`prompt = <提示词>`，`status = 1`

## 参考文档

- [设计图提示词模板](references/template-设计图提示词.md) — 外貌提取映射、输出模板、编写要点（模式A）
- [着装提示词模板](references/template-着装提示词.md) — 着装提取映射、输出模板、编写要点（模式B）
- [立绘提示词模板](references/template-立绘提示词.md) — 表情+动作描述要素、变体规则、编写要点（模式C）
