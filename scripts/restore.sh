#!/usr/bin/env bash
# Восстановление БД из резервной копии.
#   ./scripts/restore.sh                       — последняя копия в ТЕСТОВУЮ базу library_restore_test
#   ./scripts/restore.sh <файл>                — указанная копия в тестовую базу
#   ./scripts/restore.sh <файл> --production   — восстановление в рабочую базу (с подтверждением)
source "$(dirname "$0")/common.sh"
FILE="${1:-$(ls -1t backups/library_*.sql.gz 2>/dev/null | head -1)}"
MODE="${2:-test}"
[[ -z "$FILE" || ! -f "$FILE" ]] && { echo "Резервная копия не найдена"; exit 1; }

if [[ -f "$FILE.sha256" ]]; then
  sha256sum -c "$FILE.sha256" >/dev/null && log "Контрольная сумма совпадает" \
    || { log "ОШИБКА: контрольная сумма не совпадает"; exit 1; }
fi

if [[ "$MODE" == "--production" ]]; then
  TARGET="$POSTGRES_DB"
  read -rp "Перезаписать рабочую базу '$TARGET' данными из $FILE? [y/N] " ans
  [[ "$ans" == "y" ]] || exit 1
  docker compose stop app
else
  TARGET="library_restore_test"
  docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -q \
    -c "DROP DATABASE IF EXISTS $TARGET;" -c "CREATE DATABASE $TARGET;"
fi

log "Восстановление $FILE -> база '$TARGET'..."
gunzip -c "$FILE" | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$TARGET" -q -v ON_ERROR_STOP=1 >/dev/null

log "Проверка восстановленных данных:"
COUNTS_SQL="SELECT 'books', COUNT(*) FROM books UNION ALL SELECT 'readers', COUNT(*) FROM readers UNION ALL SELECT 'loans', COUNT(*) FROM loans;"
echo "  Восстановленная база ($TARGET):"
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$TARGET" -At -F ' = ' -c "$COUNTS_SQL" | sed 's/^/    /'
if [[ "$TARGET" != "$POSTGRES_DB" ]]; then
  echo "  Рабочая база ($POSTGRES_DB):"
  docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F ' = ' -c "$COUNTS_SQL" | sed 's/^/    /'
  A=$(docker compose exec -T db psql -U "$POSTGRES_USER" -d "$TARGET" -At -c "$COUNTS_SQL" | md5sum)
  B=$(docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "$COUNTS_SQL" | md5sum)
  [[ "$A" == "$B" ]] && log "OK: количество записей совпадает" \
    || log "ВНИМАНИЕ: данные отличаются (изменения после создания копии)"
else
  docker compose start app
fi
