# ReValli

Plataforma open source e auto-hospedada para conduzir revisões de literatura (sistemáticas, de escopo e integrativas) em equipe, com recursos de IA que podem rodar em modelos locais ou em APIs remotas.

> [!WARNING]
> **Este projeto é vibecodado.** Todo o código está sendo escrito com auxílio intensivo de IA (assistentes de programação baseados em modelos de linguagem), com revisão humana limitada. Ele é experimental, pode conter erros e falhas de segurança, e não passou por auditoria. Use por sua conta e risco, mantenha backups e não o use como única fonte de registro de uma revisão sem conferir os resultados.

## Estado atual

Versão **0.1.0-dev (M0 e M1)**. O que já funciona:

- Instalação com Docker Compose (banco, fila, API, worker e servidor web).
- Configuração inicial com criação do administrador.
- Login, logout e sessões seguras (cookie httpOnly).
- Projetos de revisão com papéis (líder, revisor, árbitro, extrator, observador).
- Convites por link, para a instalação ou para um projeto.
- Interface em português e inglês.
- Importação de referências em RIS, PubMed (MEDLINE e XML), BibTeX, Web of Science e CSV, com registro da estratégia de busca, data e número de resultados de cada base.
- Detecção de duplicatas por DOI, PMID e título parecido, com tela de revisão lado a lado.
- Preenchimento automático de resumos, DOIs e PMIDs faltantes pela API pública do [OpenAlex](https://openalex.org).
- Contagens de identificação (registros por fonte, duplicatas removidas, registros únicos).

A triagem e os recursos de IA vêm nos próximos marcos (veja o [roteiro](docs/roteiro.md)).

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
