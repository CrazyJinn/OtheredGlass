#!/usr/bin/env bash
# 快速启动 55_dashboard（Streamlit 后台）
# 用法：bash run.sh   或在项目根  bash 55_dashboard/run.sh
set -e

# 切到脚本所在目录，保证相对路径（config/ 等）可用
cd "$(dirname "$0")"

# 优先用虚拟环境，没有就用系统 python
if [ -d ".venv" ]; then
  # Windows Git Bash 下 venv 的解释器在 Scripts/
  if [ -x ".venv/Scripts/python.exe" ]; then
    PY=".venv/Scripts/python.exe"
  else
    PY=".venv/bin/python"
  fi
else
  PY="python"
fi

# 依赖自检：缺 streamlit 就装一次
if ! "$PY" -c "import streamlit" >/dev/null 2>&1; then
  echo "→ 未检测到 streamlit，安装依赖 requirements.txt ..."
  "$PY" -m pip install -r requirements.txt
fi

# .env 自检（仅提示，settings.py 也会从项目根 settings.json 读 neo4j 凭证）
if [ ! -f ".env" ]; then
  echo "⚠ 未找到 .env（参考 .env.example 配置 Neo4j 凭证；也可放在项目根 settings.json）"
fi

echo "→ 启动 Streamlit：http://localhost:8501"
exec "$PY" -m streamlit run app.py --server.port 8501 --server.headless false
