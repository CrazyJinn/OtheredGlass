extends SceneTree
## 章节资源包（<stem>.pck）生成工具 —— Web 按章分包的「导出工具」半程。
##
## 读 data/chapter_packs.json（章→资源清单）+ data/manifest.json（逻辑名→相对路径），
## 为每章产出 <stem>.pck 落到输出目录（默认 = export_presets.cfg 里 Web preset 的
## 导出目录，与 index.html 同目录——ChapterPackLoader 的 PACK_BASE_URL 同源约定）。
##
## 与 Web preset 的 exclude_filter=assets/*,data/chapters/* 配套：主 pck 不含任何章
## 资源，开局/读档/跨章由 ChapterPackLoader 下载章包挂载（load_resource_pack
## replace=false 合并 res:// 命名空间，资源按全局路径命中）。
##
## 打包规则（与 Godot 标准导出一致，缺一资源加载不到）：
##   - 已导入资源（png/wav）：.import 元数据 + .godot/imported 导入产物（.ctex/.sample），
##     源文件本身不进包——运行时 ResourceLoader 按 remap 加载导入产物；
##   - 无导入流程的文件（章 JSON）：源文件原样进包；
##   - manifest 缺键/文件缺失：警告跳过并计数（章清单由 chapter-publisher 维护，
##     正常发布链不该出现；少量缺失只影响对应资源加载，不炸整包）。
##
## 用法：
##   godot --headless -s tools/build_chapter_packs.gd -- [输出目录] [stem ...]
##   输出目录缺省 = Web preset 导出目录；stem 缺省 = 清单内全部章。

const PROJECT_ROOT := "res://"

var _manifest: Dictionary = {}
var _packs: Dictionary = {}
var _missing: Array = []  # [[stem, 描述], ...] 汇总警告


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var out_dir := ""
	var stems: Array = []
	for a in args:
		if out_dir == "" and stems.is_empty():
			out_dir = a  # 首个非 -- 参数视为输出目录（可传 "" 占位跳过）
		else:
			stems.append(a)
	if out_dir == "":
		out_dir = _web_export_dir()
	if out_dir == "":
		push_error("build_chapter_packs: 无法确定输出目录（export_presets.cfg 无 Web preset），请显式传入")
		quit(1)
		return

	_manifest = _load_json(PROJECT_ROOT + "data/manifest.json")
	_packs = _load_json(PROJECT_ROOT + "data/chapter_packs.json")
	if _manifest.is_empty() or _packs.is_empty():
		push_error("build_chapter_packs: manifest.json / chapter_packs.json 缺失或为空")
		quit(1)
		return
	if stems.is_empty():
		stems = _packs.keys()

	var dir := DirAccess.open(out_dir)
	if dir == null:
		DirAccess.make_dir_recursive_absolute(out_dir)
		dir = DirAccess.open(out_dir)
	if dir == null:
		push_error("build_chapter_packs: 输出目录不可用 %s" % out_dir)
		quit(1)
		return

	var total_bytes := 0
	for stem in stems:
		var entry: Dictionary = _packs.get(stem, {})
		if entry.is_empty():
			push_error("build_chapter_packs: 清单无此章 %s" % stem)
			quit(1)
			return
		total_bytes += _build_one(stem, entry, out_dir)

	print("build_chapter_packs: 完成 %d 个章包，共 %.1f MB -> %s" % [
		stems.size(), total_bytes / 1048576.0, out_dir])
	if not _missing.is_empty():
		for m in _missing:
			push_warning("build_chapter_packs: 缺资源已跳过 [%s] %s" % [m[0], m[1]])
		print("build_chapter_packs: ⚠️ %d 项缺失（见上警告）" % _missing.size())
	quit(0)


## 单章构建。返回 pck 字节数。
func _build_one(stem: String, entry: Dictionary, out_dir: String) -> int:
	var packer := PCKPacker.new()
	var out_path := out_dir.path_join("%s.pck" % stem)
	packer.pck_start(out_path)
	var file_count := 0
	# 1) 章数据 JSON（ChapterLoader 读 res://data/chapters/<stem>.json）
	file_count += _add_raw(packer, stem, "res://data/chapters/%s.json" % stem)
	# 2) 各类资源（清单键 → manifest 相对路径）
	for category in ["portraits", "scenes", "sfx", "voices", "bgm"]:
		var table: Dictionary = _manifest.get(category, {})
		for key in entry.get(category, []):
			var rel: String = table.get(key, "")
			if rel == "":
				_missing.append([stem, "%s 清单键无 manifest 映射: %s" % [category, key]])
				continue
			file_count += _add_imported(packer, stem, rel)
	var err := packer.flush()
	if err != OK:
		push_error("build_chapter_packs: flush 失败 %s (%d)" % [out_path, err])
		quit(1)
		return 0
	var size := FileAccess.get_file_as_bytes(out_path).size()
	print("build_chapter_packs: %s.pck  %.2f MB（%d 个文件）" % [stem, size / 1048576.0, file_count])
	return size


## 已导入资源：.import 元数据 + .godot/imported 导入产物（按 remap path）。
## 返回打入的文件数（0 = 失败已记警告）。
func _add_imported(packer: PCKPacker, stem: String, rel: String) -> int:
	var res_path := "res://" + rel
	var import_path := res_path + ".import"
	var abs_import := PROJECT_ROOT.path_join(rel + ".import")
	if not FileAccess.file_exists(abs_import):
		_missing.append([stem, "无源文件: %s" % rel])
		return 0
	var cf := ConfigFile.new()
	if cf.load(abs_import) != OK:
		_missing.append([stem, ".import 解析失败: %s" % rel])
		return 0
	var remap: String = cf.get_value("remap", "path", "")
	if remap == "":
		# 无 remap（资源自身即产物，如字体）：源文件原样进包
		packer.add_file(res_path, PROJECT_ROOT.path_join(rel))
		packer.add_file(import_path, abs_import)
		return 2
	packer.add_file(import_path, abs_import)
	var abs_artifact := PROJECT_ROOT.path_join(remap.trim_prefix("res://"))
	if not FileAccess.file_exists(abs_artifact):
		_missing.append([stem, "导入产物缺失（先开编辑器重导入）: %s" % remap])
		return 1
	packer.add_file(remap, abs_artifact)
	return 2


## 无导入流程的文件（JSON 等）：源文件原样进包。
func _add_raw(packer: PCKPacker, stem: String, res_path: String) -> int:
	var abs_path := PROJECT_ROOT.path_join(res_path.trim_prefix("res://"))
	if not FileAccess.file_exists(abs_path):
		_missing.append([stem, "无源文件: %s" % res_path])
		return 0
	packer.add_file(res_path, abs_path)
	return 1


func _load_json(res_path: String) -> Dictionary:
	if not FileAccess.file_exists(res_path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(res_path))
	return parsed if parsed is Dictionary else {}


## 解析 export_presets.cfg：找 name="Web" 的 preset 段，取其 export_path 的目录。
func _web_export_dir() -> String:
	var cfg := ConfigFile.new()
	if cfg.load(PROJECT_ROOT + "export_presets.cfg") != OK:
		return ""
	for section in cfg.get_sections():
		if cfg.get_value(section, "name", "") == "Web":
			var p: String = cfg.get_value(section, "export_path", "")
			if p != "":
				return p.get_base_dir().replace("\\", "/")
	return ""
