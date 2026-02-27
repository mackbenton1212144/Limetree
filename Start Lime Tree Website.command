#!/bin/zsh
set -euo pipefail

PROJECT_DIR="/Users/mackbenton/Weque Boats/Lime Tree"
PORT="8502"
URL="http://localhost:${PORT}"
LOG_FILE="${PROJECT_DIR}/streamlit.log"

cd "$PROJECT_DIR"

# Stop old app instance if one is still running.
pkill -f "streamlit run app.py --server.port ${PORT}" 2>/dev/null || true

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python3 -m pip install -U pip >/dev/null 2>&1
python3 -m pip install -r requirements.txt >/dev/null 2>&1

# Start server in background and capture logs for troubleshooting.
nohup streamlit run app.py --server.port "${PORT}" > "${LOG_FILE}" 2>&1 &

# Give server time to boot, then open browser.
sleep 2
open "${URL}"

echo "Lime Tree website started at ${URL}"
echo "Logs: ${LOG_FILE}"
