extends Control
## 主游戏场景：背景层 + 立绘层 + 对话框 + 选项 + 历史 + 系统菜单 + 设置。
## 订阅 ScriptInterpreter 信号做渲染；玩家输入驱动解释器 advance/choose。

var _bg := TextureRect.new()
var _portraits = preload("res://scripts/ui/PortraitLayer.gd").new()
var _dialogue = preload("res://scripts/ui/DialogueBox.gd").new()
var _choice = preload("res://scripts/ui/ChoiceMenu.gd").new()
var _backlog = preload("res://scripts/ui/Backlog.gd").new()
var _menu = preload("res://scripts/ui/SystemMenu.gd").new()
var _settings = preload("res://scripts/ui/SettingsPanel.gd").new()
var _auto: bool = false
var _ended: bool = false  # 本轮已进结局/章节结束（防 skip 越界）
var _auto_timer := Timer.new()
var _ctrl_held: bool = false  # Ctrl 按住快进状态
var _ctrl_acc: float = 0.0     # Ctrl 快进句末累加计时
var _skip_active: bool = false  # skip 快进中（异步 while 激活）
const CTRL_LINE_INTERVAL := 0.25  # Ctrl 快进：句末打完后自动翻页间隔（秒）

func _ready() -> void:
	# 根 Control 默认 STOP 会吞掉穿透上来的鼠标点击，导致 _unhandled_input 收不到 advance（键盘不受影响）
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	# 等比裁切填充：背景图 1536×1024（3:2），expand 下视口普遍更高，默认 STRETCH
	# 会纵向拉变形，COVERED 保持比例裁上下。
	_bg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	add_child(_bg)
	add_child(_portraits)
	add_child(_dialogue)
	add_child(_choice)
	add_child(_backlog)
	add_child(_menu)
	add_child(_settings)
	add_child(_auto_timer)
	_auto_timer.one_shot = true
	_auto_timer.timeout.connect(_auto_advance)
	# 纯展示层放行鼠标穿透到 _unhandled_input（推进对话）；按钮在 DialogueBox 内单独保留 STOP
	_bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_portraits.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dialogue.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_wire_interpreter()
	_wire_ui()
	# 主场景根 Control 不会被 Window 自动铺满（实测恒为 0,0），手动设到视口尺寸，
	# 子层（_bg/PortraitLayer/DialogueBox 等 PRESET_FULL_RECT）才会正确铺满。
	var vp: Viewport = get_viewport()
	if vp != null:
		vp.size_changed.connect(_apply_layout)
	_apply_layout()
	# 进入起始章节（GameManager.start_new_game 可传参覆盖，默认 chapter00_序章/酒店）
	ScriptInterpreter.start(GameManager.start_chapter, GameManager.start_scene)

func _apply_layout() -> void:
	# 必须用 get_visible_rect()（逻辑坐标）：root viewport 的 size 是物理像素，
	# Web hidpi / expand 下两者不同（expand 逻辑宽恒为基准 1536，物理宽=innerW*dpr），
	# 直接赋给 Control 会随窗口形状产生 ±5~10% 错位，根比视口大时子层溢出裁切。
	var s: Vector2 = Vector2(1536, 1024)
	var vp: Viewport = get_viewport()
	if vp != null:
		var visible: Vector2 = vp.get_visible_rect().size
		if visible.x > 0.0:
			s = visible
	size = s

func _wire_interpreter() -> void:
	ScriptInterpreter.line_ready.connect(_on_line_ready)
	ScriptInterpreter.portrait_changed.connect(_portraits.apply_slots)
	ScriptInterpreter.bg_changed.connect(_on_bg_changed)
	ScriptInterpreter.bgm_changed.connect(_on_bgm_changed)
	ScriptInterpreter.choice_presented.connect(_on_choice)
	ScriptInterpreter.scene_entered.connect(_on_scene_entered)
	ScriptInterpreter.ended.connect(_on_ended)
	ScriptInterpreter.chapter_finished.connect(_on_chapter_finished)

func _wire_ui() -> void:
	_choice.option_chosen.connect(ScriptInterpreter.choose)
	_dialogue.button_log.connect(_backlog.toggle)
	_dialogue.button_auto.connect(_toggle_auto)
	_dialogue.button_skip.connect(_skip)
	_dialogue.button_menu.connect(_toggle_menu)
	_menu.settings_requested.connect(_settings.show)
	_menu.title_requested.connect(GameManager.to_title)
	_menu.closed.connect(_menu.close)
	_menu.save_requested.connect(_quick_save)  # V1：存档按钮降级为 quick 存
	_menu.load_requested.connect(_quick_load)  # V1：读档按钮降级为 quick 读

func _toggle_menu() -> void:
	if _menu.visible:
		_menu.close()
	else:
		_menu.open()

func _on_line_ready(kind: String, payload: Dictionary) -> void:
	if kind == "say":
		_dialogue.show_line(payload.get("who", ""), payload.get("portrait", ""), payload.get("text", ""), false)
		_backlog.append(payload.get("who", ""), payload.get("text", ""))
		AudioManager.play_voice(payload.get("voice", ""))
	else:  # narrate
		_dialogue.show_line("", "", payload.get("text", ""), true)
		_backlog.append("", payload.get("text", ""))
		AudioManager.play_voice("")  # 旁白不配音：仅停上一句对白尾音

func _on_bg_changed(scene_name: String, _time: String) -> void:
	var man = Engine.get_singleton("Manifest") if Engine.has_singleton("Manifest") else null
	var path: String = man.get_scene(scene_name) if man else ""
	if path != "" and ResourceLoader.exists(path):
		_bg.texture = load(path)
	else:
		var pg = preload("res://scripts/util/PlaceholderGen.gd").new()
		_bg.texture = pg.get_scene_image(scene_name)

func _on_bgm_changed(track: String, mode: String, loop: bool) -> void:
	match mode:
		"play": AudioManager.play_bgm(track, loop)
		"stop": AudioManager.stop_bgm()
		"fade": AudioManager.fade_bgm(track, loop)

# 选择点前自动写 quick 槽（spec 5.3）
func _on_choice(options: Array) -> void:
	SaveManager.save_slot(SaveManager.QUICK, ScriptInterpreter.snapshot())
	_choice.show_options(options)

# 场景段头自动写 quick 槽（spec 5.3）
func _on_scene_entered() -> void:
	SaveManager.save_slot(SaveManager.QUICK, ScriptInterpreter.snapshot())
	AudioManager.stop_voice()  # 段切换清场，避免上段尾音漏进新段

func _on_ended(kind: String, title: String, _cg: String) -> void:
	_ended = true
	AudioManager.stop_voice()
	GameManager.goto_ending(kind, title)

func _on_chapter_finished() -> void:
	_ended = true
	AudioManager.stop_voice()
	GameManager.to_title()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("menu"):
		_toggle_menu()
		return
	if event.is_action_pressed("log"):
		_backlog.toggle()
		return
	if event.is_action_pressed("quick_save"):
		_quick_save()
		return
	if event.is_action_pressed("quick_load"):
		_quick_load()
		return
	if event.is_action_pressed("auto_play"):
		_toggle_auto()
		return
	if event.is_action_pressed("skip"):
		_skip()
		return
	if _choice.visible or _menu.visible:
		return
	if event.is_action_pressed("advance"):
		_advance()

func _advance() -> void:
	if _dialogue.is_typing():
		_dialogue.finish_typing()
		return
	ScriptInterpreter.advance()

func _toggle_auto() -> void:
	_auto = not _auto
	if _auto:
		_auto_timer.start(1.0)

func _auto_advance() -> void:
	if not _auto:
		return
	if not _dialogue.is_typing() and not _choice.visible and not _menu.visible:
		ScriptInterpreter.advance()
	_auto_timer.start(1.0)

func _skip() -> void:
	# 跳过 = 推进到下一个 scene-block 首句；遇 choice/menu/ending/章末必停。
	# 每帧推一句（异步）：transition 行的 await 会挂起协程，若同帧同步循环推进
	# 会被 _advancing 挡住而 _line_idx 不动 → 同帧无限空转死循环——必须让帧流动。
	# 快进期间解释器 skipping=true（_process 每帧同步），transition 行不播不等直通。
	AudioManager.stop_voice()  # skip 立即静音，不等下一句自覆盖
	_skip_active = true
	var start := ScriptInterpreter.current_scene_idx()
	while not _ended and not _choice.visible and not _menu.visible:
		if ScriptInterpreter.current_scene_idx() != start:
			break  # 已跨段，停在新段首句
		if _dialogue.is_typing():
			_dialogue.finish_typing()
		else:
			ScriptInterpreter.advance()
		await get_tree().process_frame
	_skip_active = false

func _process(delta: float) -> void:
	# Ctrl 按住 = 打字机 2× 速 + 句末自动翻页（松开恢复手动）
	# 每帧同步快进标志：skip 或 Ctrl 期间解释器 transition 行不播不等（直通）
	ScriptInterpreter.skipping = _skip_active or _ctrl_held
	var ctrl := Input.is_key_pressed(KEY_CTRL)
	if ctrl != _ctrl_held:
		_ctrl_held = ctrl
		_dialogue.set_fast(ctrl)
		_ctrl_acc = 0.0
	if not ctrl or _ended or _choice.visible or _menu.visible:
		return
	if _dialogue.is_typing():
		return  # 等 2× 速打字机自己打完
	_ctrl_acc += delta
	if _ctrl_acc >= CTRL_LINE_INTERVAL:
		_ctrl_acc = 0.0
		ScriptInterpreter.advance()

func _quick_save() -> void:
	SaveManager.save_slot(SaveManager.QUICK, ScriptInterpreter.snapshot())

func _quick_load() -> void:
	var snap = SaveManager.load_slot(SaveManager.QUICK)
	if snap.is_empty():
		return
	ScriptInterpreter.restore(snap)
