"""sync 级联：沿 sync=true 出边 BFS，重置下游 status=0。"""
from dataclasses import dataclass


@dataclass
class CascadedNode:
    id: str
    label: str
    level: int


def cascade_reset(changed_id, repo):
    """BFS 重置 changed_id 的 sync=true 可达下游。源自身不改。"""
    queue = [(changed_id, 0)]
    visited = {changed_id}
    result = []
    while queue:
        cur, level = queue.pop(0)
        for d in repo.get_sync_downstream(cur):
            did = d["id"]
            if did not in visited:
                visited.add(did)
                result.append(CascadedNode(id=did, label=d.get("label", ""), level=level + 1))
                queue.append((did, level + 1))
    if result:
        repo.set_status_batch([n.id for n in result], -1)
    return result
