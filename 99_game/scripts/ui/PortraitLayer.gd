extends Control
## 左/中/右立绘累积渲染。按各槽当前立绘的 display_scale 缩高、贴底对齐（脚踩同一地面线）；
## 宽按纹理实际宽高比（process_portrait 紧凑裁剪后立绘不再固定 2:3）；左/右内缩、中居中。
## scale 默认 1.0（占满层高），由 IllusDesign.display_scale 经 manifest 的 portrait_scales 注入。

const PORTRAIT_ASPECT := 800.0 / 1200.0  # 立绘素材宽/高（2:3）；无纹理时回退比例
const PORTRAIT_SIDE_INSET := 0.10  # 左右槽距画布边的内缩比例（往中间靠；0=贴边）
var _nodes: Dictionary = {"left": null, "center": null, "right": null}
var _scales: Dictionary = {"left": 1.0, "center": 1.0, "right": 1.0}

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	for k in _nodes.keys():
		var tr := TextureRect.new()
		# IGNORE_SIZE：不让 texture 原尺寸撑大控件，手动 size 才生效（否则立绘溢出偏右下）
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		# size 在 _position 按纹理实际比例算，SCALE 填满不变形
		tr.stretch_mode = TextureRect.STRETCH_SCALE
		# 立绘层不拦截鼠标，让点击穿透到 Game._unhandled_input 推进对话
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		tr.visible = false
		add_child(tr)
		_nodes[k] = tr
	resized.connect(_reposition_all)
	_reposition_all()

func _reposition_all() -> void:
	for k in _nodes.keys():
		_position(_nodes[k], k, _scales[k])

func _position(tr: TextureRect, key: String, scale: float) -> void:
	# 跟随本控件真实尺寸（aspect="expand" 下不等于 1536×1024），首次 layout 前回退设计基准
	var h := size.y if size.y > 0 else 1024.0
	var w := size.x if size.x > 0 else 1536.0
	var sh := h * scale                # 实际显示高（scale 来自 IllusDesign.display_scale）
	# 宽按纹理实际宽高比（紧凑裁剪后立绘不再固定 2:3）；无纹理时回退 2:3
	var aspect := PORTRAIT_ASPECT
	if tr.texture != null and tr.texture.get_height() > 0:
		aspect = float(tr.texture.get_width()) / float(tr.texture.get_height())
	var sw := sh * aspect
	tr.size = Vector2(sw, sh)
	var inset := w * PORTRAIT_SIDE_INSET  # 左右槽内缩（往中间靠）
	var y := h - sh                    # 贴底：脚踩同一地面线，矮个不悬空
	match key:
		"left": tr.position = Vector2(inset, y)
		"center": tr.position = Vector2((w - sw) / 2.0, y)
		"right": tr.position = Vector2(w - sw - inset, y)

func apply_slots(slots: Dictionary) -> void:
	for k in _nodes.keys():
		var tr: TextureRect = _nodes[k]
		var v = slots.get(k)
		if v == null:
			tr.visible = false
			tr.texture = null
			_scales[k] = 1.0
		else:
			tr.texture = _resolve(v["who"], v["portrait"])
			tr.visible = true
			_scales[k] = _resolve_scale(v["portrait"])
			_position(tr, k, _scales[k])

func _resolve_scale(portrait: String) -> float:
	# 整键查 manifest 的 portrait_scales（IllusDesign.display_scale 经 manifest_builder 搬入）；
	# 旧章/未设的立绘无记录，默认 1.0（满高）。
	var man = Engine.get_singleton("Manifest") if Engine.has_singleton("Manifest") else null
	if man:
		return man.get_portrait_scale(portrait)
	return 1.0

func _resolve(who: String, portrait: String) -> Texture2D:
	# portrait 字段可能是：新格式 guid 整键（陆择-赤裸上身-慵懒-PHSE4iftNQ）或旧格式纯变体（慵懒）。
	# 先按整键查（新章），空则拼 who 查旧二维键（旧二维键 fallback）。
	var man = Engine.get_singleton("Manifest") if Engine.has_singleton("Manifest") else null
	var path: String = ""
	if man:
		path = man.get_portrait(portrait)
		if path.is_empty():
			path = man.get_portrait("%s.%s" % [who, portrait])
	if path != "" and ResourceLoader.exists(path):
		return load(path)
	var pg = preload("res://scripts/util/PlaceholderGen.gd").new()
	return pg.get_portrait_image(who, portrait)
