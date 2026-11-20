#!/usr/bin/env bash
# Запуск инфраструктуры. Флаг --monitoring добавляет Prometheus и Grafana.
source "$(dirname "$0")/common.sh"
PROFILE=()
[[ "${1:-}" == "--monitoring" ]] && PROFILE=(--profile monitoring)
log "Сборка и запуск контейнеров..."
docker compose "${PROFILE[@]}" up -d --build
log "Ожидание готовности приложения..."
for i in $(seq 1 30); do
  if curl -fs "$APP_URL/health" >/dev/null; then
    log "Приложение готово: $APP_URL"
    docker compose ps
    exit 0
  fi
  sleep 2
done
log "ОШИБКА: приложение не ответило за 60 секунд"
docker compose logs --tail=50 app
exit 1
