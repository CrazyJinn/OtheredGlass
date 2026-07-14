extends Control
## 左/中/右立绘累积渲染。

const PW := 400
const PH := 800
var _nodes: Dictionary = {"left": null, "center": null, "right": null}

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	for k in _nodes.keys():
		var tr := TextureRect.new()
		tr.custom_minimum_size = Vector2(PW, PH)
		tr.size = Vector2(PW, PH)
		tr.visible = false
		add_child(tr)
		_nodes[k] = tr
	resized.connect(_reposition_all)
	_reposition_all()

func _reposition_all() -> void:
	for k in _nodes.keys():
		_position(_nodes[k], k)

func _position(tr: TextureRect, key: String) -> void:
	# 跟随本控件真实宽度（aspect="expand" 下不等于 1536），首次 layout 前回退 1536
	var w := size.x if size.x > 0 else 1536.0
	match key:
		"left": tr.position = Vector2(120, 120)
		"center": tr.position = Vector2((w - PW) / 2.0, 120)
		"right": tr.position = Vector2(w - PW - 120, 120)

func apply_slots(slots: Dictionary) -> void:
	for k in _nodes.keys():
		var tr: TextureRect = _nodes[k]
		var v = slots.get(k)
		if v == null:
			tr.visible = false
			tr.texture = null
		else:
			tr.texture = _resolve(v["who"], v["portrait"])
			tr.visible = true

func _resolve(who: String, portrait: String) -> Texture2D:
	var logical := "%s.%s" % [who, portrait]
	var man = Engine.get_singleton("Manifest") if Engine.has_singleton("Manifest") else null
	var path: String = man.get_portrait(logical) if man else ""
	if path != "" and ResourceLoader.exists(path):
		return load(path)
	var pg = preload("res://scripts/util/PlaceholderGen.gd").new()
	return pg.get_portrait_image(who, portrait)
