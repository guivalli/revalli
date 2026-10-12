#!/usr/bin/env bash
# Instalação rápida do ReValli em Linux ou macOS (Docker ou Podman).
#
#   ./install.sh                 gera o .env com senhas novas e sobe tudo
#   ./install.sh --port 9000     usa outra porta (padrão 8080)
#   ./install.sh --no-start      só gera o .env
#
# Não mexe em um .env que já existe: para trocar a configuração, edite o arquivo.
set -eu

cd "$(dirname "$0")"

PORT=8080
START=1
while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="${2:?informe o número da porta}"; shift 2 ;;
    --no-start) START=0; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Opção desconhecida: $1" >&2; exit 1 ;;
  esac
done

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  else
    head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

if [ -f .env ]; then
  echo "Mantendo o .env que já existe."
else
  [ -f .env.example ] || { echo "Falta o arquivo .env.example ao lado deste script." >&2; exit 1; }
  cp .env.example .env
  PASSWORD="$(random_secret)"
  sed -i.bak \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PASSWORD}|" \
    -e "s|^HTTP_PORT=.*|HTTP_PORT=${PORT}|" \
    -e "s|^PUBLIC_URL=.*|PUBLIC_URL=http://localhost:${PORT}|" \
    .env
  rm -f .env.bak
  chmod 600 .env
  echo "Criei o .env com uma senha de banco gerada para esta instalação."
fi

PORT_IN_USE="$(sed -n 's/^HTTP_PORT=//p' .env | head -n1)"
PORT_IN_USE="${PORT_IN_USE:-8080}"

[ "$START" -eq 1 ] || { echo "Pronto. Suba com: docker compose up -d"; exit 0; }

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v podman-compose >/dev/null 2>&1; then
  COMPOSE="podman-compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "Não achei Docker Compose nem Podman Compose. Instale um deles e rode de novo." >&2
  exit 1
fi

echo "Subindo o ReValli com: $COMPOSE (a primeira vez baixa ou constrói as imagens)..."
$COMPOSE up -d

URL="http://localhost:${PORT_IN_USE}"
printf 'Esperando a API responder'
for _ in $(seq 1 60); do
  if curl -fsS "${URL}/api/health" >/dev/null 2>&1; then
    printf '\n\nPronto: abra %s\n' "$URL"
    echo "No primeiro acesso, crie a conta de administrador na própria tela."
    exit 0
  fi
  printf '.'
  sleep 3
done
printf '\nA API ainda não respondeu. Veja os registros com: %s logs api\n' "$COMPOSE" >&2
exit 1
