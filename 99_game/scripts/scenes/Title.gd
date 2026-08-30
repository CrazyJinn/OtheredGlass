extends Control
## 标题/主菜单。

var _bg: ColorRect
var _center: CenterContainer
var _vbox: VBoxContainer
var _start: Button
var _quit: Button

func _ready() -> void:
	_bg = ColorRect.new()
	_bg.color = Color(0.05, 0.05, 0.08, 1.0)
	add_child(_bg)
	# CenterContainer 的 rect 被手动铺满视口后，会自动把内容（VBox）整体居中。
	_center = CenterContainer.new()
	add_child(_center)
	_vbox = VBoxContainer.new()
	_vbox.add_theme_constant_override("separation", 24)
	_center.add_child(_vbox)
	var title := Label.new()
	title.text = "他者之镜"
	title.add_theme_font_size_override("font_size", 72)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_vbox.add_child(title)
	_start = Button.new()
	_start.text = "开始游戏"
	_start.custom_minimum_size = Vector2(160, 50)
	_start.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_start.pressed.connect(GameManager.start_new_game)
	_vbox.add_child(_start)
	_quit = Button.new()
	_quit.text = "退出"
	_quit.custom_minimum_size = Vector2(160, 50)
	_quit.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_quit.pressed.connect(get_tree().quit)
	_vbox.add_child(_quit)
	# 主场景根 Control 的 size 不会被 Window 自动铺满（实测恒为 0,0），
	# 改为监听视口尺寸、手动铺满 bg/center，规避根节点锚点不生效的问题。
	var vp: Viewport = get_viewport()
	if vp != null:
		vp.size_changed.connect(_apply_layout)
	_apply_layout()

func _apply_layout() -> void:
	# 用 get_visible_rect()（逻辑坐标）而非 vp.size（物理像素），同 Game.gd 注释。
	var s: Vector2 = Vector2(1536, 1024)
	var vp: Viewport = get_viewport()
	if vp != null:
		var visible: Vector2 = vp.get_visible_rect().size
		if visible.x > 0.0:
			s = visible
	_bg.size = s
	_center.size = s
	_log_layout("apply")

func _log_layout(tag: String) -> void:
	var vp: Vector2 = Vector2.ZERO
	var v: Viewport = get_viewport()
	if v != null:
		vp = v.get_visible_rect().size
	print("[Title:%s] viewport=%s | self=%s bg=%s center=%s vbox=%s" % [tag, vp, size, _bg.size, _center.size, _vbox.size])
	print("[Title:%s]   start.global=%s | quit.global=%s" % [tag, _start.global_position, _quit.global_position])
