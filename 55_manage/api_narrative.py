#!/usr/bin/env python3
"""
叙事节点 API 处理函数
"""

from urllib.parse import urlparse, parse_qs

import db


def get_stats(handler):
    """GET /api/narrative/stats"""
    stats = db.get_narrative_stats()
    handler._json(stats)


def get_list(handler):
    """GET /api/narrative/list?label=Character"""
    qs = parse_qs(urlparse(handler.path).query)
    label = qs.get("label", ["Character"])[0]
    nodes = db.get_narrative_list(label)
    handler._json({"label": label, "nodes": nodes})


def get_relations(handler):
    """GET /api/narrative/relations?node_id=xxx"""
    qs = parse_qs(urlparse(handler.path).query)
    node_id = qs.get("node_id", [None])[0]
    if not node_id:
        handler._json({"error": "缺少 node_id 参数"}, 400)
        return
    rels = db.get_narrative_relations(node_id)
    handler._json({"node_id": node_id, "relations": rels})
