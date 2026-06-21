"""保存反馈逻辑：保存后必须产生 toast 反馈（回归「success+rerun 被吞→无反馈」）。"""
from types import SimpleNamespace

from ui import page_node_editor


def _node(label):
    return SimpleNamespace(label=label)


def test_save_plain_no_downstream():
    """无回退、无级联：仍要弹一条「已保存」即时反馈。"""
    toasts = page_node_editor._save_toasts(revert=None, affected=[])
    assert len(toasts) == 1
    msg, icon = toasts[0]
    assert "已保存" in msg
    assert icon == "✅"


def test_save_with_cascade_lists_downstream():
    """有级联：反馈包含下游数量与名称。"""
    affected = [_node("立绘"), _node("表情")]
    toasts = page_node_editor._save_toasts(revert=None, affected=affected)
    assert len(toasts) == 1
    msg, icon = toasts[0]
    assert "2" in msg and "立绘" in msg and "表情" in msg
    assert icon == "✅"


def test_save_with_revert_adds_info_toast():
    """原已批准被回退：额外弹一条 info 提示回退，且仍保留「已保存」。"""
    toasts = page_node_editor._save_toasts(revert=0, affected=[])
    assert len(toasts) == 2
    assert toasts[0][1] == "ℹ️" and "回退" in toasts[0][0]
    assert toasts[1][1] == "✅" and "已保存" in toasts[1][0]
