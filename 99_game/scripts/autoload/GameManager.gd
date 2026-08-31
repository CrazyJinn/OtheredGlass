extends Node
## 全局流程 + 键位注册（代码注册 InputMap，替代 project.godot 手写 [input]）+ 场景切换。
## autoload: GameManager（首个 autoload，_ready 时注册 Manifest 单例与输入）。

class EndingData:
	static var kind: String = ""
	static var title: String = ""

func _ready() -> void:
	# 注册 Manifest 单例，供其他 autoload 与 UI 共用
	if not Engine.has_singleton("Manifest"):
		var m = preload("res://scripts/data/Manifest.gd").new()
		m.load_from_path("res://data/manifest.json")
		Engine.register_singleton("Manifest", m)
	_register_inputs()
	_apply_default_font()

func _register_inputs() -> void:
	_add_action("advance", [KEY_SPACE, KEY_ENTER], [MOUSE_BUTTON_LEFT])
	_add_action("menu", [KEY_ESCAPE], [MOUSE_BUTTON_RIGHT])
	_add_action("quick_save", [KEY_F5], [])
	_add_action("quick_load", [KEY_F9], [])
	_add_action("log", [KEY_H], [MOUSE_BUTTON_WHEEL_UP])
	_add_action("auto_play", [KEY_A], [])
	_add_action("skip", [KEY_S], [])

func _add_action(action_name: String, keycodes: Array, mouse_buttons: Array) -> void:
	if InputMap.has_action(action_name):
		return
	InputMap.add_action(action_name)
	for kc in keycodes:
		var e := InputEventKey.new()
		e.keycode = kc
		InputMap.action_add_event(action_name, e)
	for mb in mouse_buttons:
		var em := InputEventMouseButton.new()
		em.button_index = mb
		InputMap.action_add_event(action_name, em)

func _apply_default_font() -> void:
	# 桌面端有系统中文字体兜底；Web 端浏览器缺中文字体 → 中文乱码。
	# 固定路径加载内嵌字体设为 root theme 默认字体。
	# （不用 DirAccess 扫描：该 API 在 Web 端读 pck 不可靠——桌面正常但 Web 漏扫，字体设不上。）
	const FONT_PATH := "res://fonts/LXGWWenKai-Medium.ttf"
	if not ResourceLoader.exists(FONT_PATH):
		return
	var f := load(FONT_PATH) as Font
	if f == null:
		return
	var t := Theme.new()
	t.default_font = f
	get_tree().root.theme = t

## 起始章节配置（Game 场景 _ready 时读这两个值启动解释器）。
## start_new_game() 可传参覆盖；start_scene 留空 = 章首段（scene-block id 随发布变，
## 如 chapter00 曾从 "酒店" 变 "s00_酒店"，硬编码会漂移导致"找不到场景段"）。
var start_chapter := "chapter00_序章"
var start_scene := ""

func start_new_game(chapter: String = "", scene: String = "") -> void:
	# Game 场景 _ready 时自行调 ScriptInterpreter.start，避免跨场景 call_deferred 时序问题
	if chapter != "":
		start_chapter = chapter
	if scene != "":
		start_scene = scene
	goto_scene("res://scenes/Game.tscn")

func to_title() -> void:
	goto_scene("res://scenes/Title.tscn")

func goto_ending(kind: String, title: String) -> void:
	EndingData.kind = kind
	EndingData.title = title
	goto_scene("res://scenes/Ending.tscn")

func goto_scene(path: String) -> void:
	get_tree().change_scene_to_file(path)
