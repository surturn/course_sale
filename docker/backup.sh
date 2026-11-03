#!/bin/bash
# Nightly backup of everything the storefront cannot rebuild: the database and the storage volume
# (uploaded PDFs and cover images). Watermarked copies are skipped because they regenerate on demand.
# Runs forever inside the backup container. Each file is written as .partial and renamed only when it
# finished cleanly, so a crash never leaves something that looks like a backup and is not.
set -u -o pipefail

KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"

write() {  # write <final-path> <command...>  (command writes to stdout)
  local out="$1"; shift
  if "$@" > "${out}.partial"; then
    mv "${out}.partial" "$out"
    echo "backup written: $(basename "$out") ($(du -h "$out" | cut -f1))"
  else
    rm -f "${out}.partial"
    echo "backup FAILED: $(basename "$out")" >&2
  fi
}

while true; do
  stamp="$(date -u +%Y%m%d-%H%M%S)"
  write "/backups/db-${stamp}.sql.gz" bash -c \
    'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner | gzip'
  write "/backups/storage-${stamp}.tar.gz" tar czf - -C /storage --exclude=./watermarked .
  find /backups \( -name 'db-*.sql.gz' -o -name 'storage-*.tar.gz' \) -mtime "+${KEEP_DAYS}" -delete
  sleep "$INTERVAL"
done
