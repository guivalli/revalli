# Checklist do que falta

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

Lista viva do que falta. O que cada marco já entrega está no [roteiro](docs/roteiro.md). Os passos que dependem de uma pessoa (servidor, contas, prints) estão em [checklist-humano.md](checklist-humano.md). Marque com `x` ao concluir.

Estado em 2026-10-12: tudo na `main` (`0bd077d`), com os PRs `#1` a `#6` mesclados; a stack local roda em `http://localhost:1515` e, pelo túnel, em `https://revalli.serverdosbroderz.uk`; 215 testes do backend passam; migrações até a `0018`.

## 1. Beta com avaliadores (duplo cego)

Os itens que dependem de pessoas estão no [checklist-humano.md](checklist-humano.md). Do lado do código:

- [ ] **Tela de triagem com a mesma cara do resto**: barra grande Incluir, Talvez e Excluir, lista numerada à esquerda e painel de palavras-chave. É a tela que os avaliadores mais usam.
- [ ] Opção de **mascarar autores, revista e ano** durante a triagem, se o protocolo exigir cegamento total (hoje o cegamento é só entre as decisões dos revisores).
- [ ] Tela de **Extração** em formato de tabela, com o botão de anexar PDF em cada linha.
- [ ] Conferir no navegador, em tema claro e escuro, as telas que ainda não foram vistas depois da interface nova: Triagem, Duplicatas, Extração, Síntese, Relatório, Protocolo, IA do projeto e Conversa.
- [ ] Recuperação de senha por link já existe; falta só a pessoa líder (não administradora) poder gerar o link para quem é do projeto dela, se o beta pedir.

## 2. Publicar e higiene

- [x] Mesclar os PRs `#1` a `#6` (a `main` está em `0bd077d`).
- [ ] Apagar no GitHub as branches empilhadas `m1-importacao` a `m6-buscas`, que já cumpriram o papel.
- [ ] Revogar o token do GitHub colado numa sessão anterior.
- [ ] Trocar a chave do OpenAlex se não quiser mantê-la no histórico de conversa.
- [ ] Criar uma tag `v0.1.0` para publicar as imagens (`amd64` e `arm64`) no GitHub; é o que o Raspberry Pi vai baixar.

## 3. Verificar contra o mundo real

- [ ] **Triagem por IA com a faixa gratuita**: rodar 10 registros com Gemini Flash-Lite e com Groq e anotar ritmo, erros e concordância com a decisão humana (a calibração está na aba IA do projeto).
- [ ] Medir a triagem por IA com critérios detalhados: calibração em decisões humanas reais e o benchmark em mais conjuntos, com um modelo maior (o llama3.1 8B ficou com 93% de sensibilidade e 29% de especificidade num conjunto).
- [ ] Avaliar o agrupamento de motivos de exclusão com volume real (o teste teve 6 motivos distintos, nada para juntar).
- [ ] Testar o assistente de busca com um modelo maior: no teste local faltaram blocos de conceito e houve `[mh]` em termo truncado.
- [ ] Importar exportações reais de SciELO, PePSIC e Portal CAPES (RIS e CSV) e conferir o parser. LILACS/BVS em RIS já foi conferido (22 registros); veja [docs/buscas.md](docs/buscas.md).
- [ ] Buscar PDFs de acesso aberto em um projeto maior: no projeto de teste, 6 de 14 baixaram e os 8 pendentes eram quase todos do PePSIC (bloqueio anti-robô, só à mão).
- [ ] Testar um provedor de login único além do Keycloak.
- [ ] Convites e redefinição de senha pelo endereço público (túnel) de ponta a ponta.

## 4. Funcionalidades que faltam

- [ ] **Triagem por IA no texto completo, lendo o PDF.** Hoje a IA só vale em título e resumo, e o botão fica escondido no texto completo. Plano: texto do PDF principal até `AI_EXTRACT_MAX_CHARS`, pular estudos sem PDF ou escaneados, prompt próprio, prévia de custo contando o texto. ~1 hora.
- [ ] Parar também embeddings, extração por IA e importações (só a triagem por IA para).
- [ ] OCR de PDFs escaneados.
- [ ] **Bases, próximos passos**: tela para cadastrar a chave do Semantic Scholar (hoje só `SEMANTIC_SCHOLAR_API_KEY` no `deploy/.env`); BDTD (teses brasileiras), Redalyc e Epistemonikos como alvos de importação; verificar uma a uma, antes de prometer, SSRN, RePEc, AGRIS e CAB Abstracts para ciências sociais, humanas e agro.
- [ ] Verificar o OpenAIRE com volume real: as contagens são grandes e cheias de duplicatas entre repositórios; medir quanto a deduplicação resolve.
- [ ] Conferir a sintaxe composta do arXiv (parênteses e `ANDNOT`) contra a API real, quando o limite de ritmo da rede deixar (hoje responde 429).
- [ ] Importar exportações reais de SPORTDiscus, PEDro, EconLit, IEEE Xplore e ACM e conferir o parser.
- [ ] Busca direta em LILACS/BVS (depende de uma chave da API da BVS) e no Portal CAPES (não tem API pública).
- [ ] Título original na importação da BVS: o campo `TI` pode vir em inglês num artigo em português, e a exportação não diz qual título é o original.
- [ ] Acesso pela instituição (CAFe): adiado. O link pelo proxy do Portal CAPES foi tentado e removido em 2026-10-12 (404 e página inicial do Portal; o proxy não atende `doi.org`). Para retomar, é preciso conferir com login real como o Portal monta o endereço de cada editora.
- [ ] Modo de **processo único, sem Redis nem Celery**, para instalar em Windows e Linux sem contêiner (instalador `.exe` e pacote para Linux ficam para depois).
- [ ] Lista de revisões arquivadas na tela inicial.
- [ ] Pendências do M3: Batch APIs, detecção de idioma e de tipo de estudo, tradução.

## 5. Antes de abrir para mais gente

- [ ] Revisão de segurança dedicada.
- [ ] Restringir a rede: o Ollama escuta em `*:11434` sem autenticação, e o auxiliar do Ollama em `0.0.0.0:11435` (só ligar/desligar, com token). Limitar ao IP do servidor (veja o checklist humano).
- [ ] Cloudflare Access na frente do endereço público, com a lista de e-mails dos avaliadores.
- [ ] `COOKIE_SECURE=true` quando só o endereço público (`https://`) for usado.
- [ ] Snowballing e buscas grandes em escala, com os limites reais das bases.
- [ ] Conferir o parser de PDFs de editoras (a maioria bloqueia o download automático).

## Feito recentemente

- [x] **Bases, lote 2** (2026-10-15): busca direta em DOAJ, OpenAIRE e Semantic Scholar (chave gratuita em `SEMANTIC_SCHOLAR_API_KEY`); pacotes de Educação, Sociais e Computação atualizados. OSF Preprints ficou de fora (só filtra substring de título, sem OU).
- [x] **Bases do projeto** (2026-10-15): cartão em Importar com pacotes por área (Saúde, Enfermagem e reabilitação, Psicologia, Educação, Sociais, Computação) que filtra a busca direta, a tradução e o assistente; busca direta nova em ERIC, ClinicalTrials.gov (com campos condição e intervenção), preprints (Europe PMC) e arXiv; alvos de tradução SPORTDiscus, PEDro, EconLit, IEEE Xplore e ACM ([docs/buscas.md](docs/buscas.md)).
- [x] Construtor de busca (operador, termo e campo por linha) com tradução da estratégia para a sintaxe de cada base e lista do que foi corrigido; campos conferidos contra as APIs reais.
- [x] Importação por arquivo agrupa buscas de nome parecido (`source_similar`), para o PRISMA não separar a mesma base com grafias diferentes. Estado: 225 testes do backend passam.
- [x] Interface nova: tela inicial com boas-vindas e tabela, assistente de nova revisão em três passos, Visão geral em cartões com anel de progresso e primeiros passos, menu lateral e gaveta de critérios, abas em pílulas.
- [x] Tema claro, automático e escuro; paleta e logos da marca (azul e verde-limão, com versão para fundo escuro).
- [x] Redefinição de senha: troca na página Conta e link de nova senha gerado pelo administrador em Membros.
- [x] IA com faixa gratuita: limite de pedidos por minuto por provedor, espera e nova tentativa em excesso de pedidos, parada com calma ao fim da cota do dia, presets Groq e Mistral ([docs/ia-gratuita.md](docs/ia-gratuita.md)).
- [x] Acesso de outros avaliadores: convite por link, túnel Cloudflare, Raspberry Pi com a IA no computador ([docs/avaliadores.md](docs/avaliadores.md)).
- [x] Scripts de instalação rápida (`deploy/install.sh` e `deploy/install.ps1`) e imagens `arm64` na publicação.
- [x] Lista de projetos com número de referências e responsável; PRs `#1` a `#6` mesclados na `main`.
- [x] Tela IA: o modelo de cada tarefa é uma lista dos modelos do provedor (com "Outro" para digitar).
- [x] Embeddings recusados (modelo de chat) não derrubam a indexação do corpus; a instalação usa `bge-m3`.
- [x] Busca de PDFs reexecutada com contagem por fonte; par duplicado entre versão online e impressa agrupado para revisão.
- [x] Porta local 1515 e túnel público; ligar e desligar o Ollama pela tela IA ([docs/ollama.md](docs/ollama.md)).
- [x] Chave do OpenAlex pela interface; conversa do assistente de busca salva por pessoa e projeto.
- [x] Importação da BVS conferida com exportação real; busca de PDFs em cadeia com lista de pendentes ([docs/texto-completo.md](docs/texto-completo.md)).
- [x] Triagem por IA restrita a título e resumo (botão escondido e API recusa no texto completo).
