extends Control
## 底部对话框：头像/名称/打字机正文/继续指示 + Auto/Skip/Log/Menu。

signal finished_typing()
signal button_auto()
signal button_skip()
signal button_log()
signal button_menu()

const BOX_H := 240
var _avatar := TextureRect.new()
var _name_lbl := Label.new()
var _body := RichTextLabel.new()
var _continue_lbl := Label.new()
var _char_delay: float = 0.03  # 秒/字
var _full_text := ""
var _shown := 0
var _typing := false
var _timer := Timer.new()

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var box := Panel.new()
	box.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	box.offset_top = -BOX_H
	add_child(box)
	_avatar.custom_minimum_size = Vector2(128, 128)
	_avatar.position = Vector2(20, 20)
	_avatar.size = Vector2(128, 128)
	box.add_child(_avatar)
	_name_lbl.position = Vector2(168, 16)
	_name_lbl.add_theme_font_size_override("font_size", 28)
	box.add_child(_name_lbl)
	_body.position = Vector2(168, 56)
	_body.size = Vector2(1300, 150)
	_body.bbcode_enabled = true
	_body.add_theme_font_size_override("normal_font_size", 26)
	box.add_child(_body)
	_continue_lbl.text = "点击继续 ▼"
	_continue_lbl.position = Vector2(1280, 200)
	_continue_lbl.visible = false
	box.add_child(_continue_lbl)
	_make_buttons(box)
	add_child(_timer)
	_timer.one_shot = false
	_timer.timeout.connect(_tick)

func _make_buttons(box: Panel) -> void:
	var names := ["Auto", "Skip", "Log", "Menu"]
	var sigs := [button_auto, button_skip, button_log, button_menu]
	for i in names.size():
		var b := Button.new()
		b.text = names[i]
		b.position = Vector2(700 + i * 130, 16)
		b.size = Vector2(120, 36)
		var sig = sigs[i]
		b.pressed.connect(func(): sig.emit())
		box.add_child(b)

func show_line(who: String, portrait: String, text: String, is_narrate: bool) -> void:
	_name_lbl.text = "" if is_narrate else who
	_avatar.texture = _resolve_avatar(who)
	_full_text = text
	_shown = 0
	_body.text = ""
	_continue_lbl.visible = false
	_typing = true
	_timer.start(_char_delay)

func is_typing() -> bool:
	return _typing

func finish_typing() -> void:
	_typing = false
	_timer.stop()
	_body.text = _full_text
	_shown = _full_text.length()
	_continue_lbl.visible = true
	finished_typing.emit()

func _tick() -> void:
	if not _typing:
		return
	_shown += 1
	_body.text = _full_text.substr(0, _shown)
	if _shown >= _full_text.length():
		finish_typing()

func _resolve_avatar(who: String) -> Texture2D:
	# 头像无独立逻辑名，退化为占位；manifest 若提供 <who>.default 则用之
	var man = Engine.get_singleton("Manifest") if Engine.has_singleton("Manifest") else null
	var path: String = man.get_portrait(who + ".default") if man else ""
	if path != "" and ResourceLoader.exists(path):
		return load(path)
	var pg = preload("res://scripts/util/PlaceholderGen.gd").new()
	return pg.get_avatar_image(who)
