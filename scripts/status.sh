#!/usr/bin/env bash
# Состояние контейнеров, healthcheck и потребление ресурсов
source "$(dirname "$0")/common.sh"
echo "===== docker compose ps ====="
docker compose ps
echo
echo "===== Health приложения ====="
curl -s "$APP_URL/health" || echo "приложение недоступно"
echo; echo
echo "===== Статистика библиотеки ====="
curl -s "$APP_URL/api/stats" || true
echo; echo
echo "===== docker stats (снимок) ====="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}" \
  $(docker compose ps -q)
