extends Node
## 章节资源包（.pck）下载与挂载层 —— Web 分包地基。
##
## 设计：业务层（ScriptInterpreter/ChapterLoader/PortraitLayer/Game）只通过 res:// 全局
## 路径引用资源，对"资源在哪个包里"无感知。本层在进入某章前负责把该章资源包挂载到 res://。
##
## - 桌面/Steam：所有章节资源已在主 PCK 内，ensure_chapter() 为 no-op（仅记账）。
## - Web：主 PCK 只含引擎 + 核心资源 + 首章；后续章节按需从 PACK_BASE_URL 下载 <stem>.pck
##   到 user://packs/，用 ProjectSettings.load_resource_pack 挂载。挂载后 pck 内的资源以其
##   原始全局路径（如 assets/portraits/陈默.沉重.png）暴露，与 manifest 一致。
##
## 章资源清单见 data/chapter_packs.json（chapter-publisher 发布时产出）；每个章包内含该章
## 用到的全部资源，路径与全局 manifest 一致，故跨章复用的资源在各章包内各自存在副本。
##
## ⚠️ V1 限制：本层仅在开局（ScriptInterpreter.start）与读档（restore）触发。跨章 jump
## （剧本 op=jump 带 file=）目前未接 ensure_chapter——V1 无跨章内容；启用跨章时需把
## ScriptInterpreter.resolve_target 的 file 分支也改成 await ensure_chapter。

signal pack_mounted(stem: String)
signal pack_failed(stem: String)

## Web 端章包来源 URL 前缀。空串 = 与页面同源（相对路径），托管时把 *.pck 放在 index.html 同目录。
const PACK_BASE_URL := ""
const PACK_DIR := "user://packs/"

var _mounted: Dictionary = {}   # stem -> true（已挂载）
var _http: HTTPRequest = null


func _ready() -> void:
	_http = HTTPRequest.new()
	add_child(_http)


## 进入章节前调用。幂等：已挂载直接返回。桌面端 no-op。
## 含 await（Web 端下载），调用方应 `await ChapterPackLoader.ensure_chapter(stem)`。
func ensure_chapter(stem: String) -> void:
	if _mounted.has(stem):
		return
	if not OS.has_feature("web"):
		# 桌面：资源在主 PCK，无需下载挂载
		_mounted[stem] = true
		return
	# Web：下载 + 挂载（_fetch_and_mount 含 await 是协程，须 await）
	if await _fetch_and_mount(stem):
		pack_mounted.emit(stem)
	else:
		pack_failed.emit(stem)


func _fetch_and_mount(stem: String) -> bool:
	DirAccess.make_dir_recursive_absolute(PACK_DIR)
	var packed_name := "%s.pck" % stem
	var local_path := PACK_DIR + packed_name
	# 已缓存（玩家上次玩过）则跳过下载，直接挂载
	if not FileAccess.file_exists(local_path):
		if not await _download(packed_name, local_path):
			return false
	# 挂载到 res://（replace=false：与主包资源合并，不替换）
	var ok := ProjectSettings.load_resource_pack(local_path, false)
	if not ok:
		push_error("ChapterPackLoader: load_resource_pack 失败 %s" % local_path)
		return false
	_mounted[stem] = true
	return true


func _download(packed_name: String, dest_local: String) -> bool:
	var url := "%s/%s" % [PACK_BASE_URL, packed_name] if PACK_BASE_URL != "" else packed_name
	var err := _http.request(url)
	if err != OK:
		push_error("ChapterPackLoader: HTTP 请求失败 %s (%d)" % [url, err])
		return false
	# result: [result, response_code, headers, body]
	var result: Array = await _http.request_completed
	var res_code: int = result[0]
	var http_code: int = result[1]
	var body: PackedByteArray = result[3]
	if res_code != HTTPRequest.RESULT_SUCCESS or http_code != 200:
		push_error("ChapterPackLoader: 下载失败 %s (result=%d http=%d)" % [url, res_code, http_code])
		return false
	var f := FileAccess.open(dest_local, FileAccess.WRITE)
	if f == null:
		push_error("ChapterPackLoader: 无法写入 %s" % dest_local)
		return false
	f.store_buffer(body)
	f.close()
	return true
