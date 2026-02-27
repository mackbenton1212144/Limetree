#!/bin/zsh
set -euo pipefail

PROJECT_DIR="/Users/mackbenton/Weque Boats/Lime Tree"
PORT="8502"

pkill -f "streamlit run app.py --server.port ${PORT}" 2>/dev/null || true
echo "Lime Tree website stopped."

if [ -f "${PROJECT_DIR}/streamlit.log" ]; then
  echo "Recent log output:"
  tail -n 20 "${PROJECT_DIR}/streamlit.log" 2>/dev/null || true
fi
