#!/usr/bin/env python3
"""
角色美术管理仪表盘 - 他者之镜
适配 2-step status (0→1→2) + approve 审批流程
Usage: python art_dashboard.py [--port 8765]
"""

import os
import sys
import json
import time
import argparse
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

# ── Import Neo4jClient ────────────────────────────────────────
_PLUGIN_CANDIDATES = [
    r"c:\Users\crazy\.claude\plugins\cache\game-builder\char-design\1.0.0\skills\neo4j-helper\scripts",
    r"D:\project\GameBuilder\plugins\char-design\skills\neo4j-helper\scripts",
]
for _p in _PLUGIN_CANDIDATES:
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from neo4j_client import Neo4jClient

# ── Configuration ───────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"
DEFAULT_PORT = 8765
REFRESH_INTERVAL_SEC = 30
DRAFTS_DIR = os.path.join(PROJECT_ROOT, "01_叙事数据", "drafts")

client: Neo4jClient = None


# ═══════════════════════════════════════════════════════════════
# Cypher Queries
# ═══════════════════════════════════════════════════════════════

# ── Overview: characters + data nodes + DesignSheet ──
STATUS_QUERY = """
MATCH (c:Character)
OPTIONAL MATCH (c)-[:has_appearance]->(ap:AppearanceStyle)
OPTIONAL MATCH (c)-[:has_voice_style]->(ls:LanguageStyle)
OPTIONAL MATCH (ap)-[:produces]->(ds:DesignSheet)
RETURN c.id AS char_id, c.name AS char_name,
       ap.id AS appearance_id, ap.status AS appearance_status,
       ls.id AS language_id, ls.status AS language_status,
       ds.id AS design_id, ds.status AS design_status,
       ds.approve AS design_approve,
       ds.image_path AS design_image
ORDER BY c.id
"""

# ── CostumeStyle: N per character ──
COSTUME_QUERY = """
MATCH (c:Character)
OPTIONAL MATCH (c)-[:has_costume]->(co:CostumeStyle)
RETURN c.id AS char_id,
       collect({id: co.id, status: co.status, name: co.name, approve: co.approve}) AS costumes
"""

# ── CostumeStyle approval queue ──
COSTUME_APPROVAL_QUERY = """
MATCH (c:Character)-[:has_costume]->(co:CostumeStyle)
WHERE co.approve = 'pending'
RETURN c.id AS char_id, c.name AS char_name,
       co.id AS costume_id, co.name AS costume_name,
       co.default_outfit AS outfit, co.accessories AS accessories
ORDER BY co.id
"""

# ── IllusDesign + StandingIllustration ──
DOWNSTREAM_QUERY = """
MATCH (ds:DesignSheet)-[r1:produces]->(id:IllusDesign)
OPTIONAL MATCH (id)-[:expands_to]->(si:StandingIllustration)
RETURN ds.id AS design_id,
       id.id AS illus_id, id.status AS illus_status,
       id.approve AS illus_approve, id.image_path AS illus_image,
       collect(DISTINCT {
           id: si.id, status: si.status, approve: si.approve,
           image_path: si.image_path, label: si.variant_label
       }) AS stands
"""

# ── sync=false edge approval queue ──
SYNC_APPROVAL_QUERY = """
MATCH (a)-[r]->(b)
WHERE type(r) IN ['produces','outfit_for']
  AND (r.sync = false OR r.sync IS NULL)
  AND labels(b)[0] = 'IllusDesign'
RETURN type(r) AS edge_type,
       labels(a)[0] AS from_label, a.id AS from_id,
       COALESCE(a.name, a.id) AS from_name,
       b.id AS to_id
ORDER BY b.id
"""

# ── Image approval queue (approve = pending) ──
IMAGE_APPROVAL_QUERY = """
MATCH (n)
WHERE n.approve = 'pending'
  AND (n:DesignSheet OR n:IllusDesign OR n:StandingIllustration)
RETURN labels(n)[0] AS type, n.id AS id, n.image_path AS image_path
ORDER BY n.id
"""

# ── Single node detail ──
NODE_QUERY = """
MATCH (n {id: $node_id})
RETURN labels(n)[0] AS type, properties(n) AS props
"""

# ── Node update ──
UPDATE_NODE_CYPHER = """
MATCH (n {id: $node_id})
SET n += $props
RETURN n.id AS id
"""

# ── Cascade preview (sync <> false) ──
CASCADE_PREVIEW_CYPHER = """
MATCH path = (source {id: $node_id})-[r*1..6]->(downstream)
WHERE ALL(rel IN relationships(path) WHERE rel.sync <> false)
  AND downstream.status IS NOT NULL
RETURN DISTINCT labels(downstream)[0] AS type, downstream.id AS id
"""

CASCADE_RESET_CYPHER = """
MATCH path = (source {id: $node_id})-[r*1..6]->(downstream)
WHERE ALL(rel IN relationships(path) WHERE rel.sync <> false)
  AND downstream.status IS NOT NULL
WITH DISTINCT downstream
SET downstream.status = 0, downstream.approve = null
RETURN labels(downstream)[0] AS type, downstream.id AS id
"""

# ── Approve / Reject node ──
APPROVE_NODE_CYPHER = "MATCH (n {id: $node_id}) SET n.approve = 'approved' RETURN n.id AS id"
REJECT_NODE_CYPHER = "MATCH (n {id: $node_id}) SET n.status = 0, n.approve = null RETURN n.id AS id"
SYNC_APPROVE_CYPHER = """
MATCH (a {id: $from_id})-[r]->(b {id: $to_id})
WHERE type(r) = $edge_type
SET r.sync = true
RETURN type(r) AS edge_type
"""


# ═══════════════════════════════════════════════════════════════
# Data Processing
# ═══════════════════════════════════════════════════════════════

def get_full_status():
    characters = client.run(STATUS_QUERY)
    # Deduplicate by char_id (Cartesian product from multiple OPTIONAL MATCH)
    seen = set()
    deduped = []
    for c in characters:
        if c["char_id"] not in seen:
            seen.add(c["char_id"])
            deduped.append(c)
    characters = deduped
    costumes_rows = client.run(COSTUME_QUERY)
    downstream = client.run(DOWNSTREAM_QUERY)
    sync_approvals = [a for a in client.run(SYNC_APPROVAL_QUERY) if a.get("from_id")]
    image_approvals = client.run(IMAGE_APPROVAL_QUERY)
    costume_approvals = client.run(COSTUME_APPROVAL_QUERY)

    # Costume lookup: char_id -> [costume_info]
    costume_map = {}
    for row in costumes_rows:
        cid = row.get("char_id")
        cos = row.get("costumes") or []
        costume_map[cid] = [c for c in cos if c.get("id")]

    # Downstream lookup: design_id -> [illus_info], illus_id -> [stand_info]
    illus_by_design = {}
    stands_by_illus = {}
    for row in downstream:
        did = row.get("design_id")
        iid = row.get("illus_id")
        if did and iid:
            illus_by_design.setdefault(did, []).append({
                "id": iid, "status": row["illus_status"],
                "approve": row.get("illus_approve"),
                "image_path": row.get("illus_image"),
                "scene_id": row.get("scene_id"),
                "scene_name": row.get("scene_name"),
            })
            for s in (row.get("stands") or []):
                if s and s.get("id"):
                    stands_by_illus.setdefault(iid, []).append(s)

    # Merge into characters
    for char in characters:
        did = char.get("design_id")
        char["costumes"] = costume_map.get(char["char_id"], [])
        illus_list = illus_by_design.get(did, [])
        char["illus"] = illus_list
        all_stands = []
        for il in illus_list:
            all_stands.extend(stands_by_illus.get(il["id"], []))
        char["stands"] = all_stands

    todos = _derive_todos(characters)

    return {
        "characters": characters,
        "todos": todos,
        "sync_approvals": sync_approvals,
        "image_approvals": image_approvals,
        "costume_approvals": costume_approvals,
        "total": len(characters),
        "completed": sum(1 for c in characters if _is_complete(c)),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _is_complete(char):
    return (
        char.get("appearance_status") is not None and char["appearance_status"] >= 1
        and char.get("language_status") is not None and char["language_status"] >= 1
        and all(c.get("status") is not None and c["status"] >= 1 for c in char.get("costumes", []))
        and char.get("design_status") is not None and char["design_status"] >= 2
        and char.get("design_approve") == "approved"
    )


def _derive_todos(characters):
    todos = []
    for char in characters:
        cid, name = char["char_id"], char["char_name"]
        ap_s = char.get("appearance_status")
        co_list = char.get("costumes", [])
        ls_s = char.get("language_status")

        # ── Stage 1a: AppearanceStyle + LanguageStyle (concept-designer) ──
        concept_ok = (
            (ap_s is not None and ap_s >= 1)
            and (ls_s is not None and ls_s >= 1)
        )
        if not concept_ok:
            todos.append({
                "char_id": cid, "char_name": name,
                "node_type": "数据节点", "node_type_cn": "外貌+语言",
                "status": "missing",
                "action": "concept-designer", "action_cn": "概念设计",
                "prompt": f"为 {cid} ({name}) 构建美术图",
            })
            continue

        # ── Stage 1b: CostumeStyle (costume-designer) ──
        costume_ok = (
            len(co_list) > 0
            and all(c.get("status") is not None and c["status"] >= 1 for c in co_list)
            and all(c.get("approve") in (None, "approved") for c in co_list)
        )
        if not costume_ok:
            has_pending = any(c.get("approve") == "pending" for c in co_list)
            todos.append({
                "char_id": cid, "char_name": name,
                "node_type": "着装", "node_type_cn": "着装",
                "status": "pending" if has_pending else "missing",
                "action": "costume-designer", "action_cn": "着装设计",
                "prompt": f"为 {cid} ({name}) 设计着装方案",
            })
            continue

        # ── Stage 2-4: DesignSheet pipeline ──
        ds = char.get("design_status")
        ds_ap = char.get("design_approve")
        if ds is None or ds == 0:
            todos.append(_todo(cid, name, "DesignSheet", "设计图",
                                "missing" if ds is None else "0",
                                "design-sheet", "设计图",
                                f"处理 {char.get('design_id', cid)}"))
            continue
        if ds == 1:
            todos.append(_todo(cid, name, "DesignSheet", "设计图", "1",
                                "image-generator", "图片生成",
                                f"为 {char.get('design_id')} 生成图片"))
            continue
        if ds == 2 and ds_ap != "approved":
            todos.append(_todo(cid, name, "DesignSheet", "设计图", "2",
                                "approve", "待审批",
                                "", approve=ds_ap))
            continue

        # ── Stage 6-9: IllusDesign pipeline ──
        illus = char.get("illus", [])
        if not illus:
            todos.append(_todo(cid, name, "IllusDesign", "立绘设计图", "missing",
                                "art-prompter", "创建立绘设计",
                                f"为 {cid} ({name}) 创建立绘设计图"))
            continue

        pending_illus = [il for il in illus if il["status"] is None or il["status"] < 2 or il.get("approve") != "approved"]
        if pending_illus:
            for il in pending_illus[:3]:
                il_s = il["status"]
                il_ap = il.get("approve")
                if il_s is None or il_s == 0:
                    todos.append(_todo(cid, name, "IllusDesign", "立绘设计",
                                        "missing" if il_s is None else "0",
                                        "illus-designer", "立绘设计", f"处理 {il['id']}"))
                elif il_s == 1:
                    todos.append(_todo(cid, name, "IllusDesign", "立绘设计", "1",
                                        "image-generator", "图片生成", f"为 {il['id']} 生成图片"))
                elif il_s == 2 and il_ap != "approved":
                    todos.append(_todo(cid, name, "IllusDesign", "立绘设计", "2",
                                        "approve", "待审批", "", approve=il_ap))
            continue

        # ── Stage 10+: StandingIllustration ──
        stands = char.get("stands", [])
        if not stands:
            todos.append(_todo(cid, name, "StandingIllustration", "立绘变体", "missing",
                                "stand-designer", "创建立绘",
                                f"为 {cid} ({name}) 处理立绘变体"))
    return todos


def _todo(cid, name, ntype, ntype_cn, status, action, action_cn, prompt, approve=None):
    return {
        "char_id": cid, "char_name": name,
        "node_type": ntype, "node_type_cn": ntype_cn,
        "status": status, "action": action, "action_cn": action_cn,
        "prompt": prompt, "approve": approve,
    }


# ═══════════════════════════════════════════════════════════════
# Draft Management (Narrative Growth)
# ═══════════════════════════════════════════════════════════════

def _parse_frontmatter(content):
    """Extract YAML frontmatter as dict from markdown content."""
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    yaml_text = content[3:end].strip()
    fm = {}
    for line in yaml_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip().strip('"').strip("'")
            fm[key.strip()] = val
    return fm


def _update_draft_status_on_disk(filepath, new_status):
    """Update the status field in a draft's YAML frontmatter."""
    import re
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(
        r"^(status:\s*).+$", f"status: {new_status}",
        content, count=1, flags=re.MULTILINE,
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def get_all_drafts():
    """List all draft .md files with parsed frontmatter."""
    if not os.path.isdir(DRAFTS_DIR):
        return []
    drafts = []
    for fname in sorted(os.listdir(DRAFTS_DIR)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(DRAFTS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            fm = _parse_frontmatter(content)
            if fm:
                drafts.append({
                    "filename": fname,
                    "path": fpath,
                    "draft_id": fm.get("draft_id", fname),
                    "status": fm.get("status", "unknown"),
                    "priority": fm.get("priority", ""),
                    "title": fm.get("title", fname.replace(".md", "")),
                    "created_at": fm.get("created_at", ""),
                    "opportunity_type": fm.get("opportunity_type", ""),
                })
        except Exception:
            drafts.append({"filename": fname, "path": fpath, "status": "error",
                           "title": fname, "priority": "", "draft_id": fname})
    return drafts


def get_draft_content(draft_id):
    """Read full draft content by filename or draft_id."""
    if not os.path.isdir(DRAFTS_DIR):
        return None
    for fname in os.listdir(DRAFTS_DIR):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(DRAFTS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            fm = _parse_frontmatter(content)
            did = fm.get("draft_id", "") if fm else ""
            if fname == draft_id or did == draft_id or fname.replace(".md", "") == draft_id:
                return {"frontmatter": fm, "content": content, "path": fpath, "filename": fname}
        except Exception:
            continue
    return None


# ═══════════════════════════════════════════════════════════════
# HTTP Server
# ═══════════════════════════════════════════════════════════════

class DashboardHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            self._send_html(HTML_PAGE)
        elif path == "/api/status":
            self._json(get_full_status())
        elif path == "/api/drafts":
            self._json({"drafts": get_all_drafts()})
        elif path.startswith("/api/drafts/"):
            draft_id = path.split("/api/drafts/")[1].rstrip("/")
            result = get_draft_content(draft_id)
            if result:
                self._json(result)
            else:
                self._json({"error": "草案不存在"}, 404)
        elif path.startswith("/api/node/"):
            node_id = path.split("/api/node/")[1].rstrip("/")
            if node_id.endswith("/cascade"):
                node_id = node_id.rstrip("/cascade")
                self._json(client.run(CASCADE_PREVIEW_CYPHER, {"node_id": node_id}))
            else:
                rows = client.run(NODE_QUERY, {"node_id": node_id})
                self._json(rows[0] if rows else {"error": "节点不存在"})
        elif path.startswith("/file/"):
            self._serve_file(path[6:])

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        body = self._read_json()
        try:
            if path == "/api/approve/node":
                r = client.run(APPROVE_NODE_CYPHER, {"node_id": body["node_id"]})
                self._json({"success": bool(r)})
            elif path == "/api/reject/node":
                r = client.run(REJECT_NODE_CYPHER, {"node_id": body["node_id"]})
                self._json({"success": bool(r)})
            elif path == "/api/approve/sync":
                r = client.run(SYNC_APPROVE_CYPHER, body)
                self._json({"success": bool(r)})
            elif path.startswith("/api/drafts/") and path.endswith("/approve"):
                draft_id = path.split("/api/drafts/")[1].rstrip("/approve")
                result = get_draft_content(draft_id)
                if not result:
                    self._json({"error": "草案不存在"}, 404); return
                _update_draft_status_on_disk(result["path"], "approved")
                self._json({"success": True, "draft_id": draft_id, "status": "approved"})
            elif path.startswith("/api/drafts/") and path.endswith("/reject"):
                draft_id = path.split("/api/drafts/")[1].rstrip("/reject")
                result = get_draft_content(draft_id)
                if not result:
                    self._json({"error": "草案不存在"}, 404); return
                _update_draft_status_on_disk(result["path"], "rejected")
                self._json({"success": True, "draft_id": draft_id, "status": "rejected"})
            else:
                self.send_error(404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def do_PUT(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/api/node/"):
            node_id = path.split("/api/node/")[1].rstrip("/")
            body = self._read_json()
            props = {k: v for k, v in body.get("props", {}).items() if k not in ("id", "status", "approve")}
            cascade = client.run(CASCADE_PREVIEW_CYPHER, {"node_id": node_id})
            client.run(UPDATE_NODE_CYPHER, {"node_id": node_id, "props": props})
            reset = client.run(CASCADE_RESET_CYPHER, {"node_id": node_id})
            self._json({"success": True, "cascade_reset": reset})
        else:
            self.send_error(404)

    def _serve_file(self, rel):
        fp = os.path.normpath(os.path.join(PROJECT_ROOT, rel))
        if not fp.startswith(PROJECT_ROOT) or not os.path.isfile(fp):
            self.send_error(404); return
        mime = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        with open(fp, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _send_html(self, h):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(h.encode("utf-8"))

    def _json(self, d, s=200):
        b = json.dumps(d, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(s)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


# ═══════════════════════════════════════════════════════════════
# HTML
# ═══════════════════════════════════════════════════════════════

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>角色美术管理 - 他者之镜</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
body{font-family:'Microsoft YaHei','Segoe UI',sans-serif}
.pulse{animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.fade-in{animation:fadeIn .3s ease-in}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.slide-in{animation:slideIn .25s ease-out}
@keyframes slideIn{from{transform:translateX(100%)}to{transform:translateX(0)}}
textarea.fi{min-height:60px;resize:vertical}
</style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
<div class="max-w-full mx-auto px-6 py-6">

<!-- Header -->
<div class="flex items-center justify-between mb-6">
  <h1 class="text-2xl font-bold text-amber-400">🎭 角色美术管理面板 <span class="text-base text-gray-500">他者之镜</span></h1>
  <div class="flex items-center gap-4 text-sm">
    <span id="ts" class="text-gray-400"></span>
    <button onclick="load()" class="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-gray-200">🔄 刷新</button>
  </div>
</div>

<!-- Stats -->
<div class="grid grid-cols-6 gap-3 mb-6">
  <div class="bg-gray-800 rounded-lg p-3 border border-gray-700"><div class="text-gray-400 text-xs mb-1">总角色</div><div id="s-t" class="text-2xl font-bold">-</div></div>
  <div class="bg-gray-800 rounded-lg p-3 border border-gray-700"><div class="text-gray-400 text-xs mb-1">已完成</div><div id="s-d" class="text-2xl font-bold text-green-400">-</div></div>
  <div class="bg-gray-800 rounded-lg p-3 border border-gray-700"><div class="text-gray-400 text-xs mb-1">待办</div><div id="s-todo" class="text-2xl font-bold text-amber-400">-</div></div>
  <div class="bg-gray-800 rounded-lg p-3 border border-gray-700"><div class="text-gray-400 text-xs mb-1">图片待审批</div><div id="s-ia" class="text-2xl font-bold text-red-400">-</div></div>
  <div class="bg-gray-800 rounded-lg p-3 border border-gray-700"><div class="text-gray-400 text-xs mb-1">sync待审批</div><div id="s-sa" class="text-2xl font-bold text-orange-400">-</div></div>
  <div class="bg-gray-800 rounded-lg p-3 border border-gray-700"><div class="text-gray-400 text-xs mb-1">叙事草案</div><div id="s-draft" class="text-2xl font-bold text-cyan-400">-</div></div>
</div>

<!-- Overview -->
<div class="bg-gray-800 rounded-lg p-5 mb-6 border border-gray-700">
  <h2 class="text-lg font-semibold text-amber-300 mb-4">📊 进度总览 <span class="text-sm font-normal text-gray-400">（点击状态徽标编辑节点）</span></h2>
  <div class="overflow-x-auto"><table class="w-full text-sm">
    <thead><tr class="border-b border-gray-600 text-gray-300">
      <th class="px-3 py-2 text-left w-28">角色</th>
      <th class="px-3 py-2 text-center w-20">外貌</th>
      <th class="px-3 py-2 text-center w-20">着装</th>
      <th class="px-3 py-2 text-center w-20">语言</th>
      <th class="px-3 py-2 text-center w-28">设计图</th>
      <th class="px-3 py-2 text-center w-40">预览</th>
      <th class="px-3 py-2 text-center">立绘设计</th>
      <th class="px-3 py-2 text-center">立绘</th>
    </tr></thead>
    <tbody id="ov"></tbody>
  </table></div>
  <div class="mt-3 flex gap-3 text-xs text-gray-500 flex-wrap">
    <span class="px-2 py-0.5 rounded bg-gray-600 text-gray-300">0/未创建</span>
    <span class="px-2 py-0.5 rounded bg-blue-800 text-blue-200">1 属性/提示词</span>
    <span class="px-2 py-0.5 rounded bg-green-800 text-green-200">2 图片已生成</span>
    <span class="px-2 py-0.5 rounded bg-amber-800 text-amber-200">⏳ 待审批</span>
    <span class="px-2 py-0.5 rounded bg-green-700 text-green-100">✓ 已通过</span>
    <span class="px-2 py-0.5 rounded bg-red-800 text-red-200">✗ 已驳回</span>
  </div>
</div>

<!-- TODOs -->
<div class="bg-gray-800 rounded-lg p-5 mb-6 border border-gray-700">
  <h2 class="text-lg font-semibold text-amber-300 mb-4">📝 待办事项</h2>
  <table class="w-full text-sm"><thead><tr class="border-b border-gray-600 text-gray-300">
    <th class="px-3 py-2 text-left w-28">角色</th>
    <th class="px-3 py-2 text-left w-32">节点</th>
    <th class="px-3 py-2 text-center w-20">状态</th>
    <th class="px-3 py-2 text-left w-24">下一步</th>
    <th class="px-3 py-2 text-center w-28">操作</th>
  </tr></thead><tbody id="todo"></tbody></table>
  <div id="todo-e" class="hidden text-center text-gray-500 py-6">🎉 所有任务已完成！</div>
</div>

<!-- Costume Approvals -->
<div class="bg-gray-800 rounded-lg p-5 mb-6 border border-gray-700">
  <h2 class="text-lg font-semibold text-purple-300 mb-4">👔 着装审批 <span class="text-sm font-normal text-gray-400">(costume-designer 建议)</span></h2>
  <div id="ca-list"></div>
  <div id="ca-e" class="hidden text-center text-gray-500 py-6">✓ 无待审批着装</div>
</div>

<!-- Image Approvals -->
<div class="bg-gray-800 rounded-lg p-5 mb-6 border border-gray-700">
  <h2 class="text-lg font-semibold text-amber-300 mb-4">🖼️ 图片审批 <span class="text-sm font-normal text-gray-400">(approve = pending)</span></h2>
  <div id="ia-list"></div>
  <div id="ia-e" class="hidden text-center text-gray-500 py-6">✓ 无待审批图片</div>
</div>

<!-- Sync Approvals -->
<div class="bg-gray-800 rounded-lg p-5 mb-6 border border-gray-700">
  <h2 class="text-lg font-semibold text-amber-300 mb-4">🔗 sync 审批 <span class="text-sm font-normal text-gray-400">(sync = false)</span></h2>
  <table class="w-full text-sm"><thead><tr class="border-b border-gray-600 text-gray-300">
    <th class="px-3 py-2 text-left">上游</th><th class="px-3 py-2 text-center w-28">边</th>
    <th class="px-3 py-2 text-left">下游</th><th class="px-3 py-2 text-center w-28">操作</th>
  </tr></thead><tbody id="sa"></tbody></table>
  <div id="sa-e" class="hidden text-center text-gray-500 py-6">✓ 无待审批</div>
</div>

<!-- Narrative Draft Approvals -->
<div class="bg-gray-800 rounded-lg p-5 mb-6 border border-gray-700">
  <h2 class="text-lg font-semibold text-cyan-300 mb-4">📖 叙事审批 <span class="text-sm font-normal text-gray-400">(叙事自增长草案)</span></h2>
  <div id="draft-list"></div>
  <div id="draft-e" class="hidden text-center text-gray-500 py-6">✓ 暂无叙事草案</div>
</div>

</div>

<!-- ═══ Detail Side Panel ═══ -->
<div id="po" class="hidden fixed inset-0 z-40 bg-black/60" onclick="closeP()"></div>
<div id="pn" class="hidden fixed right-0 top-0 bottom-0 z-50 w-[560px] border-l border-gray-700 overflow-y-auto slide-in" style="background:#1a1f2e">
  <div class="sticky top-0 z-10 bg-gray-900/95 backdrop-blur border-b border-gray-700 px-5 py-3 flex justify-between items-center">
    <h2 id="pn-t" class="text-lg font-bold text-amber-300"></h2>
    <button onclick="closeP()" class="text-gray-400 hover:text-white text-2xl leading-none">&times;</button>
  </div>
  <div id="pn-b" class="p-5"></div>
</div>

<!-- Confirm Dialog -->
<div id="cf" class="hidden fixed inset-0 z-[60] bg-black/70 flex items-center justify-center">
  <div class="bg-gray-800 rounded-xl p-6 max-w-md border border-gray-600 shadow-2xl">
    <h3 class="text-lg font-semibold text-amber-300 mb-2">确认操作</h3>
    <div id="cf-m" class="text-sm text-gray-300 mb-4"></div>
    <div class="flex gap-3 justify-end">
      <button onclick="cfN()" class="px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded text-sm">取消</button>
      <button id="cf-y" onclick="cfY()" class="px-4 py-2 bg-amber-700 hover:bg-amber-600 rounded text-sm text-white font-semibold">确认</button>
    </div>
  </div>
</div>

<div id="err" class="hidden fixed bottom-0 inset-x-0 bg-red-900/95 text-white text-center py-3 text-sm backdrop-blur z-30">
  <span id="err-m"></span><button onclick="this.parentElement.classList.add('hidden')" class="ml-3 underline">关闭</button>
</div>

<script>
const RMS=30000;let _t=null,_cr=null;

/* ═══ Node Schemas ═══ */
const NF={
  AppearanceStyle:{l:'外貌特征',i:'👤',f:[
    {k:'appearance',l:'外貌描述',t:'textarea'},
    {k:'color_direction',l:'主色调'},{k:'shape_language',l:'形状语言'},
    {k:'visual_tone',l:'视觉气质'},{k:'first_impression',l:'第一印象'},
    {k:'memory_points',l:'记忆点'},
  ]},
  CostumeStyle:{l:'着装特征',i:'👔',f:[
    {k:'name',l:'名称'},{k:'default_outfit',l:'默认着装',t:'textarea'},
    {k:'material_direction',l:'材质方向'},{k:'posture',l:'体态气质'},{k:'accessories',l:'配饰'},
    {k:'approve',l:'审批状态'},
  ]},
  LanguageStyle:{l:'语言风格',i:'🗣️',f:[
    {k:'description',l:'语言风格描述',t:'textarea'},
  ]},
  DesignSheet:{l:'设计图',i:'📐',f:[
    {k:'prompt',l:'提示词',t:'textarea'},{k:'image_path',l:'图片路径',t:'image'},
  ]},
  IllusDesign:{l:'立绘设计图',i:'🎨',f:[
    {k:'adaptation_notes',l:'着装补充说明',t:'textarea'},
    {k:'prompt',l:'提示词',t:'textarea'},{k:'image_path',l:'图片路径',t:'image'},
  ]},
  StandingIllustration:{l:'立绘',i:'🖼️',f:[
    {k:'variant_label',l:'变体标签'},{k:'expression',l:'表情'},
    {k:'pose',l:'姿势'},{k:'prompt',l:'提示词',t:'textarea'},{k:'image_path',l:'图片路径',t:'image'},
  ]},
};

/* status config: data nodes max=1, image nodes max=2 (0待生成→1提示词完成→2图片生成完成) */
const SM={AppearanceStyle:1,CostumeStyle:1,LanguageStyle:1,DesignSheet:2,IllusDesign:2,StandingIllustration:2};
const SL={0:'待处理',1:'属性已填',2:'图片已生成'};
const SC={0:'bg-yellow-800 text-yellow-200',1:'bg-blue-800 text-blue-200',2:'bg-green-800 text-green-200'};

async function api(p,o){const r=await fetch(p,o);if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}

/* ═══ Load ═══ */
async function load(){
  try{
    const d=await api('/api/status');
    if(d.error)throw new Error(d.error);
    $('s-t').textContent=d.total;$('s-d').textContent=d.completed;
    $('s-todo').textContent=d.todos.length;
    $('s-ia').textContent=d.image_approvals.length;
    $('s-sa').textContent=d.sync_approvals.length;
    rOv(d.characters);rTodo(d.todos);rCA(d.costume_approvals||[]);rIA(d.image_approvals);rSA(d.sync_approvals);
    $('ts').textContent=d.timestamp;
    $('err').classList.add('hidden');
    // Load drafts
    loadDrafts();
  }catch(e){$('err-m').textContent='⚠ '+e.message;$('err').classList.remove('hidden');}
}

/* ═══ Overview ═══ */
function rOv(chars){
  $('ov').innerHTML=chars.map(c=>{
    const imgH=c.design_image?`<img src="/file/${enc(c.design_image)}" class="h-20 rounded border border-gray-600 object-contain bg-gray-900 cursor-pointer" onclick="event.stopPropagation();openP('${c.design_id}','DesignSheet')" onerror="this.style.display='none';this.nextElementSibling.style.display=''" /><div style="display:none" class="text-xs text-gray-600 italic">${esc(c.design_image)}</div>`:'<span class="text-gray-600 text-xs">--</span>';
    const cosH=(c.costumes||[]).length?`<span class="text-xs ${c.costumes.every(x=>x.status>=1)?'bg-green-800 text-green-200':'bg-yellow-800 text-yellow-200'} px-1.5 py-0.5 rounded cursor-pointer" onclick="event.stopPropagation();openP('${c.costumes[0].id}','CostumeStyle')">${c.costumes.length}套</span>`:dataBadge(null,1);
    return `<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 fade-in">
      <td class="px-3 py-2"><div class="font-medium">${esc(c.char_name)}</div><div class="text-xs text-gray-500">${c.char_id}</div></td>
      <td class="px-3 py-2 text-center">${dataBadge(c.appearance_status,1,c.appearance_id,'AppearanceStyle')}</td>
      <td class="px-3 py-2 text-center">${cosH}</td>
      <td class="px-3 py-2 text-center">${dataBadge(c.language_status,1,c.language_id,'LanguageStyle')}</td>
      <td class="px-3 py-2 text-center">${imgBadge(c.design_status,2,c.design_approve,c.design_id,'DesignSheet')}</td>
      <td class="px-3 py-2 text-center">${imgH}</td>
      <td class="px-3 py-2 text-center">${rIllus(c.illus||[])}</td>
      <td class="px-3 py-2 text-center">${rStands(c.stands||[])}</td>
    </tr>`;
  }).join('');
}

function dataBadge(s,max,id,type){
  if(!id)return '<span class="text-gray-600 text-xs">--</span>';
  const cls=s===null||s===undefined?'bg-gray-600 text-gray-300':s>=max?'bg-green-800 text-green-200':'bg-yellow-800 text-yellow-200';
  const txt=s===null||s===undefined?'--':s>=max?'✓':s;
  return `<span class="cursor-pointer px-1.5 py-0.5 rounded text-xs ${cls} hover:ring-1 hover:ring-amber-400" onclick="event.stopPropagation();openP('${id}','${type}')">${txt}</span>`;
}

function imgBadge(s,max,ap,id,type){
  if(!id)return '<span class="text-gray-600 text-xs">--</span>';
  let cls,txt;
  if(s===null||s===undefined){cls='bg-gray-600 text-gray-300';txt='--';}
  else if(s>=max){
    if(ap==='approved'){cls='bg-green-700 text-green-100';txt='✓✓✓';}
    else if(ap==='rejected'){cls='bg-red-800 text-red-200';txt='✗✗✗';}
    else{cls='bg-amber-800 text-amber-200';txt='⏳2';}
  }else{cls=SC[s]||'bg-gray-600 text-gray-300';txt=String(s);}
  return `<span class="cursor-pointer px-1.5 py-0.5 rounded text-xs ${cls} hover:ring-1 hover:ring-amber-400" onclick="event.stopPropagation();openP('${id}','${type}')">${txt}</span>`;
}

function rIllus(a){return a.length?a.map(i=>imgBadge(i.status,2,i.approve,i.id,'IllusDesign')).join(' '):'<span class="text-gray-600 text-xs">--</span>';}
function rStands(a){return a.length?a.map(s=>imgBadge(s.status,2,s.approve,s.id,'StandingIllustration')).join(' '):'<span class="text-gray-600 text-xs">--</span>';}

/* ═══ TODOs ═══ */
function rTodo(todos){
  const tb=$('todo'),e=$('todo-e');
  if(!todos.length){tb.innerHTML='';e.classList.remove('hidden');return;}
  e.classList.add('hidden');
  tb.innerHTML=todos.map(t=>{
    const stH=t.status==='missing'?'<span class="px-2 py-0.5 rounded text-xs bg-gray-600 text-gray-300">未创建</span>':`<span class="px-2 py-0.5 rounded text-xs ${SC[t.status]||''}">${t.status}</span>`;
    let actH;
    if(t.action==='approve'){
      const apH=t.approve==='rejected'?'<span class="text-red-400">已驳回</span>':'<span class="text-amber-300">待审批</span>';
      actH=apH;
    }else{
      const uri='vscode://anthropic.claude-code/open?prompt='+encodeURIComponent(t.prompt);
      actH=`<a href="${uri}" class="inline-block px-3 py-1 bg-blue-700 hover:bg-blue-600 rounded text-white text-xs whitespace-nowrap">▶ 启动</a>`;
    }
    return `<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 fade-in">
      <td class="px-3 py-2"><div class="font-medium">${esc(t.char_name)}</div><div class="text-xs text-gray-500">${t.char_id}</div></td>
      <td class="px-3 py-2">${esc(t.node_type_cn)}</td>
      <td class="px-3 py-2 text-center">${stH}</td>
      <td class="px-3 py-2">${esc(t.action_cn)}</td>
      <td class="px-3 py-2 text-center">${actH}</td>
    </tr>`;
  }).join('');
}

/* ═══ Costume Approvals ═══ */
function rCA(list){
  const el=$('ca-list'),e=$('ca-e');
  if(!list.length){el.innerHTML='';e.classList.remove('hidden');return;}
  e.classList.add('hidden');
  el.innerHTML=list.map(a=>`<div class="bg-gray-750 rounded-lg border border-purple-900/50 p-4 mb-3" style="background:#252a3a">
    <div class="flex items-start justify-between">
      <div>
        <div class="font-medium text-purple-200">${esc(a.costume_name)}</div>
        <div class="text-xs text-gray-400 mt-1">${esc(a.char_name)} (${a.char_id})</div>
        ${a.outfit?`<div class="text-sm text-gray-300 mt-2">${esc(a.outfit)}</div>`:''}
        ${a.accessories?`<div class="text-xs text-gray-400 mt-1">配饰: ${esc(a.accessories)}</div>`:''}
      </div>
      <div class="flex gap-2 ml-4 shrink-0">
        <button onclick="doApproveNode('${a.costume_id}',this)" class="px-3 py-1.5 bg-green-800 hover:bg-green-700 rounded text-white text-xs font-medium">✓ 通过</button>
        <button onclick="doRejectNode('${a.costume_id}',this)" class="px-3 py-1.5 bg-red-800 hover:bg-red-700 rounded text-white text-xs font-medium">✗ 驳回</button>
      </div>
    </div>
  </div>`).join('');
}

/* ═══ Image Approvals ═══ */
function rIA(list){
  const el=$('ia-list'),e=$('ia-e');
  if(!list.length){el.innerHTML='';e.classList.remove('hidden');return;}
  e.classList.add('hidden');
  el.innerHTML='<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">'+list.map(a=>{
    const imgH=a.image_path?`<img src="/file/${enc(a.image_path)}" class="w-full rounded border border-gray-600 object-contain bg-gray-900 max-h-48" onerror="this.style.display='none'"/>`:'';
    return `<div class="bg-gray-750 rounded-lg border border-gray-700 p-3" style="background:#252a3a">
      <div class="text-xs text-gray-400 mb-2">${a.type}: ${a.id}</div>
      ${imgH}
      <div class="flex gap-2 mt-3">
        <button onclick="doApproveNode('${a.id}',this)" class="flex-1 px-2 py-1.5 bg-green-800 hover:bg-green-700 rounded text-white text-xs font-medium">✓ 通过</button>
        <button onclick="doRejectNode('${a.id}',this)" class="flex-1 px-2 py-1.5 bg-red-800 hover:bg-red-700 rounded text-white text-xs font-medium">✗ 驳回</button>
      </div>
    </div>`;
  }).join('')+'</div>';
}

/* ═══ Sync Approvals ═══ */
function rSA(list){
  const tb=$('sa'),e=$('sa-e');
  if(!list.length){tb.innerHTML='';e.classList.remove('hidden');return;}
  e.classList.add('hidden');
  tb.innerHTML=list.map(a=>`<tr class="border-b border-gray-700/50">
    <td class="px-3 py-2"><div class="font-medium">${esc(a.from_name)}</div><div class="text-xs text-gray-500">${a.from_label}: ${a.from_id}</div></td>
    <td class="px-3 py-2 text-center"><span class="px-2 py-0.5 rounded text-xs bg-amber-900 text-amber-200">${a.edge_type}</span></td>
    <td class="px-3 py-2 text-xs text-gray-400">${a.to_id}</td>
    <td class="px-3 py-2 text-center"><button onclick="doSyncApprove('${a.from_id}','${a.to_id}','${a.edge_type}',this)" class="px-3 py-1 bg-amber-700 hover:bg-amber-600 rounded text-white text-xs">✓ 批准</button></td>
  </tr>`).join('');
}

/* ═══ Detail Panel ═══ */
async function openP(nodeId,nodeType){
  $('pn-t').textContent=(NF[nodeType]||{l:nodeType}).l+' · '+nodeId;
  $('pn-b').innerHTML='<div class="text-gray-400 text-center py-8">加载中...</div>';
  $('po').classList.remove('hidden');$('pn').classList.remove('hidden');
  try{
    const d=await api('/api/node/'+nodeId);
    if(d.error)throw new Error(d.error);
    rPanel(d,nodeType);
  }catch(e){$('pn-b').innerHTML='<div class="text-red-400 py-8 text-center">'+esc(e.message)+'</div>';}
}
function closeP(){$('po').classList.add('hidden');$('pn').classList.add('hidden');}

function rPanel(detail,type){
  const schema=NF[type]||{l:type,i:'📋',f:[]};
  const props=detail.props||{};
  const maxS=SM[type]||1;
  const st=props.status;const ap=props.approve;
  let h='<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">';

  // Header
  h+=`<div class="flex items-center justify-between px-4 py-2.5 border-b border-gray-700" style="background:#252a3a">`;
  h+=`<div class="flex items-center gap-2"><span>${schema.i}</span><span class="font-semibold text-gray-200">${schema.l}</span><span class="text-xs text-gray-500">${props.id||''}</span></div>`;
  h+=`<div class="flex items-center gap-2">`;
  if(st!==undefined&&st!==null){
    const sl=SL[st]||('status='+st);const sc=SC[st]||'bg-gray-600 text-gray-300';
    h+=`<span class="px-2 py-0.5 rounded text-xs ${sc}">${sl}</span>`;
  }
  if(ap){
    const ac=ap==='approved'?'bg-green-700 text-green-100':ap==='rejected'?'bg-red-800 text-red-200':'bg-amber-800 text-amber-200';
    h+=`<span class="px-2 py-0.5 rounded text-xs ${ac}">${ap}</span>`;
  }
  h+=`</div></div>`;

  h+='<div class="px-4 py-3 space-y-2">';

  // Image preview
  for(const f of schema.f){
    if(f.t==='image'&&props[f.k]){
      h+=`<div class="mb-3"><div class="text-xs text-gray-400 mb-1">${esc(f.l)}</div>`;
      h+=`<img src="/file/${enc(props[f.k])}" class="max-w-full rounded border border-gray-600 max-h-64 object-contain bg-gray-900" onerror="this.style.display='none';this.nextElementSibling.style.display=''" />`;
      h+=`<div style="display:none" class="text-xs text-gray-500 italic">未找到: ${esc(props[f.k])}</div></div>`;
    }
  }

  // Editable fields
  for(const f of schema.f){
    if(f.t==='image')continue;
    const val=props[f.k]||'';
    const fid='f-'+f.k;
    if(f.t==='textarea'){
      h+=`<div><label class="text-xs text-gray-400 block mb-0.5">${esc(f.l)}</label>`;
      h+=`<textarea id="${fid}" class="fi w-full bg-gray-900 border border-gray-600 rounded px-2.5 py-1.5 text-sm text-gray-200 focus:border-amber-500 focus:outline-none">${esc(val)}</textarea></div>`;
    }else{
      h+=`<div><label class="text-xs text-gray-400 block mb-0.5">${esc(f.l)}</label>`;
      h+=`<input id="${fid}" type="text" value="${escA(val)}" class="w-full bg-gray-900 border border-gray-600 rounded px-2.5 py-1.5 text-sm text-gray-200 focus:border-amber-500 focus:outline-none" /></div>`;
    }
  }

  // Action buttons
  const nodeId=props.id||'';
  h+=`<div class="pt-3 flex gap-2 flex-wrap">`;
  h+=`<button onclick="saveNode('${nodeId}','${type}')" class="px-4 py-1.5 bg-amber-700 hover:bg-amber-600 rounded text-white text-sm font-medium">💾 保存</button>`;
  if(ap==='pending'){
    h+=`<button onclick="doApproveNode('${nodeId}');closeP();setTimeout(load,500)" class="px-4 py-1.5 bg-green-800 hover:bg-green-700 rounded text-white text-sm font-medium">✓ 通过</button>`;
    h+=`<button onclick="doRejectNode('${nodeId}');closeP();setTimeout(load,500)" class="px-4 py-1.5 bg-red-800 hover:bg-red-700 rounded text-white text-sm font-medium">✗ 驳回</button>`;
  }
  h+=`<span id="save-msg" class="text-xs text-gray-500 self-center ml-2"></span>`;
  h+=`</div>`;

  h+='</div></div>';
  $('pn-b').innerHTML=h;
}

/* ═══ Save Node ═══ */
async function saveNode(nodeId,type){
  const msg=$('save-msg');
  msg.textContent='检查级联...';msg.className='text-xs text-gray-400';
  const schema=NF[type]||{f:[]};
  const props={};
  for(const f of schema.f){if(f.t==='image')continue;const el=$('f-'+f.k);if(el)props[f.k]=el.value;}
  let cascade=[];
  try{cascade=await api('/api/node/'+nodeId+'/cascade');}catch(e){}
  let msgH='确认保存修改？';
  if(cascade.length)msgH+='<br/><br/>⚠️ 级联重置: '+cascade.map(c=>`<span class="px-1.5 py-0.5 rounded bg-red-900 text-red-200 text-xs m-0.5">${esc(c.type)}:${esc(c.id)}</span>`).join('');
  if(!await cfShow(msgH)){msg.textContent='已取消';msg.className='text-xs text-gray-500';return;}
  msg.textContent='保存中...';msg.className='text-xs text-amber-400';
  try{
    const r=await api('/api/node/'+nodeId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({props})});
    const n=(r.cascade_reset||[]).length;
    msg.textContent='✓ 已保存'+(n?' (重置 '+n+' 个下游)':'');msg.className='text-xs text-green-400';
    setTimeout(load,800);
  }catch(e){msg.textContent='✗ '+e.message;msg.className='text-xs text-red-400';}
}

/* ═══ Approve / Reject ═══ */
async function doApproveNode(id,btn){
  if(btn){btn.disabled=true;btn.textContent='处理中...';}
  try{await api('/api/approve/node',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({node_id:id})});
    if(btn){btn.textContent='✓ 已通过';btn.className='flex-1 px-2 py-1.5 rounded text-white text-xs font-medium bg-green-700';}
    setTimeout(load,600);
  }catch(e){if(btn)btn.textContent='✗ 失败';}
}
async function doRejectNode(id,btn){
  if(btn){btn.disabled=true;btn.textContent='处理中...';}
  try{await api('/api/reject/node',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({node_id:id})});
    if(btn){btn.textContent='✗ 已驳回';btn.className='flex-1 px-2 py-1.5 rounded text-white text-xs font-medium bg-red-700';}
    setTimeout(load,600);
  }catch(e){if(btn)btn.textContent='✗ 失败';}
}
async function doSyncApprove(fromId,toId,edgeType,btn){
  btn.disabled=true;btn.textContent='审批中...';btn.classList.add('pulse');
  try{const r=await api('/api/approve/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({from_id:fromId,to_id:toId,edge_type:edgeType})});
    btn.classList.remove('pulse');btn.textContent='✓ 已批准';btn.className='px-3 py-1 rounded text-white text-xs bg-green-700';setTimeout(load,800);
  }catch(e){btn.classList.remove('pulse');btn.textContent='✗ 失败';btn.className='px-3 py-1 rounded text-white text-xs bg-red-700';}
}

/* ═══ Confirm Dialog ═══ */
function cfShow(m){return new Promise(r=>{_cr=r;$('cf-m').innerHTML=m;$('cf').classList.remove('hidden');});}
function cfY(){$('cf').classList.add('hidden');if(_cr){_cr(true);_cr=null;}}
function cfN(){$('cf').classList.add('hidden');if(_cr){_cr(false);_cr=null;}}

/* ═══ Draft Management ═══ */
async function loadDrafts(){
  try{
    const d=await api('/api/drafts');
    if(d.error)throw new Error(d.error);
    const drafts=d.drafts||[];
    const pending=drafts.filter(x=>x.status==='pending').length;
    $('s-draft').textContent=pending;
    rDrafts(drafts);
  }catch(e){$('s-draft').textContent='?';}
}
function rDrafts(drafts){
  const el=$('draft-list'),e=$('draft-e');
  if(!drafts.length){el.innerHTML='';e.classList.remove('hidden');return;}
  e.classList.add('hidden');
  el.innerHTML=drafts.map(d=>{
    const pCls=d.priority==='high'?'bg-red-900 text-red-200':d.priority==='medium'?'bg-amber-900 text-amber-200':'bg-green-900 text-green-200';
    const pTxt=d.priority==='high'?'🔴 高':d.priority==='medium'?'🟡 中':'🟢 低';
    const sCls=d.status==='pending'?'bg-cyan-800 text-cyan-200':d.status==='approved'?'bg-green-700 text-green-100':d.status==='rejected'?'bg-red-800 text-red-200':d.status==='applied'?'bg-gray-600 text-gray-300':'bg-gray-700 text-gray-400';
    const sTxt=d.status==='pending'?'⏳ 待审批':d.status==='approved'?'✓ 已批准':d.status==='rejected'?'✗ 已驳回':d.status==='applied'?'✓✓✓ 已导入':d.status;
    let actH='';
    if(d.status==='pending'){
      actH=`<button onclick="doDraftAction('${d.filename}','approve',this)" class="px-3 py-1 bg-green-800 hover:bg-green-700 rounded text-white text-xs">✓ 批准</button>`;
      actH+=`<button onclick="doDraftAction('${d.filename}','reject',this)" class="px-3 py-1 bg-red-800 hover:bg-red-700 rounded text-white text-xs ml-1">✗ 驳回</button>`;
    } else if(d.status==='approved'){
      const applyCmd=`/narrative-grower apply --draft ${d.path.replace(/\\\\/g,'/')}`;
      actH=`<span class="text-xs text-gray-400 mr-2">待导入：</span>`;
      actH+=`<code class="text-xs bg-gray-900 px-2 py-1 rounded border border-gray-600 select-all cursor-pointer" title="点击复制" onclick="navigator.clipboard.writeText(this.textContent)">${esc(applyCmd)}</code>`;
    }
    const typeTag=d.opportunity_type?`<span class="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400 ml-2">${esc(d.opportunity_type)}</span>`:'';
    return `<div class="bg-gray-750 rounded-lg border border-gray-700 p-4 mb-3 flex items-start gap-4 fade-in" style="background:#252a3a">
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <span class="font-semibold text-gray-200">${esc(d.title)}</span>
          <span class="px-1.5 py-0.5 rounded text-xs ${pCls}">${pTxt}</span>
          <span class="px-1.5 py-0.5 rounded text-xs ${sCls}">${sTxt}</span>
          ${typeTag}
        </div>
        <div class="text-xs text-gray-500">${d.draft_id} · ${d.created_at||''}</div>
      </div>
      <div class="flex items-center gap-2 flex-shrink-0">
        <button onclick="openDraft('${d.filename}')" class="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-gray-200 text-xs">📖 阅读</button>
        ${actH}
      </div>
    </div>`;
  }).join('');
}
async function openDraft(filename){
  $('pn-t').textContent='📖 叙事草案 · '+filename;
  $('pn-b').innerHTML='<div class="text-gray-400 text-center py-8">加载中...</div>';
  $('po').classList.remove('hidden');$('pn').classList.remove('hidden');
  try{
    const d=await api('/api/drafts/'+encodeURIComponent(filename.replace('.md','')));
    if(d.error)throw new Error(d.error);
    // Render markdown content as preformatted (strip frontmatter)
    let body=d.content||'';
    if(body.startsWith('---')){const end=body.indexOf('---',3);if(end!==-1)body=body.substring(end+3);}
    body=body.trim();
    // Simple markdown→HTML for display
    let html='<div class="prose prose-invert max-w-none">';
    // Render headers
    body=body.replace(/^### (.+)$/gm,'<h3 class="text-base font-semibold text-amber-200 mt-4 mb-1">$1</h3>');
    body=body.replace(/^## (.+)$/gm,'<h2 class="text-lg font-bold text-amber-300 mt-5 mb-2 pb-1 border-b border-gray-700">$1</h2>');
    body=body.replace(/^# (.+)$/gm,'<h1 class="text-xl font-bold text-cyan-300 mb-3">$1</h1>');
    // Render blockquotes
    body=body.replace(/^> (.+)$/gm,'<blockquote class="border-l-2 border-cyan-600 pl-3 my-2 text-gray-300 text-sm">$1</blockquote>');
    // Render tables
    body=body.replace(/^\|(.+)\|$/gm,(m)=>'<tr>'+m.split('|').slice(1,-1).map(c=>'<td class="px-2 py-1 border border-gray-700 text-sm">'+c.trim()+'</td>').join('')+'</tr>');
    body=body.replace(/(<tr>.*<\/tr>\n?)+/g,(m)=>'<table class="w-full text-sm my-2 border-collapse">'+m+'</table>');
    // Render remaining as paragraphs
    const lines=body.split('\n');
    let out='';
    for(const line of lines){
      if(line.startsWith('<h')||line.startsWith('<blockquote')||line.startsWith('<table')||line.startsWith('<tr')||line.trim()===''){out+=line+'\n';continue;}
      out+=`<p class="text-sm text-gray-300 my-1">${line}</p>\n`;
    }
    html+=out+'</div>';
    // Action buttons at bottom
    const fm=d.frontmatter||{};
    if(fm.status==='pending'){
      html+=`<div class="mt-4 pt-3 border-t border-gray-700 flex gap-2">`;
      html+=`<button onclick="doDraftAction('${d.filename}','approve',this);closeP();setTimeout(loadDrafts,500)" class="px-4 py-1.5 bg-green-800 hover:bg-green-700 rounded text-white text-sm font-medium">✓ 批准</button>`;
      html+=`<button onclick="doDraftAction('${d.filename}','reject',this);closeP();setTimeout(loadDrafts,500)" class="px-4 py-1.5 bg-red-800 hover:bg-red-700 rounded text-white text-sm font-medium">✗ 驳回</button>`;
      html+=`</div>`;
    } else if(fm.status==='approved'){
      const applyCmd=`/narrative-grower apply --draft ${d.path.replace(/\\\\/g,'/')}`;
      html+=`<div class="mt-4 pt-3 border-t border-gray-700">`;
      html+=`<div class="text-xs text-gray-400 mb-2">导入命令（在 Claude Code 中执行）：</div>`;
      html+=`<code class="block text-xs bg-gray-900 px-3 py-2 rounded border border-gray-600 select-all cursor-pointer" onclick="navigator.clipboard.writeText(this.textContent)">${esc(applyCmd)}</code>`;
      html+=`</div>`;
    }
    $('pn-b').innerHTML=html;
  }catch(e){$('pn-b').innerHTML='<div class="text-red-400 py-8 text-center">'+esc(e.message)+'</div>';}
}
async function doDraftAction(filename,action,btn){
  if(btn){btn.disabled=true;btn.textContent='处理中...';}
  try{
    const r=await api('/api/drafts/'+encodeURIComponent(filename.replace('.md',''))+'/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    if(r.error)throw new Error(r.error);
    if(btn){btn.textContent=action==='approve'?'✓ 已批准':'✗ 已驳回';btn.className='px-3 py-1 rounded text-white text-xs '+(action==='approve'?'bg-green-700':'bg-red-700');}
    setTimeout(()=>{loadDrafts();load();},500);
  }catch(e){if(btn){btn.textContent='✗ 失败';btn.className='px-3 py-1 rounded text-white text-xs bg-red-700';}}
}

/* ═══ Helpers ═══ */
function $(id){return document.getElementById(id);}
function enc(s){return encodeURIComponent(s||'');}
function esc(s){if(!s)return '';const d=document.createElement('span');d.textContent=String(s);return d.innerHTML;}
function escA(s){if(!s)return '';return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

load();
</script>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="角色美术管理仪表盘")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--uri", default=NEO4J_URI)
    ap.add_argument("--user", default=NEO4J_USER)
    ap.add_argument("--password", default=NEO4J_PASSWORD)
    args = ap.parse_args()

    global client
    try:
        client = Neo4jClient(uri=args.uri, user=args.user, password=args.password)
        client.connect()
    except Exception as e:
        print(f"❌ Neo4j 连接失败: {e}"); sys.exit(1)

    server = HTTPServer(("localhost", args.port), DashboardHandler)
    url = f"http://localhost:{args.port}"
    print(f"✅ 仪表盘已启动: {url}")
    print(f"   项目: {PROJECT_ROOT}")
    import webbrowser; webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 已停止")
    finally:
        client.close(); server.server_close()

if __name__ == "__main__":
    main()
