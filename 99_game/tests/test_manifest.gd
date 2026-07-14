extends GutTest

var Manifest = preload("res://scripts/data/Manifest.gd")

func test_known_names_resolve():
	var m = Manifest.new()
	m.load_from_path("res://data/manifest.json")
	assert_eq(m.get_portrait("陈默.沉重"), "assets/portraits/陈默.沉重.png")
	assert_eq(m.get_scene("长江大桥-栏杆"), "assets/scenes/长江大桥-栏杆.png")
	assert_eq(m.get_bgm("夜风"), "assets/bgm/夜风.ogg")

func test_unknown_returns_empty():
	var m = Manifest.new()
	m.load_from_path("res://data/manifest.json")
	assert_eq(m.get_portrait("不存在"), "")
	assert_eq(m.get_scene("不存在"), "")
