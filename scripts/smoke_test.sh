#!/usr/bin/env bash
# Проверка развернутой системы (используется в CI/CD после docker compose up)
source "$(dirname "$0")/common.sh"
fail() { log "FAIL: $*"; docker compose logs --tail=50 app; exit 1; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
[[ $(code "$APP_URL/health") == 200 ]] || fail "health"
ID=$(curl -s -X POST "$APP_URL/api/books" -H 'Content-Type: application/json' \
  -d '{"title":"Smoke Test Book","author":"CI","copies":1}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])') \
  || fail "создание книги"
curl -s "$APP_URL/api/books?q=smoke" | grep -q "Smoke Test Book" || fail "поиск книги"
curl -s "$APP_URL/metrics" | grep -q "library_db_up 1" || fail "метрики"
[[ $(code -X DELETE "$APP_URL/api/books/$ID") == 204 ]] || fail "удаление"
log "Smoke-тест пройден"
