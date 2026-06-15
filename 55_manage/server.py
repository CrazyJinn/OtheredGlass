#!/usr/bin/env python3
"""
HTTP 服务器 + 路由分发
"""

import os
import json
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

import db
import api_narrative
import api_art
import api_draft

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
STATIC_DIR = os.path.join(SCRIPT_DIR, "static")


class DashboardHandler(BaseHTTPRequestHandler):

    # ── GET ────────────────────────────────────────────────────
    def do_GET(self):
        path = unquote(urlparse(self.path).path)

        # 静态页面
        if path in ("/", "/index.html"):
            self._serve_static_file("index.html", "text/html; charset=utf-8")
            return

        # 静态资源
        if path.startswith("/static/"):
            rel = path[8:]  # strip "/static/"
            fp = os.path.normpath(os.path.join(STATIC_DIR, rel))
            if not fp.startswith(STATIC_DIR) or not os.path.isfile(fp):
                self.send_error(404)
                return
            mime = mimetypes.guess_type(fp)[0] or "application/octet-stream"
            self._serve_file_from_path(fp, mime)
            return

        # 项目文件（图片预览）
        if path.startswith("/file/"):
            self._serve_project_file(path[6:])
            return

        # ── 叙事 API ──
        if path == "/api/narrative/stats":
            api_narrative.get_stats(self)
        elif path == "/api/narrative/list":
            api_narrative.get_list(self)
        elif path == "/api/narrative/relations":
            api_narrative.get_relations(self)

        # ── 角色美术 API ──
        elif path == "/api/taglib":
            self._json(db.get_taglib())
        elif path == "/api/status":
            api_art.get_status(self)
        elif path.startswith("/api/node/"):
            node_id = path.split("/api/node/")[1].rstrip("/")
            if node_id.endswith("/cascade"):
                node_id = node_id.rstrip("/cascade")
                api_art.get_cascade(self, node_id)
            else:
                api_art.get_node(self, node_id)

        # ── 草案 API ──
        elif path == "/api/drafts":
            api_draft.get_all(self)
        elif path.startswith("/api/drafts/"):
            draft_id = path.split("/api/drafts/")[1].rstrip("/")
            api_draft.get_one(self, draft_id)

        else:
            self.send_error(404)

    # ── POST ───────────────────────────────────────────────────
    def do_POST(self):
        path = unquote(urlparse(self.path).path)

        try:
            if path == "/api/approve/node":
                api_art.approve_node(self)
            elif path == "/api/reject/node":
                api_art.reject_node(self)
            elif path == "/api/approve/sync":
                api_art.approve_sync(self)
            elif path.startswith("/api/drafts/") and path.endswith("/approve"):
                draft_id = path.split("/api/drafts/")[1].rstrip("/approve")
                api_draft.approve(self, draft_id)
            elif path.startswith("/api/drafts/") and path.endswith("/reject"):
                draft_id = path.split("/api/drafts/")[1].rstrip("/reject")
                api_draft.reject(self, draft_id)
            else:
                self.send_error(404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    # ── PUT ────────────────────────────────────────────────────
    def do_PUT(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/api/node/"):
            node_id = path.split("/api/node/")[1].rstrip("/")
            try:
                api_art.update_node(self, node_id)
            except Exception as e:
                self._json({"error": str(e)}, 500)
        else:
            self.send_error(404)

    # ── Helpers ────────────────────────────────────────────────
    def _serve_static_file(self, filename, content_type):
        fp = os.path.join(STATIC_DIR, filename)
        if not os.path.isfile(fp):
            self.send_error(404)
            return
        self._serve_file_from_path(fp, content_type)

    def _serve_file_from_path(self, fp, content_type):
        with open(fp, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_project_file(self, rel):
        fp = os.path.normpath(os.path.join(PROJECT_ROOT, rel))
        if not fp.startswith(PROJECT_ROOT) or not os.path.isfile(fp):
            self.send_error(404)
            return
        mime = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        self._serve_file_from_path(fp, mime)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _json(self, d, s=200):
        b = json.dumps(d, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(s)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


def run_server(port=8765, neo4j_uri="bolt://localhost:7687", neo4j_user="neo4j", neo4j_password="12345678"):
    """启动服务器"""
    db.init_client(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)

    server = HTTPServer(("localhost", port), DashboardHandler)
    url = f"http://localhost:{port}"
    print(f"✅ 仪表盘已启动: {url}")
    print(f"   项目: {PROJECT_ROOT}")
    import webbrowser
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 已停止")
    finally:
        db.close_client()
        server.server_close()
