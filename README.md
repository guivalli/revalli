# ReValli

![vibecodado](https://img.shields.io/badge/c%C3%B3digo-vibecodado%20(IA)-orange) ![estado](https://img.shields.io/badge/estado-experimental-red)

Plataforma open source e auto-hospedada para conduzir revisões de literatura (sistemáticas, de escopo e integrativas) em equipe, com recursos de IA que podem rodar em modelos locais ou em APIs remotas.

> [!CAUTION]
> ## ⚠️ Este projeto é VIBECODADO
>
> **Todo o código do ReValli foi escrito por assistentes de IA** (modelos de linguagem), com revisão humana limitada. Ele é experimental, não passou por auditoria de segurança e pode conter erros que afetam os resultados de uma revisão.
>
> - **Não exponha à internet** sem uma revisão de segurança própria.
> - **Não use como única fonte de registro** de uma revisão: confira contagens, decisões e exportações.
> - **Mantenha backups** e use por sua conta e risco.
>
> *English: this project is **vibe-coded**. All the code was written by AI assistants with limited human review. It is experimental, unaudited and may contain bugs or security flaws. Use at your own risk.*

## Estado atual

Versão **0.0.x (M0, fundação)**. O que já funciona:

- Instalação com Docker Compose (banco, fila, API, worker e servidor web).
- Configuração inicial com criação do administrador.
- Login, logout e sessões seguras (cookie httpOnly).
- Projetos de revisão com papéis (líder, revisor, árbitro, extrator, observador).
- Convites por link, para a instalação ou para um projeto.
- Interface em português e inglês.

A importação de referências, a triagem e os recursos de IA vêm nos próximos marcos (veja o [roteiro](docs/roteiro.md)).

## Instalação

Requisitos: um servidor Linux com Docker e o plugin Compose. Uma GPU NVIDIA é opcional (usada para IA local).

```bash
git clone https://github.com/guivalli/revalli.git
cd revalli/deploy
cp .env.example .env
# Edite o .env: defina POSTGRES_PASSWORD e escolha o modo de acesso
docker compose up -d --build
```

Acesse `http://IP-DO-SERVIDOR:8080` e crie a conta de administrador. Detalhes, modos de acesso (rede local, túnel ou público), IA local e backup estão em [docs/instalacao.md](docs/instalacao.md).

## Desenvolvimento

Veja [docs/desenvolvimento.md](docs/desenvolvimento.md).

## Licença

[AGPL-3.0](LICENSE). Se você oferecer uma versão modificada do ReValli como serviço na rede, precisa disponibilizar o código-fonte dessas modificações.
