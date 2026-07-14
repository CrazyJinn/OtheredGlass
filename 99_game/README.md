# 他者之镜（OtheredGlass）— Godot 工程

2D Galgame 框架。集中式 `ScriptInterpreter` 解释器消费纯 JSON 剧本（`data/chapters/*.json`，格式见 `data/剧本.schema.json`），经 `data/manifest.json` 把逻辑名映射到资源；美术全部程序占位。本工程含一个现成示例剧本 `chapter01_新皮肤.json` 用于跑通管线。

> 剧情格式权威定义：`00_init/剧本.md` + `00_init/剧本.schema.json`（本工程 `data/剧本.schema.json` 为其字节副本）。

## 架构
- `scripts/autoload/ScriptInterpreter.gd` ★ 剧本解释器（执行循环 / 11 指令分发 / 跳转寻址 / 立绘槽 / 存档快照）。
- `scripts/autoload/GameManager.gd` 全局流程 + InputMap 代码注册（无 `project.godot` `[input]` 段）。
- `scripts/autoload/AudioManager.gd` / `SaveManager.gd` 音频 / 存档。
- `scripts/data/` Manifest、ChapterLoader；`scripts/util/PlaceholderGen.gd` 占位图。
- `scripts/ui/` DialogueBox / PortraitLayer / ChoiceMenu / Backlog / SystemMenu / SettingsPanel（均代码动态构建）。
- `scenes/` Title / Game / Ending（`.tscn` 仅根节点 + attach 脚本）。

## 打开 / 运行
1. 安装 **Godot 4.3+**（4.4 亦可，仅 `Image.create` 有 deprecation 警告，不影响运行）。
2. Godot 导入本目录（`project.godot`）。
3. F5 从标题 → 「开始游戏」进入 `chapter01_新皮肤`。

## 验收点
1. 桥上：陈默.沉重(center) 占位立绘 + 打字机台词。
2. choice「再想想」→ 经 `label keepgoing` → 陈默.释然 → `jump` 到「回出租屋」段（自动换背景）。
3. choice「跳下去」→ `jump` 到「结局_BE」段 → `ending(BE)` 进结局画面。
4. 立绘累积：narrate 期间立绘维持；不同 `pos` 累积；`hide` 移除。
5. 段尾无 `jump`/`ending` 时回标题（章节结束）。
6. H / 滚轮上 开 Backlog；ESC/右键 系统菜单；F5/F9 快速存读档；A 自动；S 跳过（遇 choice/结局停）。

## 输入键位（代码注册于 GameManager._ready）
| 操作 | 键 |
|------|----|
| 推进 | 左键 / 空格 / 回车 |
| 菜单 | 右键 / ESC |
| 历史 | H / 滚轮上 |
| 快速存读档 | F5 / F9 |
| 自动 / 跳过 | A / S |

## 数据校验（本环境可跑，无需 Godot）
```
cd tools
pip install -r requirements.txt
python validate_chapter.py ../data/chapters/chapter01_新皮肤.json ../data/剧本.schema.json
python -m pytest test_validate.py -v
```
预期：3 用例通过 + CLI 输出 `OK`。

## GUT 单测（需 Godot）
1. 从 https://github.com/bitwes/Gut 下载，把 `addons/gut/` 放进 `addons/gut/`。
2. 命令行运行：
```
godot --headless -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit
```
测试覆盖：Manifest、ChapterLoader、ScriptInterpreter（执行 / 跳转 / 立绘槽）、PlaceholderGen、SaveManager。

## 资源
全部程序占位图（立绘 400×800 纯绿 `#00FF00`、场景 1536×1024、头像 128²），首次引用时生成缓存到 `user://placeholder_cache/`。换真图只改 `data/manifest.json`，不动剧本。

## 已知 V1 边界 / 待办
- **未运行验证**：本会话环境无 Godot CLI，GDScript/GUT 未运行；Python schema 校验是唯一已跑通的锚点。请在 Godot 编辑器中按「验收点」走一遍。
- `SettingsPanel` 仅落地配置存取（`user://settings.cfg`）+ apply 逻辑，**未实现滑杆/开关 UI**（plan 声明的 V1 简化）。
- `snapshot()` 的 bg/bgm 字段留空——`restore()` 从场景段 block 重新推导，不依赖该字段。
- 系统菜单「存档/读档」按钮 V1 降级为 quick 槽（无多槽选择 UI）；多手动槽 API（`SaveManager.save_slot/load_slot/list_slots`）已就绪，待 UI。
- 跳过/自动 V1 不区分「已读」。
- 不含：变量/flag、条件分支、特效、独立 CG 指令、多图层场景、配音、CG 鉴赏（对齐 `剧本.md` V1 边界）。
