"""台词 JSONL 的 dashboard 侧薄封装（bootstrap import .claude/scripts/jsonl_script）。

ui 层不直接操作 sys.path；全部读写经本模块转发到项目唯一实现 jsonl_script
（core 层纯文件操作不连 Neo4j，tests/test_script_jsonl.py 可脱库单测）。
"""
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import jsonl_script  # noqa: E402

# 显式再导出 dashboard 用到的 API（行级审批动作/统计/校验/行 id 水位/投影）
load = jsonl_script.load
save = jsonl_script.save
iter_say_rows = jsonl_script.iter_say_rows
find_row = jsonl_script.find_row
line_state = jsonl_script.line_state
needs_regen = jsonl_script.needs_regen
set_audio = jsonl_script.set_audio
reset_all_audio = jsonl_script.reset_all_audio
audio_counts = jsonl_script.audio_counts
all_approved = jsonl_script.all_approved
validate = jsonl_script.validate
validate_rows = jsonl_script.validate_rows
project = jsonl_script.project
line_seq = jsonl_script.line_seq
next_line_id = jsonl_script.next_line_id
alloc_line_id = jsonl_script.alloc_line_id
