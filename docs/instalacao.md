# Instalação e operação

> O ReValli é um projeto vibecodado (escrito com auxílio intensivo de IA). Mantenha backups.

## 1. Requisitos

- Linux com Docker 24+ e o plugin `docker compose`.
- 2 GB de RAM livres para o sistema (sem contar a IA local).
- Opcional: GPU NVIDIA com o [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) para rodar modelos locais.

## 2. Primeira instalação

```bash
git clone https://github.com/guivalli/revalli.git
cd revalli/deploy
cp .env.example .env
openssl rand -base64 32   # use o resultado como POSTGRES_PASSWORD no .env
docker compose up -d --build
```

Abra o endereço configurado e crie a conta de administrador. Essa tela só aparece enquanto não existe nenhum usuário.

## 3. Modos de acesso

O modo é definido no `.env` (há exemplos comentados no `.env.example`).

| Modo | Quando usar | Configuração |
|---|---|---|
| Rede local (padrão) | Uso só dentro da sua rede | `SITE_ADDRESS=:80`, `HTTP_PORT=8080` |
| Túnel | Acesso pela internet sem abrir portas no roteador | Cloudflare Tunnel com `--profile tunnel` e `CLOUDFLARE_TUNNEL_TOKEN`, ou Tailscale instalado no servidor |
| Público | Domínio próprio com HTTPS automático | `SITE_ADDRESS=seu.dominio`, `HTTP_PORT=80`, `HTTPS_PORT=443` |

Em qualquer modo exposto à internet, use `COOKIE_SECURE=true` e ajuste `PUBLIC_URL` para o endereço real (ele é usado nos links de convite).

Com **Tailscale**, instale o Tailscale no servidor, mantenha o modo rede local e acesse pelo endereço do servidor na sua tailnet.

## 4. IA local (opcional)

```bash
docker compose --profile local-ai up -d
docker compose exec ollama ollama pull qwen3:8b
docker compose exec ollama ollama pull bge-m3
```

Com uma GPU de 11 GB, um modelo de 7 a 9B em Q4 e o modelo de embeddings cabem juntos.

Depois, entre como administrador e abra **IA** no topo da página:

1. Em **Provedores**, clique em **Adicionar provedor**, escolha **Ollama (local)** e salve. O endereço já vem preenchido (`http://ollama:11434/v1`). Use **Testar** para ver os modelos baixados.
2. Em **Modelos por tarefa**, escolha o provedor e escreva o nome do modelo: `qwen3:8b` para a triagem e `bge-m3` para os embeddings.
3. Em cada projeto, a aba **IA** liga a IA, define se ela só sugere ou se atua como segunda revisora, e permite rodar uma calibração antes de confiar nela.

Se você já tem um Ollama rodando fora do Docker no mesmo servidor, não ative o profile e cadastre o endereço `http://host.docker.internal:11434/v1`.

### APIs remotas

Qualquer serviço que siga o formato de chat compatível com OpenAI funciona: escolha o tipo na lista (ou **Outro**), cole a chave de API e informe o preço por milhão de tokens para o ReValli estimar o custo antes de cada execução. As chaves ficam cifradas no banco com a chave secreta da instalação (veja `SECRET_KEY` no `.env`). Projetos marcados como **Só IA local** nunca enviam dados para provedores remotos.

## 5. Backup

```bash
docker compose --profile backup up -d
```

Gera um dump do banco por dia em `deploy/backups/` e apaga os mais antigos que `BACKUP_KEEP_DAYS`. Copie essa pasta para outro disco ou outra máquina.

Restaurar um dump:

```bash
docker compose stop api worker
docker compose exec -T db pg_restore --clean --if-exists -U revalli -d revalli < backups/ARQUIVO.dump
docker compose start api worker
```

## 6. Atualizar

```bash
git pull
docker compose up -d --build
```

As migrações do banco rodam automaticamente quando a API sobe. Faça um backup antes de atualizar.

## 7. Diagnóstico

```bash
docker compose ps
docker compose logs -f api worker
curl http://localhost:8080/api/health
```
