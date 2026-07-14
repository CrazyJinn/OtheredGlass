extends GutTest

func _new_interp():
	return preload("res://scripts/autoload/ScriptInterpreter.gd").new()

func test_say_sets_slot():
	var interp = _new_interp()
	var snap: Dictionary = {}
	interp.portrait_changed.connect(func(s): snap = s)
	interp.start("chapter01_新皮肤", "桥上")  # 首条 say: 陈默.沉重 center
	assert_eq(snap["center"]["who"], "陈默")
	assert_eq(snap["center"]["portrait"], "沉重")
	assert_is_null(snap["left"])

func test_show_hide_updates_slots():
	var interp = _new_interp()
	var snap: Dictionary = {}
	interp.portrait_changed.connect(func(s): snap = s.duplicate(true))
	interp._apply_portrait({"op": "show", "who": "陈默", "portrait": "疲惫", "pos": "left"})
	assert_eq(snap["left"]["portrait"], "疲惫")
	interp._apply_portrait({"op": "hide", "who": "陈默"})
	assert_is_null(snap["left"])

# 注：brief 原版依赖信号快照，但 narrate 不发 portrait_changed（connect 在 start 之后），
# snap 永远为空、断言 key 不存在必败。改为直接读 interp.slots 公开成员验证 narrate 未改槽。
func test_narrate_keeps_slots():
	var interp = _new_interp()
	interp.start("chapter01_新皮肤", "桥上")  # 首条 say 设 center=陈默.沉重
	interp.advance()  # 离开 say 到 narrate；narrate 不改槽
	# 直接读 slots：center 仍是沉重，证明 narrate 维持画面
	assert_eq(interp.slots["center"]["portrait"], "沉重")
