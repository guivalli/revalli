# Ligar e desligar o Ollama

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

O Ollama roda a IA local (GPU do próprio computador). Nesta máquina ele é um serviço do sistema (`systemd`), instalado em `/usr/local/bin/ollama`, e escuta na porta `11434`.

## Ver o estado

```bash
systemctl is-active ollama     # active = rodando
systemctl is-enabled ollama    # enabled = sobe sozinho quando o computador liga
ollama ps                      # modelos carregados na memória agora
```

## Ligar e desligar agora

```bash
sudo systemctl start ollama    # liga
sudo systemctl stop ollama     # desliga (libera a GPU e a memória)
sudo systemctl restart ollama  # reinicia (aplica mudança de configuração)
```

## Subir (ou não) junto com o computador

```bash
sudo systemctl enable ollama           # passa a subir no boot
sudo systemctl disable ollama          # não sobe mais no boot
sudo systemctl disable --now ollama    # desabilita e desliga agora
```

Com o serviço desabilitado, o ReValli continua funcionando; só a triagem por IA, os embeddings e a extração por IA falham até o Ollama voltar.

## Liberar a memória sem desligar

O Ollama mantém o modelo carregado por 30 minutos depois do último uso. Para descarregar já:

```bash
ollama stop NOME_DO_MODELO     # veja o nome em `ollama ps`
```

## Quem pode acessar

Por padrão o serviço escuta em todas as interfaces (`*:11434`) e **não tem autenticação**: qualquer aparelho da rede local consegue usar a sua GPU. Para restringir ao próprio computador:

```bash
sudo systemctl edit ollama
```

Escreva no editor que abrir:

```ini
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
```

Salve e rode `sudo systemctl restart ollama`.

Os contêineres do ReValli chegam ao Ollama pelo nome `host.docker.internal`. Se o serviço escutar só em `127.0.0.1`, esse caminho pode deixar de funcionar; nesse caso use o endereço da ponte do Podman (`OLLAMA_HOST=0.0.0.0:11434` com firewall) ou rode o Ollama como contêiner, com `--profile local-ai` do `docker-compose.yml`.

## Pelo ReValli (botão Ligar/Desligar)

Na tela **IA** (menu superior, só administradores), o cartão **Ollama neste computador** mostra se o serviço está ligado, se sobe junto com o computador e tem o botão **Ligar** ou **Desligar**. O cartão só aparece depois de instalado o auxiliar.

### Como funciona

O contêiner da API não pode controlar serviços do computador. Por isso há um auxiliar pequeno (`deploy/ollama-helper/ollama_helper.py`, só biblioteca padrão) que roda no computador, fora dos contêineres:

- aceita só `GET /status`, `POST /start` e `POST /stop`, e sempre sobre o serviço `ollama` (o nome não vem do pedido);
- exige o cabeçalho `Authorization: Bearer <token>`; sem ele responde 401;
- a permissão de ligar e desligar vem de uma regra do `polkit` que vale só para `ollama.service` e só para o seu usuário.

### Instalar

No **seu** terminal, na raiz do projeto (pede a senha do `sudo` uma vez):

```bash
bash deploy/ollama-helper/install.sh
```

O script:

1. copia o auxiliar para `~/.config/revalli/` e gera um token (arquivo `ollama-helper.env`, só você lê);
2. cria e liga o serviço de usuário `revalli-ollama-helper` (porta `11435`);
3. grava a regra `/etc/polkit-1/rules.d/50-revalli-ollama.rules` (com `sudo`);
4. escreve `OLLAMA_HELPER_URL` e `OLLAMA_HELPER_TOKEN` em `deploy/.env`.

Depois recrie a API e o worker:

```bash
podman-compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --force-recreate --no-deps api worker
```

### Remover

```bash
bash deploy/ollama-helper/uninstall.sh
```

### Segurança

- O auxiliar escuta em `0.0.0.0:11435` porque o contêiner só alcança o computador por uma interface de rede, não pelo `127.0.0.1`. Quem estiver na sua rede local chega à porta, mas sem o token só recebe 401, e com ele só consegue ligar ou desligar o Ollama. Para fechar a porta à rede, restrinja a `11435` no firewall do computador.
- O token fica em `~/.config/revalli/ollama-helper.env` e em `deploy/.env` (ignorado pelo git). Para trocar, apague o primeiro arquivo e rode `install.sh` de novo.
- Só administradores da instalação usam o botão.
- O botão só controla o Ollama do computador onde o auxiliar está instalado; num servidor remoto ele não aparece.
