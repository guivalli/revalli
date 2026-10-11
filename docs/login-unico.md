# Login único (OpenID Connect)

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

O ReValli pode deixar a pessoa entrar com a conta de um provedor OpenID Connect (Keycloak, Authentik, a conta da instituição, entre outros). A entrada por senha continua funcionando.

## Configuração

No `.env` do servidor:

```
OIDC_ISSUER=https://sso.exemplo.org/realms/laboratorio
OIDC_CLIENT_ID=revalli
OIDC_CLIENT_SECRET=...
OIDC_BUTTON_LABEL=Entrar com a conta do laboratório
```

No provedor, cadastre o ReValli como cliente confidencial com o fluxo de código de autorização e este **endereço de retorno** (o mesmo `PUBLIC_URL` do ReValli):

```
https://revalli.exemplo.org/api/auth/oidc/callback
```

Reinicie `api` e `worker`. A tela de entrada passa a mostrar o botão.

| Variável | Para que serve | Padrão |
|---|---|---|
| `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` | ligam o recurso | vazio (desligado) |
| `OIDC_SCOPES` | escopos pedidos | `openid email profile` |
| `OIDC_BUTTON_LABEL` | texto do botão | “Entrar com login único” |
| `OIDC_AUTO_CREATE` | cria a conta de quem entra pela primeira vez | `false` |
| `OIDC_ALLOWED_DOMAINS` | domínios de e-mail aceitos (vírgula) | qualquer um |
| `OIDC_REQUIRE_VERIFIED_EMAIL` | exige `email_verified: true` | `true` |

## Como a pessoa é reconhecida

O ReValli usa o **e-mail** do ID token para achar a conta. Por isso exige que o provedor o declare verificado: sem isso, quem controla um provedor permissivo poderia se passar por outra pessoa. Desligue `OIDC_REQUIRE_VERIFIED_EMAIL` só se o seu provedor não envia o campo `email_verified` e você confia nos e-mails dele.

- E-mail de uma conta existente e ativa: entra na conta.
- E-mail desconhecido: com `OIDC_AUTO_CREATE=false` (o padrão), a pessoa recebe a mensagem de que não há conta e precisa de um convite. Com `true`, a conta é criada **sem permissão de administração** e sem senha.
- Conta desativada: recusada, como na entrada por senha.

Pertencer a projetos continua sendo por convite ou pela liderança; o login único só resolve quem a pessoa é.

## O que é validado

Fluxo de código com PKCE (S256), `state` e `nonce` amarrados ao navegador por um cookie cifrado de 10 minutos. O ID token precisa ter assinatura válida (chaves do `jwks_uri` do provedor), emissor, público (`aud`) e validade corretos, e o `nonce` da tentativa. Os algoritmos aceitos são RS256/384/512, PS256 e ES256/384.

## Limites

- Há um provedor por instalação.
- Não há sincronização de grupos nem de papéis: administração e papéis nos projetos ficam no ReValli.
- Sair do ReValli não encerra a sessão no provedor.
- A configuração é por variáveis de ambiente, sem tela, para que o segredo do cliente não passe pelo banco.
- Foi verificado contra um Keycloak 26.0 real (veja abaixo). Outros provedores (Authentik, Azure AD, Google etc.) não foram testados.

## Verificação contra um provedor real

Em 2026-10-11 o fluxo foi exercitado, de ponta a ponta e sem simulação, contra um Keycloak 26.0 (`start-dev`, cliente confidencial com PKCE S256 exigido) e a API do ReValli em outro processo, navegando como um navegador (formulário de login do provedor, redirecionamento de volta, cookie de sessão). Resultado:

| Situação | Resultado |
|---|---|
| Conta existente, e-mail verificado | entra; sessão válida em `/api/auth/me` |
| E-mail não verificado no provedor | `erro=email_not_verified` |
| Sem conta, `OIDC_AUTO_CREATE=false` | `erro=no_account` |
| Sem conta, `OIDC_AUTO_CREATE=true` | conta criada sem administração e sem senha; entrada por senha responde 401 |
| Conta desativada | `erro=account_disabled` |
| Domínio fora de `OIDC_ALLOWED_DOMAINS` | `erro=domain_not_allowed` |
| `state` forjado | `erro=state_mismatch` |
| Sem o cookie da tentativa | `erro=invalid_attempt` |
| Mesmo código usado duas vezes | `erro=token_exchange_failed` (o provedor recusa) |
| Provedor responde `login_required` | `erro=provider_login_required` |
| Senha errada | o provedor recusa; o ReValli nem é chamado |

Observação para quem testa por script: o Keycloak marca os cookies da tela de login como `Secure`, e clientes HTTP comuns não os reenviam por HTTP puro (navegadores reenviam para `localhost`). Em produção o acesso é por HTTPS e isso não importa.
