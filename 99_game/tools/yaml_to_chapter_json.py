"""把创作区 YAML 章节转换为运行时 JSON。

CLI: yaml_to_chapter_json.py <src.yaml> <dest.json>
纯转换，不做 schema 校验（校验由 validate_chapter.py 负责，保持工具正交）。
退码：0 成功 / 1 解析或 IO 失败 / 2 参数错（与 validate_chapter.py 对齐）。
"""
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("缺少依赖：pip install -r tools/requirements.txt (PyYAML)\n")
    raise


def convert(src: str, dest: str) -> None:
    """读 YAML → 写 JSON（ensure_ascii=False, indent=2, 末尾换行）。"""
    with open(src, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("用法: python yaml_to_chapter_json.py <src.yaml> <dest.json>\n")
        return 2
    try:
        convert(argv[1], argv[2])
    except (OSError, yaml.YAMLError) as e:
        sys.stderr.write(f"转换失败: {e}\n")
        return 1
    print(f"OK: {argv[1]} -> {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
