# Checklist humano

> Este projeto é vibecodado. O que está aqui precisa de uma pessoa (servidor, contas, olho no navegador). Faça na ordem; cada bloco diz **o que devolver** e em qual pasta pôr os prints (`screenshotrevalli/`).

Tempo total estimado: **1h30**. Marque com `x` ao concluir.

## A. Segurança e dados do servidor (30 min)

- [x] **A1. Atualizar o `.env` do servidor.** Em `deploy/.env`:
  ```
  PUBLIC_URL=https://revalli.serverdosbroderz.uk
  COOKIE_SECURE=true
  ```
  Depois recrie os contêineres (o `.env` só é lido na criação):
  ```bash
  podman-compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --force-recreate --no-deps api worker scheduler web
  ```
  *Atenção:* com `COOKIE_SECURE=true` o login só mantém a sessão por `https://`. Use sempre o endereço público.
  **Devolva:** print da tela de login aberta pelo endereço público (`a1-login.png`).

- [x] **A2. Cloudflare Access.** Zero Trust → Access → Applications → Add → Self-hosted, hostname `revalli.serverdosbroderz.uk`, política "Allow" com os e-mails dos avaliadores (código por e-mail). Teste numa janela anônima.
  **Devolva:** print da tela do Cloudflare pedindo o e-mail (`a2-access.png`).

- [x] **A3. Fechar o Ollama para a rede.** No computador do Ollama, liberar as portas 11434 (Ollama) e 11435 (auxiliar de ligar e desligar) **só** para o IP do Raspberry. Confira o que está aberto com `sudo firewall-cmd --list-all`; se as portas não aparecem, já estão fechadas para a rede (nesse caso, só o Raspberry precisa de uma regra de entrada). Exemplo, trocando `IP_DO_PI`:
  ```bash
  sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="IP_DO_PI" port port="11434" protocol="tcp" accept'
  sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="IP_DO_PI" port port="11435" protocol="tcp" accept'
  sudo firewall-cmd --reload
  ```
  **Devolva:** a saída de `sudo firewall-cmd --list-all` (`a3-firewall.txt`, sem senhas).

- [x] **A4. Backup do banco.** Suba o perfil de backup (gera um dump a cada 24 h, guarda 14 dias, e copia os PDFs e a chave que cifra as chaves de API):
  ```bash
  podman-compose -f deploy/docker-compose.yml --env-file deploy/.env --profile backup up -d
  ```
  Confira que apareceu um arquivo `revalli-*.dump` na pasta `deploy/backups/` (ou em `BACKUP_DIR`). **Copie a pasta para outro disco ou nuvem uma vez por semana**: o backup no mesmo disco não protege contra o disco.
  **Devolva:** print do `ls -la deploy/backups` (`a4-backup.png`).

- [x] **A5. Higiene de chaves.** Revogue o token antigo do GitHub (Settings → Developer settings → Personal access tokens) e gere outra chave do OpenAlex (menu IA do ReValli, cartão da chave). Nada a devolver.

## B. Teste de ponta a ponta com outra pessoa (30 min)

Precisa de **2 contas**: a sua (administradora) e uma de teste (outro e-mail seu serve).

- [x] **B1. Convite.** No projeto de teste, aba **Membros** → gere um convite para o e-mail de teste, papel **Revisor**. Confira que o link começa com `https://revalli.serverdosbroderz.uk/convite/`. Abra numa janela anônima e crie a conta.
  **Devolva:** print do link gerado (`b1-convite.png`) e da tela depois de entrar (`b1-entrada.png`).

- [x] **B2. Protocolo duplo cego.** **Protocolo**: 2 revisores por fase, cegamento ligado. Em **IA** do projeto, sugestões depois da decisão humana.
  **Devolva:** print do Protocolo (`b2-protocolo.png`).

- [x] **B3. Triagem às cegas.** Com as duas contas, triar ~10 registros em **Triagem → sessão**, **de propósito discordando em 2 ou 3**. Confira que cada conta **não vê** a decisão da outra.
  **Devolva:** print da sessão de triagem em cada conta (`b3-sessao-a.png`, `b3-sessao-b.png`).

- [x] **B4. Conflito e árbitro.** Convide uma terceira conta (ou promova a de teste) como **Árbitro**, abra **Triagem → Conflitos** e resolva um.
  **Devolva:** print da tela de conflitos (`b4-conflitos.png`).

- [x] **B5. Senha.** Em **Membros**, gere o **link de nova senha** da conta de teste, abra numa janela anônima e defina uma senha nova. Depois, na conta de teste, **Conta → Senha** e troque de novo.
  **Devolva:** print do link gerado (`b5-reset.png`) e da página Conta (`b5-conta.png`).

## C. IA gratuita (15 min)

- [x] **C1. Chave.** Crie uma chave no Google AI Studio (conta Google, grátis).
- [x] **C2. Provedor.** Menu **IA** → Adicionar provedor → tipo **Google**; cole a chave; confira o limite por minuto sugerido (12) com o que o painel do Google mostra; clique em **Testar**.
  **Devolva:** print da tela IA com o provedor e a lista de modelos (`c2-provedor.png`).
- [x] **C3. Modelo.** Em **Modelos por tarefa → Triagem**, escolha o modelo Flash-Lite da lista. Em **IA** do projeto, **desligue "só local"**.
- [x] **C4. Triagem pequena.** Rode a triagem por IA em ~10 registros. Anote o tempo e se houve erro de cota.
  **Devolva:** print do resultado e do painel de calibração (`c4-ia.png`) e uma linha com o tempo total.

## D. Olhar a interface (15 min)

Em **tema claro e escuro**, abra cada tela e tire um print. Me diga o que está feio, desalinhado ou difícil de achar.

- [x] D1. Tela inicial e assistente de nova revisão, passos 1 a 3 (`d1-home.png`, `d1-wizard.png`).
- [x] D2. Visão geral do projeto com os **Primeiros passos** (`d2-visao.png`).
- [x] D3. Triagem (lista e sessão) (`d3-triagem.png`).
- [x] D4. Referências, Duplicatas e Extração (`d4-*.png`).
- [x] D5. Menu ☰ aberto e a gaveta **Critérios** (`d5-menu.png`, `d5-criterios.png`).
- [x] D6. Uma tela no **celular** (largura estreita) (`d6-celular.png`).

## O que me devolver

Os prints citados acima, em `screenshotrevalli/`, e uma lista curta com:

1. O que **quebrou** (mensagem de erro exata, se houver).
2. O que **confundiu** (onde você ou a outra pessoa hesitou).
3. O que **faltou** para o seu protocolo (por exemplo, mascarar autores e revista).

Com isso eu fecho os itens da seção 1 de [checklist.md](checklist.md).
