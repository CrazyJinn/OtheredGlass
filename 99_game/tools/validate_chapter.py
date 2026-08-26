"""剧本章节 Schema 校验。支持 JSON / YAML / 台词 JSONL 输入（按后缀分流加载）。本环境（bash + python）可立即运行。"""
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    sys.stderr.write("缺少依赖：pip install -r tools/requirements.txt\n")
    raise

try:
    import yaml
except ImportError:
    sys.stderr.write("缺少依赖：pip install -r tools/requirements.txt (PyYAML)\n")
    raise

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "scripts"  # 项目根/.claude/scripts
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jsonl_script  # noqa: E402


def _load_doc(path: str):
    """按后缀分流加载文档：.json→json.load，.yaml/.yml→yaml.safe_load。其余后缀报错。

    （.jsonl 不走本函数——行级校验 + 投影 + schema 由 validate_chapter 整体分流处理。）
    """
    suffix = Path(path).suffix.lower()
    with open(path, "r", encoding="utf-8") as f:
        if suffix in (".yaml", ".yml"):
            return yaml.safe_load(f)
        if suffix == ".json":
            return json.load(f)
        raise ValueError(f"不支持的文件格式: {suffix}（仅支持 .json/.yaml/.yml/.jsonl）")


def validate_chapter(path: str, schema_path: str) -> tuple[bool, list[str]]:
    """返回 (是否通过, 错误消息列表)。"""
    # 台词 JSONL：行级规则（8 行类型/行 id 水位/say 四字段）+ 投影后走章 JSON schema，一步到位
    if Path(path).suffix.lower() == ".jsonl":
        return jsonl_script.validate(path, schema_path)

    errors: list[str] = []
    try:
        doc = _load_doc(path)
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as e:
        return False, [f"读取/解析失败: {e}"]

    validator = jsonschema.Draft202012Validator(schema)
    # line 用 oneOf 表达；jsonschema 默认只回一个 "not valid under any of the
    # given schemas" 父错误，作者看不出缺哪个字段。err.context 里才是真正的原因
    # （如 "'op' is a required property"），这里展开+去重后呈现给作者。
    seen: set[tuple[str, str]] = set()

    def _add(loc: str, msg: str) -> None:
        key = (loc, msg)
        if key not in seen:
            seen.add(key)
            errors.append(f"{loc}: {msg}")

    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        _add(loc, err.message)
        for sub in err.context or []:
            sub_loc = "/".join(str(p) for p in sub.absolute_path) or loc
            _add(sub_loc, sub.message)
    return (len(errors) == 0), errors


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("用法: python validate_chapter.py <chapter.json|chapter.yaml|台词.jsonl> <schema.json>\n")
        return 2
    ok, errors = validate_chapter(argv[1], argv[2])
    if ok:
        print(f"OK: {argv[1]} 通过 schema 校验")
        return 0
    print(f"FAIL: {argv[1]}")
    for e in errors:
        print("  - " + e)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
