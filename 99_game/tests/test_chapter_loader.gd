extends GutTest

var ChapterLoader = preload("res://scripts/data/ChapterLoader.gd")

func test_load_known_chapter():
	var cl = ChapterLoader.new()
	var ch = cl.load_chapter("chapter01_新皮肤")
	assert_not_null(ch)
	assert_eq(ch.get("meta", {}).get("title"), "新皮肤·Day0")
	assert_true(ch.has("scenes"))
	assert_eq(len(ch["scenes"]), 3)

func test_missing_file_returns_empty():
	var cl = ChapterLoader.new()
	var ch = cl.load_chapter("不存在")
	assert_eq(ch, {})

func test_cached_on_second_call():
	var cl = ChapterLoader.new()
	var a = cl.load_chapter("chapter01_新皮肤")
	var b = cl.load_chapter("chapter01_新皮肤")
	# 别名效应：缓存须返回同一 Dictionary 引用，改 a 应见于 b
	# （GDScript 4 的 == 是内容比较，无法区分同内容的不同字典）
	a["__probe__"] = true
	assert_true(b.has("__probe__"), "缓存应返回同一引用（别名效应）")
	a.erase("__probe__")
