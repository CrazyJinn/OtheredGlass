"""
执行 Cypher 查询脚本
支持从文件、命令行参数或 stdin 执行 Cypher，输出 JSON 结果。
支持多语句事务模式（--multi）。
"""

import os
import sys
import json
import argparse
from urllib.parse import urlparse, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from neo4j_client import Neo4jClient


def resolve_file_path(path):
    """解析文件路径，支持 file:/// URI 和普通路径"""
    if path.startswith("file:///"):
        # file:///D:/foo/bar.cypher → D:/foo/bar.cypher
        parsed = urlparse(path)
        resolved = unquote(parsed.path)
        # Windows: 去掉开头的 /
        if resolved.startswith("/") and len(resolved) > 2 and resolved[2] == ":":
            resolved = resolved[1:]
        return resolved
    return path


def split_cypher_statements(text):
    """将多语句文本按 ; 分割为独立 Cypher 语句列表。

    正确处理：
    - 字符串字面量内的 ;（不作为分隔符）
    - 行注释 //：仅当不在字符串字面量内时视为注释，剥离整行；
      字符串内的 //（如 URL）不会被误判。
    """
    statements = []
    current = []
    in_string = False       # 是否在字符串字面量内
    string_char = None      # 当前字符串的引号字符 (' 或 ")
    escape_next = False     # 上一个字符是否为转义符 \

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        # 行注释 //（仅当不在字符串内）：跳过到行尾，不写入 current
        if not in_string and ch == '/' and i + 1 < n and text[i + 1] == '/':
            while i < n and text[i] != '\n':
                i += 1
            continue  # 留下 \n 给主循环处理（保持换行语义）

        if escape_next:
            current.append(ch)
            escape_next = False
            i += 1
            continue
        if ch == '\\' and in_string:
            current.append(ch)
            escape_next = True
            i += 1
            continue
        if in_string:
            current.append(ch)
            if ch == string_char:
                in_string = False
            i += 1
            continue
        # 不在字符串内
        if ch in ("'", '"'):
            current.append(ch)
            in_string = True
            string_char = ch
        elif ch == ';':
            stmt = ''.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(ch)
        i += 1

    # 处理末尾无 ; 的残余
    stmt = ''.join(current).strip()
    if stmt:
        statements.append(stmt)

    return statements


def execute_and_print(client, cypher, output_json=False):
    """执行单条 Cypher 并打印结果"""
    results = client.run(cypher)
    if output_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        if not results:
            print("(无结果)")
            return
        # 打印表格
        keys = list(results[0].keys())
        col_widths = {k: max(len(str(k)), *(len(str(r.get(k, ""))) for r in results)) for k in keys}
        col_widths = {k: min(w, 40) for k, w in col_widths.items()}

        header = " | ".join(k.ljust(col_widths[k]) for k in keys)
        sep = "-+-".join("-" * col_widths[k] for k in keys)
        print(header)
        print(sep)
        for row in results:
            line = " | ".join(str(row.get(k, ""))[:col_widths[k]].ljust(col_widths[k]) for k in keys)
            print(line)
        print(f"\n({len(results)} 行)")


def execute_multi_and_print(client, cypher_text, output_json=False):
    """在单个事务中执行多条 Cypher（按 ; 分割），打印结果"""
    statements = split_cypher_statements(cypher_text)
    if not statements:
        print("(无有效语句)")
        return

    results = client.run_in_transaction(statements)
    if output_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for i, (stmt, res) in enumerate(zip(statements, results), 1):
            # 截断显示语句
            preview = stmt.replace("\n", " ")[:80]
            print(f"\n--- 语句 {i}: {preview}{'...' if len(stmt) > 80 else ''} ---")
            if not res:
                print("(无结果)")
            else:
                keys = list(res[0].keys())
                col_widths = {k: max(len(str(k)), *(len(str(r.get(k, ""))) for r in res)) for k in keys}
                col_widths = {k: min(w, 40) for k, w in col_widths.items()}
                header = " | ".join(k.ljust(col_widths[k]) for k in keys)
                sep = "-+-".join("-" * col_widths[k] for k in keys)
                print(header)
                print(sep)
                for row in res:
                    line = " | ".join(str(row.get(k, ""))[:col_widths[k]].ljust(col_widths[k]) for k in keys)
                    print(line)
                print(f"({len(res)} 行)")


def execute_raw_and_print(client, cypher):
    """执行单条 Cypher，仅当结果为单行单列标量时输出裸值到 stdout（管道消费专用）"""
    results = client.run(cypher)
    if len(results) != 1:
        print(f"错误：--raw 模式要求结果恰好 1 行，实际 {len(results)} 行", file=sys.stderr)
        sys.exit(1)
    row = results[0]
    if len(row) != 1:
        print(f"错误：--raw 模式要求结果恰好 1 列，实际 {len(row)} 列: {list(row.keys())}", file=sys.stderr)
        sys.exit(1)
    value = next(iter(row.values()))
    if value is None:
        print("错误：--raw 模式结果为 null（目标字段可能未设置）", file=sys.stderr)
        sys.exit(1)
    if isinstance(value, (list, dict)):
        print(f"错误：--raw 模式要求标量值，实际复合类型 {type(value).__name__}", file=sys.stderr)
        sys.exit(1)
    sys.stdout.write(str(value))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="执行 Cypher 查询")
    parser.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", ""))
    parser.add_argument("-c", "--cypher", help="要执行的 Cypher 语句（注意：$param 会被 Shell 解析，推荐用 -f 或 --stdin）")
    parser.add_argument("-f", "--file", help="要执行的 .cypher 文件路径（支持 file:/// URI）")
    parser.add_argument("--stdin", action="store_true", help="从标准输入读取 Cypher")
    parser.add_argument("--multi", action="store_true", help="多语句事务模式：按 ; 分割，在单个事务中顺序执行")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    parser.add_argument("--raw", action="store_true", help="裸标量输出：仅当结果为单行单列标量时，输出裸值到 stdout（管道消费专用，不加 JSON/表格包装）")
    args = parser.parse_args()

    if args.raw and (args.multi or args.json):
        parser.error("--raw 与 --multi/--json 互斥")

    # 收集 Cypher 输入
    cypher = None
    if args.stdin:
        cypher = sys.stdin.read()
    elif args.file:
        file_path = resolve_file_path(args.file)
        with open(file_path, "r", encoding="utf-8") as f:
            cypher = f.read()
    elif args.cypher:
        cypher = args.cypher

    if not cypher:
        parser.error("请提供 -c Cypher 语句、-f .cypher 文件或 --stdin")

    with Neo4jClient(args.uri, args.user, args.password) as client:
        if args.raw:
            execute_raw_and_print(client, cypher)
        elif args.multi:
            execute_multi_and_print(client, cypher, args.json)
        else:
            execute_and_print(client, cypher, args.json)
