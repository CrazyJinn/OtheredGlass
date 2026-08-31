# 《代恋》Godot 框架设计（V1）

- 日期：2026-07-11
- 状态：已通过 brainstorming，待编写实现计划
- 输出根目录：`99_game/`
- 依据：`00_init/剧本.md`、`00_init/剧本.schema.json`、`00_init/游戏概览.md`、`00_init/大纲.md`

---

## 1. 背景与目标

《代恋》是 2D 剧情向视觉小说（Galgame）。本 V1 的目标：在 `99_game/` 下产出一个**可运行的 Godot 工程框架**，完整消费 `剧本.md` 定义的纯 JSON 剧本格式（以 `剧本.schema.json` 为权威），用现成示例剧本 `chapter01_新皮肤.json` 跑通整条管线：

> 读 JSON → 结构校验 → 解释器逐条执行 → 立绘/背景/BGM 演出 → choice/jump 分支跳转 → ending 结局。

**不做的事**：不生成新剧情对话；不生产真实美术资源；不实现 V1 边界外的系统。

---

## 2. 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 技术栈 | Godot 4.3+ | 对齐文档"引擎=Godot"。**约束：本会话环境（Windows bash）无 Godot CLI，工程无法在此运行验证；用户需在 Godot 编辑器中导入测试。** |
| 范围 | 仅框架 + 现成示例剧本 | 用 `剧本.md` 中 `chapter01_新皮肤.json` 节选验证管线，最快达成"可玩可验收"。 |
| 美术 | 全部程序占位图 | 不依赖 `06_/07_` 现有设计图，管线最干净；换真图只改 manifest。 |
| 架构 | 集中式解释器（方案 A） | V1 状态简单、指令少；状态集中、跳转寻址一处实现、好测试。 |

目标分辨率：**1536 × 1024（3:2）**；角色对话立绘 **400 × 800**。

---

## 3. V1 范围边界（严格对齐 `剧本.md` 的 V1 边界）

**含**：
- 章节 → 场景段 → 指令序列结构；11 条指令（say/narrate/show/hide/bg/bgm/sfx/choice/label/jump/ending）全实现。
- `say` 必带立绘 + `pos` 累积维持；`meta.requires`；manifest 资源映射。
- 跳转寻址（`to` / `scene` / `file` 三层组合）。
- 场景段切换自动套用其 `scene`（背景）+ `bgm`。
- 程序占位图（立绘/场景/头像）。
- 标题/主菜单、对话框（对话布局 + 独白布局）、选择面板、对话历史 Log、系统菜单（存档/读档/设置/返回标题）。
- 存档：quick 槽（F5/F9）+ auto + 手动多槽；选择点前与场景段头自动写 quick。
- 键位/设置核心项。

**不含（YAGNI）**：变量/flag、条件分支（`if`）、特效（wait/shake/flash）、独立 CG 指令（结局 `cg` 字段除外）、多图层场景、时段驱动背景变体、配音、CG鉴赏/回想、跳过未读、手柄。

---

## 4. 架构：集中式剧本解释器

`ScriptInterpreter`（autoload 单例）持有全部运行时状态，用 `match op` 分发指令；`Game.tscn` 纯做渲染，订阅解释器信号更新画面。

备选方案已排除：**方案 B**（命令模式，每 op 一个 Command 类）对 V1 过度设计；**方案 C**（Dialogic 等社区插件）格式不兼容纯 JSON，违背核心要求。

### 4.1 目录结构

```
99_game/
├─ project.godot                  # 工程配置 + autoload 注册
├─ README.md                      # 打开/运行/验证步骤、资源缺口说明
├─ scripts/
│  ├─ autoload/
│  │  ├─ GameManager.gd           # 全局流程：标题↔游戏↔结局；设置/键位
│  │  ├─ ScriptInterpreter.gd     # ★ 核心剧本解释器
│  │  ├─ AudioManager.gd          # bgm play/stop/fade、sfx
│  │  └─ SaveManager.gd           # 选择点/场景段头自动存档 + 手动槽
│  ├─ data/
│  │  ├─ Manifest.gd              # 加载 manifest.json：逻辑名→资源路径
│  │  └─ ChapterLoader.gd         # 加载/缓存章节 JSON + 基本结构校验
│  ├─ ui/
│  │  ├─ DialogueBox.gd           # 头像/名称/打字机/继续指示
│  │  ├─ PortraitLayer.gd         # 左中右立绘累积管理 + 入离场
│  │  ├─ ChoiceMenu.gd            # 选项面板
│  │  ├─ Backlog.gd               # 对话历史 Log（H/滚轮）
│  │  └─ SystemMenu.gd            # 存档/读档/设置/返回标题
│  └─ util/
│     └─ PlaceholderGen.gd        # 程序占位图生成（立绘/场景/头像）
├─ scenes/
│  ├─ Title.tscn                  # 标题/主菜单
│  ├─ Game.tscn                   # 背景层+立绘层+对话框+选项层
│  ├─ Settings.tscn
│  └─ Ending.tscn                 # BE/TE/HE/NE 结局画面
├─ data/
│  ├─ chapters/chapter01_新皮肤.json   # 现成示例剧本
│  ├─ manifest.json               # 逻辑名→占位资源映射
│  └─ 剧本.schema.json            # 复制 schema，作离线校验参考
├─ assets/
│  ├─ portraits/ scenes/ bgm/ sfx/ cg/ ui/   # 运行时占位资源
└─ saves/                         # 存档目录（运行时生成）
```

### 4.2 指令执行模型

指令指针 = `{file, scene_idx, line_idx}`。`advance()` 执行当前 line：

| 类别 | 指令 | 行为 |
|------|------|------|
| 阻塞 | `say` / `narrate` / `choice` | 发信号给 UI，**停指针等输入**；玩家点击/选择后 `line_idx++` 继续 |
| 即时 | `show` / `hide` / `bg` / `bgm` / `sfx` | 立即执行副作用并**自动递进** |
| 标记 | `label` | 记录锚点位置，递进 |
| 流程 | `jump` | `resolve_target` 后移指针 |
| 终止 | `ending` | 发 `ended(kind,title,cg)` 信号，GameManager 切 Ending 场景 |

`advance()` 内对即时指令循环递进，直到撞上阻塞/终止指令才把控制权交还 UI。

**章节/段结束边界**：当某段 `lines` 执行到末尾（`line_idx` 越界）而无 `jump`/`ending` 时，视为章节结束——`GameManager` 切回标题场景并提示"章节结束"。这是 V1 的明确终态，不静默卡死。

### 4.3 跳转寻址 `resolve_target(to, scene, file)`

choice 选项与 jump 共用此逻辑：

1. 有 `file` → `ChapterLoader` 切换章节（已加载的章节缓存复用）。
2. 有 `scene` → 在目标章节按 `id` 定位 `scene_idx`，`line_idx = 0`。
3. 有 `to` → 在目标段内线性扫描 `label.name`，定位其 `line_idx`。
4. 任一定位失败 → `push_error` 停机（V1 不做容错回退，开发期尽早暴露）。

### 4.4 立绘累积与场景段切换

- 立绘槽：`slots = {left: null, center: null, right: null}`。
- `say` / `show`：`slots[pos] = {who, portrait}`。
- `hide`：遍历三槽按 `who` 匹配置空。
- `narrate` / `bg`：不动槽位（维持画面）。
- 每次变更发 `portrait_changed(全槽快照)`，`PortraitLayer` 重绘；独白用 `center`、对话分列 `left`/`right`。
- 进入任意场景段：自动套用其 `scene`（经 Manifest → 背景图）+ `bgm`（AudioManager）。

---

## 5. 子系统

### 5.1 程序占位图（PlaceholderGen）

- **立绘**：400×800，纯绿底（`#00FF00`，对齐文档 chroma key）+ 居中标注 `` `who.portrait` ``。
- **头像**：取立绘顶部方形区域裁切 + 角色名。
- **场景**：1536×1024，渐变底 + 居中 `` `场景：scene` ``。
- **策略**：按需生成 + 缓存。首次引用某逻辑名时生成 PNG 写入 `assets/`，之后直接读文件；换真图只改 manifest 路径。

### 5.2 manifest 与 ChapterLoader

`manifest.json` 把逻辑名映射到资源路径（示例剧本所需）：

```json
{
  "portraits": {
    "陈默.沉重": "assets/portraits/陈默.沉重.png",
    "陈默.释然": "assets/portraits/陈默.释然.png",
    "陈默.疲惫": "assets/portraits/陈默.疲惫.png"
  },
  "scenes": {
    "长江大桥-栏杆": "assets/scenes/长江大桥-栏杆.png",
    "出租屋": "assets/scenes/出租屋.png"
  },
  "bgm": { "夜风": "assets/bgm/夜风.ogg" },
  "sfx": {},
  "cg": {}
}
```

- `ChapterLoader`：读 `.json` → `JSON.parse` → 基本结构校验（`meta`/`scenes`/每 line 的 `op`）→ 缓存。完整 JSON Schema 校验留作离线（Godot 无内置），运行时信任。
- 资源缺失容错：图片/音频文件不存在时，图片 fallback 到占位图、音频 `push_warning` 后静默跳过，**不阻塞管线**。

### 5.3 存档（SaveManager）

- V1 无变量无 flag → 存档状态 = `{file, scene_id, line_idx, slots, bg_scene, bgm_track}`。
- 自动：进入选择点前、进入场景段头时写 quick 槽。
- 手动：SystemMenu 提供 9 手动槽 + quick + auto。
- 序列化为 JSON 写入 `saves/`。

### 5.4 键位与设置（对齐 `游戏概览.md`）

| 操作 | 键 |
|------|----|
| 推进对话 | 鼠标左键 / 空格 / 回车（文字未播完时点击立即显示全句） |
| 呼出菜单 | 鼠标右键 / ESC |
| 对话历史 | H / 滚轮上 |
| 快速存读档 | F5 / F9 |
| 自动播放 | A |
| 跳过 | S |
| 快进（已读） | Ctrl 按住 |

设置项：文字速度、自动播放间隔、BGM/SE/语音音量、全屏/窗口。核心（推进/菜单/Log/快存读档）实装；**自动/跳过/快进 V1 不区分"已读"**（V1 不跟踪已读历史），统一按设定速率加速推进——开关与音量档位实装，已读判定留待后续。

### 5.5 音频（AudioManager）

`bgm` 指令的 `mode`：`play` / `stop` / `fade`；`loop` 缺省 true。`sfx` 一次性播放。文件缺失静默跳过。

---

## 6. 验证步骤（写入 README，因本环境无 Godot）

1. 安装 Godot 4.3+，导入 `99_game/` 工程。
2. F5 从标题 → 开始游戏 → 进入 `chapter01_新皮肤.json`。
3. **分支验收**：桥上 `say`（陈默.沉重 center）→ `narrate` → `choice`：
   - 选"跳下去" → jump 到 `结局_BE` 段 → `ending(BE)` 进结局画面；
   - 选"再想想" → 经 `label keepgoing` → `say`（陈默.释然）→ `jump` 到 `回出租屋` 段 → 继续。
4. **立绘累积验收**：`narrate` 维持画面；不同 `pos` 累积；`hide` 移除。
5. **场景段切换验收**：进段自动换背景 + BGM。
6. **离线 schema 校验**：`ajv validate -s 00_init/剧本.schema.json -d 99_game/data/chapters/chapter01_新皮肤.json` 或 `python -m jsonschema` 应通过。

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 本环境无法运行 Godot，工程未经运行验证 | 代码尽量自洽；README 给出明确验收点；示例剧本已过 schema，逻辑可静态推导 |
| 中文文件名/逻辑名在 Godot 资源路径下的兼容性 | 资源用中文文件名（Godot 4 支持），但脚本/类名用 ASCII；运行时按字符串键读取，不依赖节点路径推断 |
| 占位图与未来真图的替换摩擦 | manifest 单点映射，换图不动剧本、不重编译 |

---

## 8. 后续（非本 V1）

- 扩 `set` / `if` 指令支持 flag/好感度分支（当大纲推进到需要时）。
- 接入真实美术生产链产物自动生成 manifest。
- 多图层场景（functional / combat）、时段驱动背景变体。
- 完整 CG鉴赏/回想、配音、手柄。
