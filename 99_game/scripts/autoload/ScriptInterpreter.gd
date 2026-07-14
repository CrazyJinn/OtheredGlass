extends Node
## 集中式剧本解释器。持有运行时状态，match op 分发指令。

signal line_ready(kind: String, payload: Dictionary)
signal portrait_changed(slots: Dictionary)
signal bg_changed(scene_name: String, time: String)
signal bgm_changed(track: String, mode: String, loop: bool)
signal choice_presented(options: Array)
signal ended(kind: String, title: String, cg: String)
signal chapter_finished()
signal scene_entered()
signal sfx_triggered(track: String)

var _file: String = ""
var _chapter: Dictionary = {}
var _scenes: Array = []
var _scene_idx: int = 0
var _line_idx: int = 0
# 立绘槽状态：值为 {who, portrait} 或 null。say/show 写入，hide 清除。
var slots: Dictionary = {"left": null, "center": null, "right": null}

var _ChapterLoader = preload("res://scripts/data/ChapterLoader.gd")
var _loader

func _ready() -> void:
	_loader = _ChapterLoader.new()

func start(file: String, scene_id: String = "", label: String = "") -> void:
	# 重置立绘槽：每次 start 开局清空，避免跨章节/重开残留
	slots = {"left": null, "center": null, "right": null}
	# GUT 适配：测试用 .new() 创建、未入树时 _ready 不触发，此处兜底初始化
	if _loader == null:
		_loader = _ChapterLoader.new()
	_file = file
	_chapter = _loader.load_chapter(file)
	if _chapter.is_empty():
		push_error("ScriptInterpreter: 无法加载章节 %s" % file)
		chapter_finished.emit()
		return
	_scenes = _chapter["scenes"]
	_scene_idx = 0
	if scene_id != "":
		_scene_idx = _find_scene_index(scene_id)
	_enter_scene_block()
	if label != "":
		var li := _find_label(label)
		if li >= 0:
			_line_idx = li
	_run_from_current()

func advance() -> void:
	_line_idx += 1
	_run_from_current()

# 内部：进入场景段时套用 scene + bgm，从 line 0 起
func _enter_scene_block() -> void:
	_line_idx = 0
	var blk: Dictionary = _scenes[_scene_idx]
	bg_changed.emit(blk.get("scene", ""), blk.get("time", ""))
	if blk.has("bgm"):
		var b: Dictionary = blk["bgm"]
		bgm_changed.emit(b.get("track", ""), b.get("mode", "play"), b.get("loop", true))
	scene_entered.emit()

# 从当前 line 起推进：即时指令自动递进，阻塞/终止停下
func _run_from_current() -> void:
	while true:
		if _scene_idx >= len(_scenes):
			chapter_finished.emit()
			return
		var blk: Dictionary = _scenes[_scene_idx]
		var lines: Array = blk["lines"]
		if _line_idx >= len(lines):
			# 当前段执行完且无 jump/ending：章节结束
			chapter_finished.emit()
			return
		var line: Dictionary = lines[_line_idx]
		var op: String = line["op"]
		match op:
			"say":
				_set_slot(line.get("pos", "center"), line.get("who", ""), line.get("portrait", ""))
				portrait_changed.emit(_snapshot())
				line_ready.emit("say", line)
				return  # 阻塞
			"narrate":
				line_ready.emit("narrate", line)
				return  # 阻塞
			"choice":
				choice_presented.emit(line["options"])
				return  # 阻塞
			"ending":
				ended.emit(line.get("kind", "NE"), line.get("title", ""), line.get("cg", ""))
				return  # 终止
			"label":
				_line_idx += 1
				continue
			"show", "hide":
				_apply_portrait(line)
				_line_idx += 1
				continue
			"bg":
				bg_changed.emit(line.get("scene", ""), line.get("time", ""))
				_line_idx += 1
				continue
			"bgm":
				bgm_changed.emit(line.get("track", ""), line.get("mode", "play"), line.get("loop", true))
				_line_idx += 1
				continue
			"sfx":
				sfx_triggered.emit(line.get("track", ""))
				_line_idx += 1
				continue
			"jump":
				_do_jump(line)
				continue  # _do_jump 已重定位 _scene_idx/_line_idx，继续推进
			_:
				push_error("ScriptInterpreter: 未知 op %s" % op)
				_line_idx += 1

# 立绘累积：show/hide 维护槽并发 portrait_changed；say 的立绘在 _run_from_current 里直接 _set_slot
func _apply_portrait(line: Dictionary) -> void:
	var op: String = line["op"]
	if op == "show":
		_set_slot(line.get("pos", "center"), line.get("who", ""), line.get("portrait", ""))
		portrait_changed.emit(_snapshot())
	elif op == "hide":
		_clear_slot_by_who(line.get("who", ""))
		portrait_changed.emit(_snapshot())

func _set_slot(pos: String, who: String, portrait: String) -> void:
	if slots.has(pos):
		slots[pos] = {"who": who, "portrait": portrait}

func _clear_slot_by_who(who: String) -> void:
	for k in slots.keys():
		if slots[k] != null and slots[k].get("who", "") == who:
			slots[k] = null

func _snapshot() -> Dictionary:
	return slots.duplicate(true)

func _do_jump(line: Dictionary) -> void:
	# 仅重定位指令指针，不推进；由 _run_from_current 的 while continue 自然走到新位置
	resolve_target(line.get("to", ""), line.get("scene", ""), line.get("file", ""))

# 玩家选定选项后由 UI 调用。option 含 to/scene/file（与 jump 共用 resolve_target）。
func choose(option: Dictionary) -> void:
	if not resolve_target(option.get("to", ""), option.get("scene", ""), option.get("file", "")):
		push_error("ScriptInterpreter: 选项目标无法定位 %s" % str(option))
		chapter_finished.emit()
		return
	_run_from_current()

# 重定位指令指针（file→scene→to 三层）。返回 false 表示定位失败。
func resolve_target(to: String, scene: String, file: String) -> bool:
	# file：跨章节切换并缓存
	if file != "":
		var new_chapter: Dictionary = _loader.load_chapter(file)
		if new_chapter.is_empty():
			push_error("ScriptInterpreter: 跨章节文件不存在 %s" % file)
			return false
		_file = file
		_chapter = new_chapter
		_scenes = new_chapter["scenes"]
		_scene_idx = 0
		_line_idx = 0  # 跨章节从头（spec：file=跨章节文件从头）；若后续有 scene/to 会覆盖
	# scene：本/新章节内定位段（_enter_scene_block 重置 _line_idx=0 并发 bg/bgm）
	if scene != "":
		_scene_idx = _find_scene_index(scene)
		_enter_scene_block()
	# to：段内 label 定位
	if to != "":
		var li := _find_label(to)
		if li < 0:
			return false
		_line_idx = li
	return true

func _find_scene_index(scene_id: String) -> int:
	for i in len(_scenes):
		if _scenes[i].get("id", "") == scene_id:
			return i
	push_error("ScriptInterpreter: 找不到场景段 %s" % scene_id)
	return 0

func _find_label(name: String) -> int:
	var lines: Array = _scenes[_scene_idx]["lines"]
	for i in len(lines):
		if lines[i].get("op") == "label" and lines[i].get("name") == name:
			return i
	push_error("ScriptInterpreter: 找不到 label %s" % name)
	return -1

# 存档快照：V1 无变量无 flag，状态 = 文件/段/指针/槽。供 SaveManager 持久化。
func snapshot() -> Dictionary:
	var blk: Dictionary = _scenes[_scene_idx] if _scene_idx < len(_scenes) else {}
	return {
		"file": _file,
		"scene_id": blk.get("id", ""),
		"line_idx": _line_idx,
		"slots": slots.duplicate(true),
		"bg": "", "bgm": ""
	}

# 从快照恢复运行时状态，套用当前段视觉并从 line_idx 继续执行。
func restore(snapshot_data: Dictionary) -> void:
	if _loader == null:
		_loader = _ChapterLoader.new()
	slots = snapshot_data.get("slots", {"left": null, "center": null, "right": null})
	var file: String = snapshot_data.get("file", "")
	var scene_id: String = snapshot_data.get("scene_id", "")
	var line_idx: int = int(snapshot_data.get("line_idx", 0))
	_chapter = _loader.load_chapter(file)
	if _chapter.is_empty():
		push_error("ScriptInterpreter: restore 无法加载 %s" % file)
		chapter_finished.emit()
		return
	_file = file
	_scenes = _chapter["scenes"]
	_scene_idx = _find_scene_index(scene_id) if scene_id != "" else 0
	_line_idx = line_idx
	# 套用当前段的视觉（scene+bgm+立绘），但不重置 line_idx
	var blk: Dictionary = _scenes[_scene_idx]
	bg_changed.emit(blk.get("scene", ""), blk.get("time", ""))
	if blk.has("bgm"):
		var b: Dictionary = blk["bgm"]
		bgm_changed.emit(b.get("track", ""), b.get("mode", "play"), b.get("loop", true))
	portrait_changed.emit(_snapshot())
	_run_from_current()
