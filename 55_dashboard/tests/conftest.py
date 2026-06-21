"""测试基础设施：内存 MockRepo + 样例 Schema markdown。"""
from dataclasses import dataclass, field


class MockRepo:
    """内存图，模拟 graph_repo 的接口，供 core 单测使用。"""

    def __init__(self):
        self.nodes = {}          # id -> {"label", "status", "props"}
        self.sync_edges = []     # [(from_id, to_id)] 仅 sync=true
        self.status_calls = []   # 记录 set_status_batch 调用 [(ids, status)]
        self.updates = []        # 记录 update_node 调用

    def add_node(self, node_id, label, status=0, props=None):
        self.nodes[node_id] = {"label": label, "status": status, "props": props or {}}

    def add_sync_edge(self, from_id, to_id):
        self.sync_edges.append((from_id, to_id))

    def get_sync_downstream(self, node_id):
        return [dict(id=to, **self.nodes[to])
                for (f, to) in self.sync_edges if f == node_id and to in self.nodes]

    def set_status_batch(self, ids, status):
        self.status_calls.append((list(ids), status))
        for i in ids:
            if i in self.nodes:
                self.nodes[i]["status"] = status

    def set_status(self, node_id, status):
        self.set_status_batch([node_id], status)

    def update_node(self, node_id, props):
        self.updates.append((node_id, dict(props)))
        if node_id in self.nodes:
            self.nodes[node_id]["props"].update(props)

    def get_node(self, node_id):
        return dict(id=node_id, **self.nodes.get(node_id, {"label": "", "status": 0, "props": {}}))


# 样例 Schema markdown（模拟 00_init/Schema/叙事基础.md 的节点表格格式）
SAMPLE_MD = """# 01 叙事基础

### 角色（Character）

最小粒度：每个有名字的真实人物。

| 字段 | 中文 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| id | 编号 | string | 是 | snowflake Base62 |
| name | 姓名 | string | 是 | 陆择 |
| gender | 性别 | enum | 否 | 男 |
| birth_year | 出生年份 | int | 否 | 2003 |

### 事件（Event）

| 字段 | 中文 | 类型 | 必填 | 示例 |
|------|------|------|------|------|
| id | 编号 | string | 是 | x |
| title | 标题 | string | 是 | 加入战队 |
"""
