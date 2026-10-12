# ReValli

Plataforma open source e auto-hospedada para conduzir revisões de literatura (sistemáticas, de escopo e integrativas) em equipe, com recursos de IA que podem rodar em modelos locais ou em APIs remotas.

> [!WARNING]
> **Este projeto é vibecodado.** Todo o código está sendo escrito com auxílio intensivo de IA (assistentes de programação baseados em modelos de linguagem), com revisão humana limitada. Ele é experimental, pode conter erros e falhas de segurança, e não passou por auditoria. Use por sua conta e risco, mantenha backups e não o use como única fonte de registro de uma revisão sem conferir os resultados.

## Estado atual

Versão **0.1.0.dev0 (M0 a M6)**. O que já funciona:

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
- Protocolo da triagem: critérios de inclusão e exclusão, motivos de exclusão, palavras destacadas em verde e vermelho, número de revisores por registro e cegamento.
- Triagem por título e resumo feita pelo teclado (I incluir, E excluir com motivo, M talvez, U desfazer, setas para navegar), com etiquetas e notas.
- Divisão automática do trabalho: cada registro recebe o número de revisores definido no protocolo.
- Painel da triagem com progresso por revisor, concordância (porcentagem e kappa de Cohen), resolução de conflitos com decisão final e lista das minhas decisões.
- Fluxograma PRISMA 2020 gerado a partir das decisões, para baixar em SVG ou PNG.
- Exportação das referências em RIS ou CSV, com estado, motivos de exclusão, etiquetas e decisões (respeitando o cegamento).
- IA plugável: Ollama no próprio servidor ou APIs remotas compatíveis com OpenAI, com chaves cifradas, opção “só IA local” por projeto, estimativa de custo, limite de gasto e cache.
- Triagem por IA como sugestão (mostrada só depois da decisão humana) ou como segunda revisora, checagem dos excluídos e calibração (sensibilidade, especificidade e kappa contra os humanos).
- Aprendizado ativo: a fila de título e resumo pode ser ordenada pelos registros mais prováveis de inclusão, com curva de incluídos e sugestão de parada.
- Benchmark da IA sobre conjuntos já rotulados (veja [docs/benchmark.md](docs/benchmark.md)).
- Texto completo: PDFs enviados um a um ou num ZIP (ligados às referências pelo DOI ou pelo título), busca automática de versões de acesso aberto pelo OpenAlex e visualizador de PDF na tela de triagem, com as palavras do protocolo destacadas no próprio documento.
- Estudos com vários relatórios: agrupamento à mão ou por sugestão (referências que citam o mesmo número de registro de ensaio, como NCT ou ISRCTN), com contagem de estudos e de relatórios no PRISMA.
- Extração de dados: formulários próprios (texto, número, escolha, tabelas por grupo, perguntas condicionais), versionados, com extração em dupla, comparação campo a campo e consenso. Exportação em CSV (uma linha por estudo ou formato longo para R e meta-análise). Veja [docs/extracao.md](docs/extracao.md).
- Extração por IA com citação literal: cada valor vem com o trecho do artigo, que é conferido no texto do PDF e destacado no visualizador. Trechos que não aparecem no PDF ficam marcados para conferência.
- Risco de viés com modelos de RoB 2 (julgamento de cada domínio calculado pelo algoritmo do instrumento) e ROBINS-I, com gráficos de semáforo e de resumo em SVG e PNG.

- Busca direta no PubMed, no OpenAlex e no Europe PMC pela API pública, com contagem e amostra antes de importar, e tradução da estratégia de busca para outras bases com IA (sempre revisada pela pessoa).
- Snowballing pelo OpenAlex: referências dos incluídos (para trás) e trabalhos que os citam (para frente), separados como "outros métodos" no PRISMA. Veja [docs/buscas.md](docs/buscas.md).

- Codificação qualitativa para revisões integrativas e de escopo: árvore de códigos, trechos marcados direto no PDF, matriz de códigos por estudo e exportação em CSV. Veja [docs/sintese.md](docs/sintese.md).
- Meta-análise (RR, OR, RD, MD, SMD, HR ou genérica; efeito fixo ou aleatório, subgrupos, forest plot, funil e Egger) e tabela GRADE de sumário de achados. Veja [docs/sintese.md](docs/sintese.md).
- Checklists PRISMA 2020 e PRISMA-ScR no relatório, com o local de cada item no manuscrito e os dados do projeto que ajudam a escrevê-lo.
- Atualizações automáticas (revisões vivas): repete uma busca ou relê um arquivo de referências numa URL e importa só o que é novo, com aviso na visão geral. Também lê e exporta CSL JSON. Veja [docs/atualizacoes.md](docs/atualizacoes.md).
- Login único por OpenID Connect (opcional), com a entrada por senha mantida. Veja [docs/login-unico.md](docs/login-unico.md).
- IA que detalha os critérios de inclusão e exclusão, sugere incluir ou excluir com o motivo e propõe até 4 etiquetas por registro; edição e exclusão de projetos. Veja [docs/triagem-ia.md](docs/triagem-ia.md).
- Mapa de lacunas de evidência: estudos incluídos cruzados por duas dimensões (códigos ou campos de extração), com as lacunas em destaque. Veja [docs/sintese.md](docs/sintese.md).
- Conversa com os PDFs: perguntas sobre os estudos com resposta só a partir do texto, cada afirmação com trecho e página, e cada citação conferida no PDF. Veja [docs/conversa.md](docs/conversa.md).
- API pública somente leitura (chaves por pessoa ou por projeto, em Minha conta) e servidor MCP para consultar os projetos de um assistente de IA. Veja [docs/api.md](docs/api.md).
- Relatório da revisão em DOCX ou PDF (português ou inglês): rascunho de métodos e resultados com fluxograma PRISMA, estudos incluídos, risco de viés, forest plots, GRADE e códigos, mais apêndices com as estratégias de busca, o registro de uso da IA e o checklist. Veja [docs/relatorio.md](docs/relatorio.md).

O que falta e o que vem depois está no [roteiro](docs/roteiro.md).

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
