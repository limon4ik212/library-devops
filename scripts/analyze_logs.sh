#!/usr/bin/env bash
# Анализ JSON-логов приложения за указанный период (по умолчанию 1 час)
source "$(dirname "$0")/common.sh"
SINCE="${1:-1h}"
TMP="$(mktemp)"
docker compose logs app --no-log-prefix --since "$SINCE" 2>/dev/null | grep '^{' > "$TMP" || true
TOTAL=$(wc -l < "$TMP")
echo "===== Анализ логов приложения за $SINCE (записей: $TOTAL) ====="
echo "--- По уровням ---"
grep -o '"level": "[A-Z]*"' "$TMP" | sort | uniq -c | sort -rn || true
echo "--- По HTTP-статусам ---"
grep -o '"status": [0-9]*' "$TMP" | sort | uniq -c | sort -rn || true
echo "--- Самые частые запросы ---"
grep -o '"method": "[A-Z]*", "path": "[^"]*"' "$TMP" | sort | uniq -c | sort -rn | head -10 || true
echo "--- Медленные запросы (> 500 мс) ---"
grep -E '"duration_ms": ([5-9][0-9]{2}|[0-9]{4,})' "$TMP" | tail -10 || echo "нет"
echo "--- Последние ошибки (ERROR/WARNING) ---"
grep -E '"level": "(ERROR|WARNING)"' "$TMP" | tail -10 || echo "нет"
rm -f "$TMP"
