"""VoiceDesign 多候选 manifest 读取 + 采用固化 + 临时文件夹清理。

manifest（char-voice-design 产：voice_clone_runner design-candidates 创建、
audition 子命令回填）位于 `14_声音设计/<char>/candidates/candidates.json`，
含 char / instruct / ref_text / audition_texts 与 candidates[{key, ref, auditions}]
（ref 为 24kHz 候选；试听由 Qwen3 Base Voice Clone 生成）。

采用动作（page_approval 编排，事务顺序）：
promote_candidate 先行（幂等 move）→ repo.update_node 写图
（ref_audio_path + candidates_path=None 删属性）→ cleanup_candidates_dir 殿后
（整删临时文件夹；失败仅留无害残留，发布期拷贝只收 15_声音/ 母带不扫此目录）。

函数均吃 project_root 参数（Path），不 import settings / streamlit——core 层可纯单测。
"""
import json
import shutil
from pathlib import Path


def _resolve(rel_path, project_root: Path) -> Path:
    """项目根相对路径 → 绝对 Path（已是绝对路径则原样）。"""
    p = Path(rel_path)
    return p if p.is_absolute() else project_root / p


def load_manifest(candidates_path, project_root) -> dict | None:
    """读 manifest；路径为空/文件缺失/坏 JSON/无 candidates 键 → None（调用方提示重跑 skill）。"""
    if not candidates_path:
        return None
    p = _resolve(candidates_path, Path(project_root))
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or not data.get("candidates"):
        return None
    return data


def promote_candidate(manifest: dict, key: str, project_root) -> dict:
    """固化选中候选：move 其 24k ref 到角色目录惯例正式路径 <char>_ref.wav（覆盖幂等）。

    返回写图 props：ref_audio_path=项目根相对正式路径、candidates_path=None
    （graph_repo.update_node 的 `SET n += {k: null}` 会删除该属性）。
    """
    cand = next((c for c in manifest["candidates"] if c.get("key") == key), None)
    if cand is None:
        raise KeyError(f"manifest 无候选 {key}")
    src = _resolve(cand["ref"], Path(project_root))
    if not src.exists():
        raise FileNotFoundError(f"候选 ref 不存在：{cand['ref']}")
    char = manifest["char"]
    char_dir = src.parent.parent  # candidates 临时夹的上一级 = 角色目录
    if char_dir.name != char:
        raise ValueError(f"候选目录布局异常：{char_dir} 应为角色目录 {char}")
    dst = char_dir / f"{char}_ref.wav"
    if dst.exists():
        dst.unlink()
    shutil.move(str(src), str(dst))
    try:
        rel = dst.relative_to(Path(project_root)).as_posix()
    except ValueError:
        rel = str(dst)
    return {"ref_audio_path": rel, "candidates_path": None}


def cleanup_candidates_dir(manifest: dict, project_root):
    """采用后整删候选临时文件夹（候选 wav + 试听 + manifest 本身）；失败静默（无害残留）。"""
    if not manifest.get("candidates"):
        return
    d = _resolve(manifest["candidates"][0]["ref"], Path(project_root)).parent
    shutil.rmtree(d, ignore_errors=True)
