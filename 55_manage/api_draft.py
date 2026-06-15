#!/usr/bin/env python3
"""
叙事草案 API 处理函数
"""

import db


def get_all(handler):
    """GET /api/drafts"""
    drafts = db.get_all_drafts()
    handler._json({"drafts": drafts})


def get_one(handler, draft_id):
    """GET /api/drafts/<id>"""
    result = db.get_draft_content(draft_id)
    if result:
        handler._json(result)
    else:
        handler._json({"error": "草案不存在"}, 404)


def approve(handler, draft_id):
    """POST /api/drafts/<id>/approve"""
    result = db.approve_draft(draft_id)
    if result:
        handler._json({"success": True, **result})
    else:
        handler._json({"error": "草案不存在"}, 404)


def reject(handler, draft_id):
    """POST /api/drafts/<id>/reject"""
    result = db.reject_draft(draft_id)
    if result:
        handler._json({"success": True, **result})
    else:
        handler._json({"error": "草案不存在"}, 404)
