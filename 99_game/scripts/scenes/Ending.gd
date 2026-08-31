extends Control
## 结局画面（BE/TE/HE/NE）。数据由 GameManager.EndingData 传入。

var _bg: ColorRect
var _center: CenterContainer
var _vbox: VBoxContainer

func _ready() -> void:
	_bg = ColorRect.new()
	_bg.color = Color(0.02, 0.02, 0.03, 1.0)
	add_child(_bg)
	_center = CenterContainer.new()
	add_child(_center)
	_vbox = VBoxContainer.new()
	_vbox.add_theme_constant_override("separation", 32)
	_center.add_child(_vbox)
	var label := Label.new()
	label.text = "结局 [%s]\n%s" % [GameManager.EndingData.kind, GameManager.EndingData.title]
	label.add_theme_font_size_override("font_size", 48)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_vbox.add_child(label)
	var btn := Button.new()
	btn.text = "返回标题"
	btn.custom_minimum_size = Vector2(160, 50)
	btn.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	btn.pressed.connect(GameManager.to_title)
	_vbox.add_child(btn)
	# 主场景根 Control 不会被 Window 自动铺满（实测恒为 0,0），手动设到视口尺寸。
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
