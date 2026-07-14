"""剧本章节 JSON Schema 校验。本环境（bash + python）可立即运行。"""
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    sys.stderr.write("缺少依赖：pip install -r tools/requirements.txt\n")
    raise


def validate_chapter(path: str, schema_path: str) -> tuple[bool, list[str]]:
    """返回 (是否通过, 错误消息列表)。"""
    errors: list[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
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
        sys.stderr.write("用法: python validate_chapter.py <chapter.json> <schema.json>\n")
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
