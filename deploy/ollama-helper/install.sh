#!/usr/bin/env bash
# Instala o auxiliar que deixa o ReValli ligar e desligar o Ollama deste computador.
# Rode no SEU terminal (a senha do sudo é pedida uma vez, para a regra de permissão):
#   bash deploy/ollama-helper/install.sh
# Para desfazer: bash deploy/ollama-helper/uninstall.sh
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
env_file="$here/../.env"
conf="$HOME/.config/revalli"
unit_dir="$HOME/.config/systemd/user"
port="${OLLAMA_HELPER_PORT:-11435}"

mkdir -p "$conf" "$unit_dir"
install -m 0755 "$here/ollama_helper.py" "$conf/ollama_helper.py"

# Token: gerado uma vez e reaproveitado nas reinstalações
if [ ! -s "$conf/ollama-helper.env" ]; then
  (umask 077
   printf 'OLLAMA_HELPER_TOKEN=%s\nOLLAMA_HELPER_PORT=%s\n' \
     "$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')" "$port" > "$conf/ollama-helper.env")
fi
token="$(grep '^OLLAMA_HELPER_TOKEN=' "$conf/ollama-helper.env" | cut -d= -f2-)"

cat > "$unit_dir/revalli-ollama-helper.service" <<UNIT
[Unit]
Description=Auxiliar do ReValli para ligar e desligar o Ollama

[Service]
EnvironmentFile=%h/.config/revalli/ollama-helper.env
ExecStart=/usr/bin/python3 %h/.config/revalli/ollama_helper.py
Restart=on-failure

[Install]
WantedBy=default.target
UNIT

# Permissão: este usuário pode ligar e desligar só o serviço ollama
rule=/etc/polkit-1/rules.d/50-revalli-ollama.rules
sudo tee "$rule" >/dev/null <<RULE
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        action.lookup("unit") == "ollama.service" &&
        (action.lookup("verb") == "start" || action.lookup("verb") == "stop") &&
        subject.user == "$USER") {
        return polkit.Result.YES;
    }
});
RULE

systemctl --user daemon-reload
systemctl --user enable --now revalli-ollama-helper.service

# Entrega a URL e o token ao ReValli
if [ -f "$env_file" ]; then
  { grep -v -E '^(OLLAMA_HELPER_URL|OLLAMA_HELPER_TOKEN)=' "$env_file" || true; } > "$env_file.tmp"
  printf 'OLLAMA_HELPER_URL=http://host.docker.internal:%s\nOLLAMA_HELPER_TOKEN=%s\n' "$port" "$token" >> "$env_file.tmp"
  mv "$env_file.tmp" "$env_file"
  echo "Gravado em $env_file. Para aplicar, recrie a API e o worker:"
  echo "  podman-compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --force-recreate --no-deps api worker"
else
  echo "Defina no deploy/.env: OLLAMA_HELPER_URL=http://host.docker.internal:$port e OLLAMA_HELPER_TOKEN=$token"
fi
