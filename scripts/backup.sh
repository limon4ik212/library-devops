#!/usr/bin/env bash
# Резервное копирование БД PostgreSQL в каталог backups/
# Хранится BACKUP_KEEP последних копий (по умолчанию 7).
source "$(dirname "$0")/common.sh"
BACKUP_DIR="$ROOT_DIR/backups"
KEEP="${BACKUP_KEEP:-7}"
mkdir -p "$BACKUP_DIR"
FILE="$BACKUP_DIR/library_$(date '+%Y%m%d_%H%M%S').sql.gz"

log "Создание резервной копии базы '$POSTGRES_DB'..."
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --clean --if-exists --no-owner | gzip > "$FILE"

# Проверка: файл не пустой и архив целый
if [[ ! -s "$FILE" ]] || ! gzip -t "$FILE"; then
  log "ОШИБКА: резервная копия повреждена"; rm -f "$FILE"; exit 1
fi
sha256sum "$FILE" > "$FILE.sha256"
chmod 600 "$FILE" "$FILE.sha256"
log "Готово: $FILE ($(du -h "$FILE" | cut -f1))"

# Ротация старых копий
ls -1t "$BACKUP_DIR"/library_*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f "$old" "$old.sha256"; log "Удалена старая копия: $(basename "$old")"
done
