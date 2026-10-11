#!/bin/sh
set -e
# Aplica as migrações do banco antes de subir a API
alembic upgrade head
exec uvicorn revalli.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
