---
name: infra-image-generator
description: |
  OfoxAI Images API 调用层。从图节点读取 prompt 字段调用 API 生成图片：
  DesignSheet（文生图）、IllusDesign（图生图）、StandingIllustration（图生图）。
  生成后设 approve='pending' 等待审批。在需要生成美术图片或被其他 skill 调用时使用。
argument-hint: <node_id>
arguments:
  - node_id
allowed-tools: Read, Bash, Write, Edit
---

# OfoxAI 图片生成

读取节点 `prompt` 字段和参考图路径，调用 API 生成图片。**不组装提示词，不读取风格文件。**

脚本：`${CLAUDE_SKILL_DIR}/scripts/ofoxai_api.py`

---

## API Key

脚本自动从**工作目录**向上搜索 `settings.json`，读取 `ofox_api_key` 字段。无需手动传参。

确保工作目录或其上级目录存在 `settings.json`：
```json
{ "ofox_api_key": "sk-of-xxxxx" }
```

---

## 流程

### 1. 确定目标节点

由调用方传入目标节点 ID（参数 `$0`）。通过 neo4j-helper 查询节点类型、状态和提示词：

```cypher
MATCH (n {id: $node_id})
RETURN labels(n)[0] AS type, n.status AS status,
       n.prompt AS prompt, n.image_path AS image_path
```

前置检查：status 必须为 1（提示词已由 prompt-assembler 组装完成），prompt 不为空。

### 2. 确定生成方式和参考图

| 节点类型 | 生成方式 | 参考图来源 |
|---------|---------|-----------|
| DesignSheet | 文生图 | 无 |
| IllusDesign | 图生图 | 上游 DesignSheet.image_path（`produces` 边） |
| StandingIllustration | 图生图 | 上游 IllusDesign.image_path（`expands_to` 边） |

图生图模式下，通过 neo4j-helper 查询上游节点的 `image_path` 作为 `--image` 参数。

### 3. 生成图片

> **`--size` 必须显式传入**。无法确定时向用户确认。

#### DesignSheet（文生图）

```bash
python "${CLAUDE_SKILL_DIR}/scripts/ofoxai_api.py" submit "<n.prompt>" --size 1024x1024 --quality low -o "./06_角色美术/<char_id>/设计图.png"
```

#### IllusDesign（图生图）

```bash
# 以 DesignSheet 图片为参考
python "${CLAUDE_SKILL_DIR}/scripts/ofoxai_api.py" submit "<n.prompt>" --image "<DesignSheet.image_path>" --size 1024x1024 --quality low -o "./06_角色美术/<char_id>/立绘设计/<costume_id>/设计图.png"
```

#### StandingIllustration（图生图）

```bash
# 以 IllusDesign 图片为参考
python "${CLAUDE_SKILL_DIR}/scripts/ofoxai_api.py" submit "<n.prompt>" --image "<IllusDesign.image_path>" --size 1024x1024 --quality low -o "./06_角色美术/<char_id>/立绘/<costume_id>/<variant_label>/立绘.png"
```

### 4. 更新图节点

通过 neo4j-helper 更新目标节点的 image_path、status 和 approve：

```cypher
MATCH (n {id: $node_id})
SET n.image_path = '<图片路径>', n.status = 2, n.approve = 'pending'
```

---

## 脚本参数

### submit

```bash
python "${CLAUDE_SKILL_DIR}/scripts/ofoxai_api.py" submit "<prompt>" [options]
```

| 参数 | 必填 | 说明 |
|------|:----:|------|
| prompt | Y | 图像描述文本（从节点 prompt 字段读取） |
| `--model` | N | 默认 `openai/gpt-image-2` |
| `--size` | Y | 输出尺寸，gpt-image-2 最大边 3840px，两边 16 的倍数 |
| `--quality` | - | **已强制为 `low`** |
| `--n` | N | 生成数量，默认 1 |
| `--image` | N | 参考图路径，可多次指定 |
| `-o, --output` | N | 直接保存路径（跳过 wait） |

### wait / download

```bash
python "${CLAUDE_SKILL_DIR}/scripts/ofoxai_api.py" wait '<json|file>' ./output.png
python "${CLAUDE_SKILL_DIR}/scripts/ofoxai_api.py" download <url> ./output.png
```

## 错误处理

| HTTP 状态码 | 处理 |
|-------------|------|
| 400 | 检查参数格式和尺寸 |
| 401 | 检查 API Key |
| 402 | 余额不足，充值后重试 |
| 429 | 等待后重试 |
| 500 | 重试 |

## 参考文档

- [完整 API 参数](references/api-reference.md)
