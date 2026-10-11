#!/bin/sh
# Faz um dump do banco a cada 24 h e apaga os dumps mais antigos que BACKUP_KEEP_DAYS.
# Também espelha os PDFs (em /backups/files) e a chave que cifra as chaves de API.
set -eu
while true; do
  file="/backups/revalli-$(date -u +%Y%m%d-%H%M%S).dump"
  echo "Gerando $file"
  pg_dump --format=custom --file="$file.tmp" && mv "$file.tmp" "$file"
  find /backups -name 'revalli-*.dump' -mtime +"${BACKUP_KEEP_DAYS}" -delete
  # Os PDFs são guardados pelo hash do conteúdo: copiar só os novos basta
  if [ -d /data/files ]; then
    mkdir -p /backups/files
    cp -a -u /data/files/. /backups/files/
  fi
  if [ -f /data/secret.key ]; then
    cp -a /data/secret.key /backups/secret.key
  fi
  sleep 86400
done
