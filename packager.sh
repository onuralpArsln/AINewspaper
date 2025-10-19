#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
export PYTHONDONTWRITEBYTECODE=1

APP_NAME="ainp_backend"
ENTRYPOINT="backend/backendServer.py"

# PyInstaller options
PYI_OPTS=(
  --onedir
  --name "$APP_NAME"
  --paths backend
  # Hidden imports that FastAPI/uvicorn stacks often need
  --hidden-import h11
  --hidden-import anyio
  --hidden-import starlette
  --hidden-import pydantic
  # lxml and Pillow plugin collection safety
  --hidden-import lxml.etree
  --hidden-import lxml._elementpath
  --collect-all PIL
  # Google GenAI and SSL certs
  --collect-all google
  --collect-data certifi
  # Resource files used at runtime
  --add-data "backend/rsslist.txt:."
  --add-data "backend/editor_prompt.txt:."
  --add-data "backend/writer_prompt.txt:."
  --add-data "backend/rewriter_prompt.txt:."
)

main() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$script_dir"

  echo "[+] Checking Python..."
  command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; exit 1; }

  echo "[+] Optionally installing build prerequisites (if root and apt available)..."
  if command -v apt-get >/dev/null 2>&1 && [ "${CI:-0}" != "1" ]; then
    if [ "${SKIP_APT:-0}" != "1" ] && [ "$(id -u)" = "0" ]; then
      apt-get update -y
      apt-get install -y python3-venv python3-dev build-essential
    else
      echo "[*] Skipping apt-get (not root or SKIP_APT=1)."
    fi
  fi

  echo "[+] Creating venv in .packager/venv ..."
  mkdir -p .packager
  if [ ! -d .packager/venv ]; then
    python3 -m venv .packager/venv
  fi
  source .packager/venv/bin/activate
  python -m pip install --upgrade pip wheel setuptools
  python -m pip install pyinstaller
  python -m pip install -r backend/requirements.txt

  echo "[+] Cleaning previous build artifacts..."
  rm -rf build dist

  echo "[+] Running PyInstaller..."
  pyinstaller "${PYI_OPTS[@]}" "$ENTRYPOINT"

  echo "[+] Preparing release folder..."
  local rel_root="release/${APP_NAME}-linux-x86_64"
  rm -rf "$rel_root"
  mkdir -p "$rel_root/${APP_NAME}"

  echo "[+] Copying onedir app into release..."
  # Copy contents of dist/$APP_NAME into release/$APP_NAME
  cp -a "dist/${APP_NAME}/." "$rel_root/${APP_NAME}/"

  echo "[+] Copying optional runtime files (if present)..."
  for f in our_articles.db rss_articles.db workflow_log.txt; do
    if [ -f "backend/$f" ]; then
      cp -n "backend/$f" "$rel_root/${APP_NAME}/$f"
    fi
  done
  if [ -f "backend/.env" ]; then
    cp -n "backend/.env" "$rel_root/${APP_NAME}/.env"
  fi

  echo "[+] Ensuring executable bit on launcher..."
  if [ -f "$rel_root/${APP_NAME}/${APP_NAME}" ]; then
    chmod +x "$rel_root/${APP_NAME}/${APP_NAME}"
  fi

  echo "[+] Writing run guide..."
  cat > "$rel_root/README_RUN.md" << 'EOF'
Run on target (Debian x86_64):

1) Copy this folder to the target machine.
2) Ensure executable bit: chmod +x ./ainp_backend/ainp_backend
3) If you use Gemini, place a .env with GEMINI_FREE_API into ./ainp_backend/
4) Start from inside the folder: ./ainp_backend/ainp_backend
   - Server listens on 0.0.0.0:8000 by default
5) Data files (SQLite/log) live next to the binary in ./ainp_backend/
EOF

  echo "[+] Release ready at: $rel_root"
}

main "$@"


