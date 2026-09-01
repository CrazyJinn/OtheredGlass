extends Control
## 底部对话框：名称/打字机正文/继续指示 + Auto/Skip/Log/Menu。

signal finished_typing()
signal button_auto()
signal button_skip()
signal button_log()
signal button_menu()

const BOX_H := 240
const BASE_CHAR_DELAY := 0.03  # 秒/字（正常）
const FAST_CHAR_DELAY := 0.015  # 秒/字（Ctrl 快进 2× 速）
const COLOR_SAY := Color(1.0, 1.0, 1.0)  # 人物对白正文色（亮白）
const COLOR_NARRATE := Color(0.66, 0.71, 0.80)  # 旁白正文色（冷银灰，与对白区分）
var _name_lbl := Label.new()
var _body := RichTextLabel.new()
var _continue_lbl := Label.new()
var _char_delay: float = BASE_CHAR_DELAY  # 秒/字（由 set_fast 切换）
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
	_name_lbl.position = Vector2(60, 16)
	_name_lbl.add_theme_font_size_override("font_size", 28)
	box.add_child(_name_lbl)
	# 锚点撑满 + 负右偏移：宽度跟随 box（expand 拉伸下逻辑宽度随窗口变，禁止固定像素宽）
	_body.set_anchors_preset(Control.PRESET_FULL_RECT)
	_body.offset_left = 60
	_body.offset_right = -60
	_body.offset_top = 56
	_body.offset_bottom = -34
	_body.bbcode_enabled = true
	_body.add_theme_font_size_override("normal_font_size", 26)
	box.add_child(_body)
	_continue_lbl.text = "点击继续 ▼"
	# 右下角锚点 + 向左上生长：始终贴 box 右下
	_continue_lbl.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_continue_lbl.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_continue_lbl.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_continue_lbl.offset_right = -60
	_continue_lbl.offset_bottom = -12
	_continue_lbl.visible = false
	box.add_child(_continue_lbl)
	_make_buttons(box)
	add_child(_timer)
	_timer.one_shot = false
	_timer.timeout.connect(_tick)
	# 展示控件放行鼠标穿透到 Game._unhandled_input（推进对话）；按钮保留默认 STOP
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_name_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_continue_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE

func _make_buttons(box: Panel) -> void:
	var names := ["Auto", "Skip", "Log", "Menu"]
	var sigs := [button_auto, button_skip, button_log, button_menu]
	for i in names.size():
		var b := Button.new()
		b.text = names[i]
		# 右上锚点整排贴右缘（i 越大越靠右），禁止固定 x 起点铺开
		b.set_anchors_preset(Control.PRESET_TOP_RIGHT)
		b.offset_right = -60 - (names.size() - 1 - i) * 130
		b.offset_left = b.offset_right - 120
		b.offset_top = 16
		b.offset_bottom = 52
		var sig = sigs[i]
		b.pressed.connect(func(): sig.emit())
		box.add_child(b)

func show_line(who: String, text: String, is_narrate: bool) -> void:
	_name_lbl.text = "" if is_narrate else who
	_body.add_theme_color_override("default_color", COLOR_NARRATE if is_narrate else COLOR_SAY)
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

# Ctrl 快进切换：打字机 2× 速；打字中需重启 timer 才用上新周期
func set_fast(fast: bool) -> void:
	_char_delay = FAST_CHAR_DELAY if fast else BASE_CHAR_DELAY
	if _typing:
		_timer.stop()
		_timer.start(_char_delay)

func _tick() -> void:
	if not _typing:
		return
	_shown += 1
	_body.text = _full_text.substr(0, _shown)
	if _shown >= _full_text.length():
		finish_typing()
