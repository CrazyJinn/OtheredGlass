#!/usr/bin/env python3
"""
角色美术 API 处理函数
"""

import db


def get_status(handler):
    """GET /api/status"""
    data = db.get_art_full_status()
    handler._json(data)


def get_node(handler, node_id):
    """GET /api/node/<id>"""
    detail = db.get_node_detail(node_id)
    if detail:
        handler._json(detail)
    else:
        handler._json({"error": "节点不存在"}, 404)


def get_cascade(handler, node_id):
    """GET /api/node/<id>/cascade"""
    result = db.cascade_preview(node_id)
    handler._json(result)


def approve_node(handler):
    """POST /api/approve/node"""
    body = handler._read_json()
    ok = db.approve_node(body["node_id"])
    handler._json({"success": ok})


def reject_node(handler):
    """POST /api/reject/node"""
    body = handler._read_json()
    ok = db.reject_node(body["node_id"])
    handler._json({"success": ok})


def approve_sync(handler):
    """POST /api/approve/sync"""
    body = handler._read_json()
    ok = db.approve_sync(body["from_id"], body["to_id"], body["edge_type"])
    handler._json({"success": ok})


def update_node(handler, node_id):
    """PUT /api/node/<id>"""
    body = handler._read_json()
    props = body.get("props", {})
    result = db.update_node(node_id, props)
    handler._json({"success": True, **result})
