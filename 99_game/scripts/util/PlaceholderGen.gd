extends Node
## 程序占位图：立绘 400×800 纯绿底、场景 1536×1024 渐变、头像方形。

const CHROMA := Color(0.0, 1.0, 0.0)  # #00FF00
const CACHE_DIR := "user://placeholder_cache/"

func get_portrait_image(who: String, portrait: String) -> ImageTexture:
	var key := "%s.%s" % [who, portrait]
	var path := CACHE_DIR + "portrait_" + _safe(key) + ".png"
	var img := _load_or_make(path, func(): return _make_portrait(key))
	return ImageTexture.create_from_image(img)

func get_scene_image(scene: String) -> ImageTexture:
	var path := CACHE_DIR + "scene_" + _safe(scene) + ".png"
	var img := _load_or_make(path, func(): return _make_scene(scene))
	return ImageTexture.create_from_image(img)

func get_avatar_image(who: String) -> ImageTexture:
	var path := CACHE_DIR + "avatar_" + _safe(who) + ".png"
	var img := _load_or_make(path, func(): return _make_avatar(who))
	return ImageTexture.create_from_image(img)

func _load_or_make(path: String, maker: Callable) -> Image:
	if FileAccess.file_exists(path):
		var cached := Image.load_from_file(path)
		if cached != null:
			return cached
	DirAccess.make_dir_recursive_absolute(CACHE_DIR)
	var img: Image = maker.call()
	img.save_png(path)
	return img

func _make_portrait(label: String) -> Image:
	var img := Image.create(400, 800, false, Image.FORMAT_RGBA8)
	img.fill(CHROMA)
	_draw_label(img, label, 400, 800)
	return img

func _make_scene(label: String) -> Image:
	var img := Image.create(1536, 1024, false, Image.FORMAT_RGBA8)
	for y in 1024:
		var t := float(y) / 1024.0
		img.fill_rect(Rect2i(0, y, 1536, 1), Color(0.15 + t * 0.2, 0.15, 0.25, 1.0))
	_draw_label(img, "场景：" + label, 1536, 1024)
	return img

func _make_avatar(label: String) -> Image:
	var img := Image.create(128, 128, false, Image.FORMAT_RGBA8)
	img.fill(Color(0.3, 0.3, 0.35, 1.0))
	_draw_label(img, label, 128, 128)
	return img

# 简易文字：用大像素块拼不现实，这里用占位色块 + 不依赖字体的标注。
# 真实文字渲染由 PortraitLayer/DialogueBox 用 Label 节点叠加；图片本身只填色。
func _draw_label(img: Image, label: String, w: int, h: int) -> void:
	img.fill_rect(Rect2i(w / 4, h / 2 - 20, w / 2, 40), Color(0.0, 0.0, 0.0, 0.4))

func _safe(s: String) -> String:
	return s.replace(".", "_").replace("/", "_").replace(":", "_")
