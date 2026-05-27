# 他者之镜Schema

## 节点类型（4种）

### 1. 人物（char）

最小粒度：每个有名字的真实人物。

| 字段 | 中文 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| id | 编号 | string | 是 | `char_001` |
| name | 姓名 | string | 是 | `陆择` |
| gender | 性别 | enum | 否 | `男` |
| description | 简介 | string | 否 | `星耀电竞战队队长，沉默寡言的天才选手` |
| birth_year | 出生年份 | int | 否 | `2003` |
| character_tags | 人设标签 | string | 否 | `沉默寡言, 外冷内热, 完美主义` |
| appearance | 外貌特征 | string | 否 | `182cm, 黑色短发, 琥珀色瞳, 偏瘦` |
| status | 流程状态 | int | 否 | `1` |
| art_design_path | 美术设定路径 | string | 否 | `05_角色设计/char/char_001/美术设定.md` |
| voice_style_path | 语言风格路径 | string | 否 | `05_角色设计/char/char_001/语言风格.md` |
| design_prompt_path | 设计图提示词路径 | string | 否 | `06_角色美术/char_001/设计图提示词.md` |
| stand_painting_prompt_path | 立绘提示词路径 | string | 否 | `06_角色美术/char_001/立绘/提示词.md` |
| design_image_path | 设计图图片路径 | string | 否 | `06_角色美术/char_001/设计图.png` |

**gender 枚举**：`男` / `女`

**status 枚举**：
- `0`: 初始（数据已导入）
- `1`: 角色设计完成（美术设定 + 语言风格已生成）
- `2`: 美术提示词完成（设计图 + 立绘提示词已生成）
- `3`: 图片生成完成（设计图 + 立绘图片已生成）

---

### 2. 地点（Location）

最小粒度：具体地点

| 字段 | 中文 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| id | 编号 | string | 是 | `loc_001` |
| name | 名称 | string | 是 | `重庆长江大桥` |
| description | 描述 | string | 否 | `横跨长江的公路铁路两用桥` |
| status | 流程状态 | int | 否 | `0` |

**location_level 枚举**：
- `城市`: 城市级地理范围
- `具体地点`: 具体的地点/建筑

**status 枚举**：
- `0`: 初始（数据已导入）
- `1`: 场景设计完成
- `2`: 场景美术完成

---

### 3. 信息（Info）

最小粒度：每条对读者有意义的新认知。一条信息 = 一个之前不知道的事实。

| 字段 | 中文 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| id | 编号 | string | 是 | `info_001` |
| title | 标题 | string | 是 | `胖猫曾向女友转账51万` |
| content | 内容 | string | 是 | `2023年至2024年间，胖猫通过微信和支付宝累计向女友转账约51万元` |
| knowledge_level | 知识层 | enum | 是 | `2` |

**knowledge_level 枚举**：
- `1`: 表层——新闻报道、警方通报等公开信息
- `2`: 参与层——需要阅读聊天记录、转账记录等细节才能了解的信息
- `3`: 深层——需要综合推断或获取非公开信息才能理解的隐性事实

---

### 4. 事件（Event）

最小粒度：某时某刻发生的某件事。一个事件 = 一个有明确时间点的具体动作或状态变化。

| 字段 | 中文 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| id | 编号 | string | 是 | `evt_001` |
| title | 标题 | string | 是 | `胖猫从重庆长江大桥跳江` |
| time | 时间 | Date | 是 | `2024-04-11` |
| description | 描述 | string | 否 | `凌晨4时许，胖猫独自前往重庆长江大桥跳江身亡` |
| type | 类型 | enum | 否 | `行动` |

**type 枚举**：
- `行动`: 具体的物理行为，如跳江、转账、报警
- `交流`: 对话、发帖、聊天记录等沟通行为
- `转折`: 改变事态走向的关键节点
- `状态变化`: 人物状态或关系状态的改变，如分手、确诊

---

## 边类型

### 一、人物关系（relation）

| 边 | 方向 | 属性 | 含义 |
|----|------|------|------|
| relation | char → char | type: string（如"恋爱""亲属""指控""报案"）<br>detail: string（如"恋爱中""已分手""姐弟"） | 人物间的关系 |

---

### 二、人物—地点（at）

| 边 | 方向 | 属性 | 含义 |
|----|------|------|------|
| at | char → Location | type: string（如"居住""前往"）<br>detail: string | 人物与地点的关联 |

---

### 三、信息关联（link）

| 边 | 方向 | 属性 | 含义 |
|----|------|------|------|
| link | 任意实体 → Info | type: string（如"涉及""因果"）<br>detail: string <br>time: Date | 信息关联 |

> type=`因果` 时仅用于 Info → Info，表示原因→结果。
> time是发生的时间

---

### 四、人物—事件（involved）

| 边 | 方向 | 属性 | 含义 |
|----|------|------|------|
| involved | char → Event | role: string（如"当事人""施害者""受害者""目击者""发布者"）<br>detail: string | 人物参与某事件 |

---

### 五、事件—地点（occurred_at）

| 边 | 方向 | 属性 | 含义 |
|----|------|------|------|
| occurred_at | Event → Location | detail: string（如"跳江地点""转账地点"） | 事件发生的地点 |

---

### 六、事件—事件（evt_relation）

| 边 | 方向 | 属性 | 含义 |
|----|------|------|------|
| evt_relation | Event → Event | type: string（如"因果""先后""包含"）<br>detail: string | 事件间的关联 |

> type=`因果`：前因→后果；type=`先后`：时间顺序；type=`包含`：大事件→子事件。

---

## ID 规则

| 节点类型 | ID 前缀 | 格式 | 示例 |
|---------|--------|------|------|
| 人物 | `char_` | `char_NNN` | `char_001` |
| 地点 | `loc_` | `loc_NNN` | `loc_001` |
| 信息 | `info_` | `info_NNN` | `info_001` |
| 事件 | `evt_` | `evt_NNN` | `evt_001` |

## 边汇总

| # | 边 | 从 → 到 | 属性 type/role 示例 |
|---|-----|---------|----------------|
| 1 | relation | char → char | 恋爱、亲属、指控、报案 |
| 2 | loc_link | char → Location | 居住、前往 |
| 3 | info_link | 任意 → Info | 涉及、因果 |
| 4 | involved | char → Event | 当事人、施害者、受害者、目击者 |
| 5 | occurred_at | Event → Location | 跳江地点、转账地点 |
| 6 | evt_relation | Event → Event | 因果、先后、包含 |
