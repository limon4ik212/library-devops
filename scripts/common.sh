#!/usr/bin/env bash
# Общие настройки для всех скриптов
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if [[ ! -f .env ]]; then
  echo "[!] Файл .env не найден. Создайте его: cp .env.example .env" >&2
  exit 1
fi
set -a; source .env; set +a
APP_URL="http://localhost:${APP_PORT:-8000}"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
