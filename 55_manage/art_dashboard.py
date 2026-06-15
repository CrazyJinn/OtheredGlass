#!/usr/bin/env python3
"""
他者之镜 · 管理面板 启动入口
Usage: python art_dashboard.py [--port 8765]
"""

import argparse
import server

DEFAULT_PORT = 8765


def main():
    ap = argparse.ArgumentParser(description="他者之镜 · 管理面板")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--uri", default="bolt://localhost:7687")
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", default="12345678")
    args = ap.parse_args()

    server.run_server(
        port=args.port,
        neo4j_uri=args.uri,
        neo4j_user=args.user,
        neo4j_password=args.password,
    )


if __name__ == "__main__":
    main()
