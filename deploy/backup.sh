#!/bin/sh
# Faz um dump do banco a cada 24 h e apaga os dumps mais antigos que BACKUP_KEEP_DAYS.
set -eu
while true; do
  file="/backups/revalli-$(date -u +%Y%m%d-%H%M%S).dump"
  echo "Gerando $file"
  pg_dump --format=custom --file="$file.tmp" && mv "$file.tmp" "$file"
  find /backups -name 'revalli-*.dump' -mtime +"${BACKUP_KEEP_DAYS}" -delete
  sleep 86400
done
