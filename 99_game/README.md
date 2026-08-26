# 他者之镜（OtheredGlass）— Godot 工程

2D Galgame 框架。集中式 `ScriptInterpreter` 解释器消费纯 JSON 剧本（`data/chapters/*.json`，格式见 `data/剧本.schema.json`），经 `data/manifest.json` 把逻辑名映射到资源；美术默认程序占位兜底（真图经上游 `chapter-publisher` 搬运，见「资源」）。本工程现含序章 `chapter00_序章.json`。

> 剧情格式权威定义：`.claude/skills/chapter-dialoguer/references/剧本.md` + `.claude/skills/chapter-dialoguer/references/剧本.schema.json`（本工程 `data/剧本.schema.json` 为其字节副本）。

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
3. F5 从标题 → 「开始游戏」进入 `chapter00_序章`（起始章配置见 `scripts/autoload/GameManager.gd` 的 `start_chapter`/`start_scene`，默认 `chapter00_序章`/`酒店`）。

## 验收点

> 「开始游戏」默认进序章 `chapter00_序章`（线性叙事，无分支/结局；角色 陆择/顾盈/小夏/伊芙，场景 酒店-客房 → 街角咖啡店 → 马路-路口 → 灵魂夹缝）。

1. 立绘累积：角色 `say`/`show` 进 left/center/right 槽，`narrate` 期间维持，`hide` 移除。
2. 立绘按身高缩放、贴底对齐（高个偏高、矮个偏矮；缩放值来自 `IllusDesign.display_scale` 经 manifest `portrait_scales` 注入）。
3. 背景：`scene` 切换时换背景图（缺图走绿色占位兜底）。
4. 章末（末段末句后无 `jump`/`ending`）自动回标题。
5. H / 滚轮上 开 Backlog；ESC/右键 系统菜单；F5/F9 快速存读档；A 自动；S 跳过。

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
python validate_chapter.py ../data/chapters/chapter00_序章.json ../data/剧本.schema.json
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
- **占位兜底**：缺资源时程序生成占位图（立绘 400×800 纯绿 `#00FF00`、场景 1536×1024、头像 128²），首次引用时缓存到 `user://placeholder_cache/`。
- **真图搬运**：真图由上游 `chapter-publisher` skill（`.claude/skills/chapter-publisher/`）从创作区（`06_角色美术/`、`07_场景美术/`）发布到 `data/chapters/`（剧本）与 `assets/`（图片），并更新 `manifest.json`。
- **立绘缩放 + 去绿**：立绘原图是 `#00FF00` 绿幕，搬运时经 `tools/process_portrait.py` 先缩放到 800×1200（保 2:3）、再用 ffmpeg `colorkey` 抠去绿幕成透明 PNG，落到 `assets/portraits/<角色>.<变体>.png`；**原图不动**，处理只发生在搬运结果上。背景图是场景油画（非绿幕），原样拷贝。ffmpeg 路径读 `settings.json` 的 `ffmpeg_path`。
- **改图不改剧本**：换真图只改 `manifest.json`（逻辑名→`assets/...` 路径），不动剧本 JSON。

## 已知 V1 边界 / 待办
- **未运行验证**：本会话环境无 Godot CLI，GDScript/GUT 未运行；Python schema 校验是唯一已跑通的锚点。请在 Godot 编辑器中按「验收点」走一遍。
- `SettingsPanel` 仅落地配置存取（`user://settings.cfg`）+ apply 逻辑，**未实现滑杆/开关 UI**（plan 声明的 V1 简化）。
- `snapshot()` 的 bg/bgm 字段留空——`restore()` 从场景段 block 重新推导，不依赖该字段。
- 系统菜单「存档/读档」按钮 V1 降级为 quick 槽（无多槽选择 UI）；多手动槽 API（`SaveManager.save_slot/load_slot/list_slots`）已就绪，待 UI。
- 跳过/自动 V1 不区分「已读」。
- 不含：变量/flag、条件分支、特效、独立 CG 指令、多图层场景、配音、CG 鉴赏（对齐 `剧本.md` V1 边界）。
