#!/usr/bin/env bash
# Моделирование отказа: остановка БД и наблюдение за поведением приложения
source "$(dirname "$0")/common.sh"
log "1) Исходное состояние"; curl -s "$APP_URL/health"; echo
log "2) Останавливаем контейнер БД (имитация отказа)"; docker compose stop db
sleep 3
log "3) Health во время отказа (ожидается 503 / degraded):"
curl -s -w '  HTTP %{http_code}\n' "$APP_URL/health"
log "4) Попытка бизнес-операции (ожидается 500 и запись ERROR в логе):"
curl -s -w '  HTTP %{http_code}\n' "$APP_URL/api/books"
log "5) Записи об ошибке в логах приложения:"
docker compose logs app --no-log-prefix --since 30s | grep -E '"level": "ERROR"' | tail -3 || true
log "6) Восстанавливаем БД"; docker compose start db
for i in $(seq 1 20); do
  curl -fs "$APP_URL/health" >/dev/null && break; sleep 2
done
log "7) Состояние после восстановления:"; curl -s -w '  HTTP %{http_code}\n' "$APP_URL/health"
log "8) Данные сохранились:"; curl -s "$APP_URL/api/stats"; echo
