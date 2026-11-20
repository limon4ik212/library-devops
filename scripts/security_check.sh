#!/usr/bin/env bash
# Базовая проверка безопасности конфигурации
source "$(dirname "$0")/common.sh"
ok() { echo "  [OK]   $*"; }; bad() { echo "  [WARN] $*"; WARN=1; }
WARN=0
echo "== Секреты =="
git check-ignore -q .env 2>/dev/null && ok ".env исключён из Git" || bad ".env не в .gitignore"
git ls-files 2>/dev/null | grep -qE '(^|/)\.env$' && bad ".env закоммичен!" || ok ".env отсутствует в репозитории"
[[ "${POSTGRES_PASSWORD:-}" == "change_me"* || ${#POSTGRES_PASSWORD} -lt 12 ]] \
  && bad "Слабый/стандартный пароль БД" || ok "Пароль БД задан и достаточно длинный"
grep -rnE "(password|secret)\s*=\s*['\"][^'\"]+" app/ && bad "Пароль в коде" || ok "Пароли в коде не найдены"
echo "== Контейнеры =="
APP_ID=$(docker compose ps -q app)
if [[ -n "$APP_ID" ]]; then
  U=$(docker exec "$APP_ID" id -u); [[ "$U" != "0" ]] && ok "Приложение работает не от root (uid=$U)" || bad "Приложение работает от root"
  [[ $(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "$APP_ID") == true ]] && ok "Файловая система read-only" || bad "ФС доступна на запись"
  docker inspect -f '{{.HostConfig.Privileged}}' "$APP_ID" | grep -q false && ok "Не privileged" || bad "Privileged-контейнер"
  docker inspect -f '{{.HostConfig.CapDrop}}' "$APP_ID" | grep -q ALL && ok "Все capabilities сброшены" || bad "capabilities не ограничены"
else
  bad "Контейнер app не запущен — проверки контейнера пропущены"
fi
docker compose port db 5432 >/dev/null 2>&1 && bad "Порт БД опубликован наружу" || ok "Порт БД не опубликован (сеть backend internal)"
echo "== Резервные копии =="
ls backups/*.sql.gz >/dev/null 2>&1 && { [[ $(stat -c %a "$(ls -1t backups/*.sql.gz | head -1)") == 600 ]] && ok "Права на копии 600" || bad "Копии читаемы всеми"; } || bad "Резервных копий нет"
exit $WARN
