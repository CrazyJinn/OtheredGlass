# 他者之镜 - 游戏开发流程图

---

## 1. 叙事数据打磨流程 (剧本 → 图数据库)

> 反复迭代：撰写剧本 → 提取结构化数据 → 导入图数据库 → 审查 → 补充/修改 → 再次提取。

```mermaid
sequenceDiagram
    participant Input as 创作输入层
    participant Ext as [Skill] 事件提取器
    participant Rev as [人工] 审核
    participant Help as [Skill] Neo4j Helper
    participant Neo as [图] Neo4j
    participant Cre as [Skill] 创作 Skill

    Input->>Ext: 世界观 / 角色设定 / 事件 / 场景 + Schema
    Ext-->>Rev: 实体.md + entities.csv + relations.csv
    Rev->>Help: 审核通过
    Help->>Neo: import.cypher
    Neo->>Cre: 图结构数据
    Cre-->>Input: 剧情建议 / 角色互动 / 支线事件 / 场景扩展
    Cre-->>Help: 新发现实体 / 关系 (自增长)
    Note over Cre,Help: 知识自增长循环
```


## 2. 游戏开发流程 (图数据已就绪)

---

> 前提：Neo4j 中已有完整的叙事数据（角色、事件、场景、章节等），开发流程从此开始。

```mermaid
%%{init: {'flowchart': {'nodeSpacing': 50, 'rankSpacing': 80, 'curve': 'basis', 'htmlLabels': true}, 'themeVariables': {'nodeTextAlignment': 'center', 'subGraphTitleFontWeight': 'bold'}}}%%
flowchart TB
    %% ========== 数据源 ==========
    neo[("Neo4j 数据就绪")]

    %% ========== 叙事设计 ==========
    subgraph nar["叙事设计 [图]"]
        O_nar1[叙事节奏.md]
        O_nar2[角色声线.md]
    end

    %% ========== 角色设计 ==========
    subgraph char["角色设计 [图]"]
        O_char1[角色美术设定.md]
        O_char2[角色语言风格.md]
    end

    %% ========== 美术提示词 ==========
    subgraph artp["美术提示词"]
        O_artp1[设计图提示词.md]
        O_artp2[立绘提示词.md]
    end

    %% ========== 场景设计 ==========
    subgraph scened["场景设计 [图]"]
        O_scened1[游戏场景.md]
        O_scened2[对话背景.md]
        O_scened3[UI背景.md]
    end

    %% ========== 剧本组装 ==========
    subgraph script["剧本组装 [图]"]
        O_script[剧本.json]
    end

    %% ========== 解决方案设计 ==========
    subgraph sol["解决方案设计 [图]"]
        O_sol1[需求分析文档]
        O_sol2[测试用例设计]
    end

    %% ========== 文生图 ==========
    subgraph t2i["文生图 (api)"]
        O_t2i1[角色设计图.png]
        O_t2i2[场景装饰.png]
        O_t2i3[对话背景.png]
        O_t2i4[UI背景.png]
    end

    %% ========== 图生图 ==========
    subgraph i2i["图生图 (api)"]
        O_i2i1[立绘.png]
        O_i2i2[过场.png]
    end

    %% ========== 装饰裁剪 ==========
    subgraph deco["装饰裁剪"]
        O_deco[装饰切片.png]
    end

    %% ========== 音频实现 ==========
    subgraph audio["音频实现"]
        O_audio1[BGM.mp3]
        O_audio2[音效.mp3]
    end

    %% ========== 代码生成 ==========
    subgraph code["代码生成"]
        O_code[游戏代码]
    end

    %% ========== 资源搬运 ==========
    subgraph xfer["资源搬运"]
        O_xfer[assets目录]
    end

    %% ========== 游戏组装 ==========
    subgraph final["游戏组装 (人工)"]
        O_final[游戏成品]
    end

    %% ========== 连线 ==========
    neo --> nar
    neo --> char
    neo --> scened
    neo --> sol
    neo --> audio
    O_char1 & O_char2 --> artp
    O_nar1 --> script
    O_artp1 --> t2i
    O_artp2 --> t2i
    O_artp2 --> i2i
    O_scened1 & O_scened2 & O_scened3 --> t2i
    O_t2i1 --> i2i
    O_t2i2 --> deco
    O_sol1 & O_sol2 --> code
    O_t2i1 & O_t2i2 & O_t2i3 & O_t2i4 & O_i2i1 & O_i2i2 & O_deco & O_audio1 & O_audio2 --> xfer
    O_xfer & O_code & O_script --> final

    %% ========== 样式 ==========
    classDef neo4j fill:#e3f2fd,stroke:#1565c0,stroke-width:3px,color:#0d47a1
    classDef manual fill:#ffebee,stroke:#c62828,stroke-width:3px,color:#000
    classDef auto fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#000
    classDef graphSkill fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000

    class neo neo4j
    class final manual
    class artp,t2i,i2i,deco,code,xfer auto
    class nar,char,scened,script,sol,audio graphSkill
```

### Neo4j 数据中枢 (mindmap)

> 下方独立展示 Neo4j 作为结构化数据中枢的角色：哪些 Skill 向图写入，哪些从图读取。

```mermaid
mindmap
  root((Neo4j Helper))
    写入
      来自创作输入层
        世界观 / 角色设定 / 事件 / 场景 + Schema
        → 事件提取器 → 人工审核 → import.cypher
      来自创作 Skill
        新发现实体 / 关系 (自增长回流)
    存储
      Character · 角色属性/性格/标签
      Location · 地点/级别
      Event · 事件类型/时间/因果链
      Info · 信息/知识层级
      Location · 场景边界/环境叙事
      Chapter · 章节结构/时序
    查询
      叙事设计
        关系图 · 事件链 · 信息层级 · 场景序列
      角色设计
        角色属性 · 关系 · 标签 · 参与事件
      场景设计
        Location 节点 · 环境叙事属性
      剧本组装
        Chapter / Location / Event 层次结构
```

---

## 图例说明

| 样式 | 含义 |
|------|------|
| 蓝色节点 + [图] 标记 | 从 Neo4j 读取结构化数据的 Skill |
| 绿色节点 | Skill 自动完成 |
| 红色节点 | 人工完成 |
| 虚线箭头 | 迭代回溯（审查后返回修改） |

---


## Skill 说明

### 叙事数据打磨阶段 (图1)

| Skill | 说明 |
|-------|------|
| **事件提取器** | 从创作输入提取实体/关系，输出实体.md + entities.csv + relations.csv |
| **人工审核** | 审核提取结果，通过或驳回修改 |
| **Neo4j Helper** | 汇总所有读写操作，去重/合并/补全后生成 Cypher，写入图数据库 |
| **创作 Skill** | 基于图数据推理，生成剧情建议/角色互动/支线事件/场景扩展，自增长回流新实体和关系 |

### 游戏开发阶段 (图2)

| Skill | 说明 |
|-------|------|
| **叙事设计** | 查询关系图/事件链/信息层级/场景序列 → 叙事节奏.md、角色声线.md |
| **角色设计** | 查询角色属性/关系/标签/参与事件 → 角色美术设定.md、角色语言风格.md |
| **场景设计** | 查询 Location 节点环境叙事属性 → 游戏场景.md、对话背景.md、UI背景.md |
| **剧本组装** | 查询 Chapter/Location/Event 层次结构 → 剧本.json |
| **解决方案设计** | 基于代码需求进行技术方案分析 → 需求分析文档、测试用例设计 |
| **美术提示词** | 根据角色美术设定 → 设计图提示词.md、立绘提示词.md |
| **文生图 (api)** | 调用 seedream API → 角色设计图/场景装饰/对话背景/UI背景 .png |
| **图生图 (api)** | 调用 seedream API → 立绘.png、过场.png |
| **装饰裁剪** | 切割宫格图片 → 装饰切片.png |
| **音频实现** | 根据音频需求 → BGM.mp3、音效.mp3 |
| **代码生成** | 根据需求分析文档 → 游戏代码 |
| **资源搬运** | 将终稿资源同步到 assets 目录 |
| **游戏组装** | 将剧本、代码、资源组装为游戏成品 |

---

## 项目文件夹结构

```
他者之镜/
├── 00_init/                          # 创作输入层 (图1)
│   ├── 游戏概览.md
│   ├── 世界设定.md
│   ├── 剧本大纲.md
│   ├── 人物设定.md
│   └── Schema.md                     # Neo4j Schema 规则
│
├── 01_叙事数据/                      # 事件提取器产出 (图1)
│   ├── 实体/
│   │   ├── 角色实体.md
│   │   ├── 事件实体.md
│   │   └── 地点实体.md
│   ├── entities.csv
│   └── relations.csv
│
├── 05_角色设计/                      # 角色设计 [图] (图2)
│   ├── 角色设计总览.md
│   └── char/
│       └── char_001/
│           ├── 美术设定.md
│           └── 语言风格.md
│
├── 06_角色美术/                      # 美术提示词 + 文生图 + 图生图
│   ├── 角色美术总览.md
│   └── char_001/
│       ├── 设计图提示词.md
│       ├── 设计图.png
│       └── 立绘/
│           ├── 立绘提示词.md
│           └── *.png
│
├── 10_场景设计/                      # 场景设计 [图] (图2)
│   ├── 场景设计总览.md
│   ├── 游戏场景/
│   │   └── scene_xxx_场景名/
│   │       ├── 概览.md
│   │       └── room_xxx_房间名/
│   │           └── 提示词.md
│   ├── 对话背景/
│   │   └── dialog_xxx_场景名/
│   │       └── 提词.md
│   └── UI背景/
│       └── ui_xxx_界面名/
│           └── 提示词.md
│
├── 11_场景美术/                      # 文生图产出 + 装饰裁剪
│   ├── 场景美术总览.md
│   ├── 游戏场景/
│   │   └── scene_xxx_场景名/
│   │       └── room_xxx_房间名/
│   │           ├── 场景装饰.png
│   │           └── 装饰切片/
│   │               └── *.png
│   ├── 对话背景/
│   │   └── *.png
│   └── UI背景/
│       └── *.png
│
├── 15_叙事设计/                      # 叙事设计 [图] (图2)
│   ├── 叙事节奏.md
│   └── 角色声线.md
│
├── 20_剧本/                          # 剧本组装 [图] (图2)
│   ├── 剧本总览.md
│   ├── 剧本.json
│   └── 章节/
│       └── 第一章.md
│
├── 25_解决方案设计/                  # 解决方案设计 [图] (图2)
│   ├── 需求分析文档.md
│   └── 测试用例设计.md
│
├── 30_音频/                          # 音频实现 (图2)
│   ├── BGM/
│   └── 音效/
│
├── 89_game/                          # 代码生成 + 资源搬运 + 游戏组装
│   └── AllCooper/
│       ├── project.godot
│       ├── scenes/
│       ├── scripts/
│       ├── assets/
│       │   ├── sprites/
│       │   ├── backgrounds/
│       │   ├── ui/
│       │   └── audio/
│       └── addons/
│
├── 99_流程管理/
│
└── .claude/skills/
```