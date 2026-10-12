#!/usr/bin/env bash
# Remove o auxiliar do Ollama: serviço de usuário, arquivos e regra de permissão.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
env_file="$here/../.env"

systemctl --user disable --now revalli-ollama-helper.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/revalli-ollama-helper.service"
rm -f "$HOME/.config/revalli/ollama_helper.py" "$HOME/.config/revalli/ollama-helper.env"
systemctl --user daemon-reload
sudo rm -f /etc/polkit-1/rules.d/50-revalli-ollama.rules

if [ -f "$env_file" ]; then
  { grep -v -E '^(OLLAMA_HELPER_URL|OLLAMA_HELPER_TOKEN)=' "$env_file" || true; } > "$env_file.tmp"
  mv "$env_file.tmp" "$env_file"
fi
echo "Removido. Recrie a API e o worker para o botão sumir da interface."
