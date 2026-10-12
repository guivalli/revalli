# Trabalhar com outros avaliadores (duplo cego)

> O ReValli é um projeto vibecodado. Antes de expor o servidor à internet, leia o aviso do README.

## 1. Configurar a triagem duplo cega

1. Em **Protocolo**, defina **2 revisores por fase** (título e resumo, texto completo) e deixe o **cegamento ligado**: ninguém vê as decisões dos outros até a fase terminar ou um árbitro abrir o conflito.
2. Em **Membros**, convide cada avaliador como **Revisor**, e uma pessoa como **Árbitro** para resolver os conflitos.
3. Se usar IA como apoio, em **IA** do projeto deixe a sugestão aparecer **depois da decisão** da pessoa, para ela não influenciar quem decide.
4. Cada avaliador vê a fila na aba **Triagem**, na sessão de triagem; o seu progresso e o da equipe aparecem na Visão geral.

O cegamento do ReValli é entre revisores (decisões independentes). Ele **não** esconde autores e revista; se o seu protocolo exige isso, avise para tratarmos como uma opção.

## 2. Como o convidado acessa o servidor

O convite é um **link** que o ReValli gera (aba **Membros**, **Gerar convite**). O ReValli **não envia e-mail**: você copia o link e manda pelo e-mail ou mensagem que preferir. O link usa o endereço configurado em `PUBLIC_URL`, então esse endereço precisa ser acessível por quem recebe.

| Quem acessa | O que usar |
|---|---|
| Mesma rede (laboratório, casa) | `PUBLIC_URL=http://IP-DO-SERVIDOR:8080` |
| Pessoas de fora, sem abrir portas no roteador | **Cloudflare Tunnel** (recomendado) ou Tailscale |
| Pessoas de fora, com domínio e portas abertas | Modo público com HTTPS automático (veja [instalação](instalacao.md)) |

### Cloudflare Tunnel, passo a passo

Precisa de uma conta Cloudflare gratuita e de um domínio gerenciado nela.

1. No painel **Zero Trust**: **Networks → Tunnels → Create a tunnel** (tipo Cloudflared). Copie o **token**.
2. Em **Public hostname**, crie `revalli.seudominio.org` apontando para `http://web:80`.
3. No `deploy/.env` do servidor:
   ```
   CLOUDFLARE_TUNNEL_TOKEN=cole-o-token-aqui
   PUBLIC_URL=https://revalli.seudominio.org
   COOKIE_SECURE=true
   ```
4. Suba com o perfil do túnel: `docker compose --profile tunnel up -d`.
5. Gere o convite em **Membros** e mande o link. Ele já virá com o endereço público.

**Recomendado antes de convidar:** em **Zero Trust → Access → Applications**, crie uma aplicação protegendo `revalli.seudominio.org` com a regra "e-mails permitidos" (código por e-mail). É grátis até 50 pessoas e coloca uma porta de entrada na frente do login do ReValli.

## 3. Rodar em um Raspberry Pi (com a IA no seu computador)

- **Modelo e sistema:** Pi 4 ou 5 com 64 bits e **4 GB ou mais** de RAM, e **SSD por USB** (o banco escreve bastante; cartão SD se desgasta).
- **Imagens:** o aplicativo precisa de imagens `arm64`. Construir no próprio Pi é lento; o fluxo **Publicar imagens** do GitHub gera `amd64` e `arm64` quando você cria uma tag `v*`. No Pi, o `docker compose up -d` baixa as imagens prontas.
- **IA no seu computador:** no computador com GPU, deixe o Ollama escutar na rede (`OLLAMA_HOST=0.0.0.0`) e libere a porta 11434 só para o IP do Pi. No ReValli (menu **IA**), crie um provedor com endereço `http://IP-DO-COMPUTADOR:11434/v1`, marcado como **local**. O botão de ligar/desligar o Ollama usa `OLLAMA_HELPER_URL=http://IP-DO-COMPUTADOR:11435` no `.env`.
- **Sem o computador ligado:** configure um provedor online com faixa gratuita (veja [IA com faixas gratuitas](ia-gratuita.md)) como alternativa.

O Ollama não tem autenticação: não o exponha à internet, só à rede local.
