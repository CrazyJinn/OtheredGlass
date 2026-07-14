extends GutTest

var PlaceholderGen = preload("res://scripts/util/PlaceholderGen.gd")

func test_portrait_image_size():
	var g = PlaceholderGen.new()
	var tex = g.get_portrait_image("陈默", "沉重")
	assert_eq(tex.get_width(), 400)
	assert_eq(tex.get_height(), 800)

func test_scene_image_size():
	var g = PlaceholderGen.new()
	var tex = g.get_scene_image("长江大桥-栏杆")
	assert_eq(tex.get_width(), 1536)
	assert_eq(tex.get_height(), 1024)
