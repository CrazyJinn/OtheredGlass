extends Control
## 选项面板。

signal option_chosen(option: Dictionary)
var _container := VBoxContainer.new()

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_container.set_anchors_preset(Control.PRESET_CENTER)
	_container.position = Vector2(-150, -120)
	add_child(_container)
	hide()

func show_options(options: Array) -> void:
	for c in _container.get_children():
		c.queue_free()
	for opt in options:
		var b := Button.new()
		b.text = opt["label"]
		b.custom_minimum_size = Vector2(300, 56)
		var o = opt  # 局部解耦，避免 lambda 捕获循环变量
		b.pressed.connect(func(): _on_chosen(o))
		_container.add_child(b)
	show()

func _on_chosen(opt: Dictionary) -> void:
	hide()
	option_chosen.emit(opt)
