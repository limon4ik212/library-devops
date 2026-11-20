#!/usr/bin/env bash
# Остановка инфраструктуры. Данные в volume сохраняются.
# Флаг --purge удаляет и тома (ВСЕ ДАННЫЕ БУДУТ ПОТЕРЯНЫ).
source "$(dirname "$0")/common.sh"
if [[ "${1:-}" == "--purge" ]]; then
  read -rp "Удалить контейнеры И ДАННЫЕ? [y/N] " ans
  [[ "$ans" == "y" ]] && docker compose --profile monitoring down -v && log "Удалено вместе с томами"
else
  docker compose --profile monitoring down
  log "Контейнеры остановлены, данные сохранены в томе db_data"
fi
