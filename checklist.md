# Checklist do que falta

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

Lista viva do que falta. O que cada marco já entrega está no [roteiro](docs/roteiro.md). Marque com `x` ao concluir.

Estado em 2026-10-12: tudo commitado e enviado na branch `m6-buscas` (CI verde) até `774ef2b`; a stack local roda em `http://localhost:1515`; 207 testes do backend passam.

## 1. Fechar o trabalho recente

- [x] Ver no navegador as telas novas que ainda não foram conferidas: aba Configurações do projeto, cartões do Protocolo (critérios detalhados, etiquetas, motivos), painel de sugestão na sessão de triagem, assistente de busca em Importar (conversa salva e **Recomeçar**).
- [x] Testar **Parar** e **Continuar** a triagem por IA com o worker real pelo navegador. **Parar** foi visto de verdade (job `cancelled` com 5 de 354); falta **Continuar**, que falhou porque o Ollama estava desligado. Ligue o Ollama na tela IA e rode de novo.
- [x] Conferir o clique na tela do cartão **Chave do OpenAlex** (menu IA) e, se quiser, passar a chave do `deploy/.env` para a interface.
- [X] Apagar `erro.png` (captura de tela na raiz, não versionada) e arquivar ou apagar o `HANDOFF.md`, que descreve outro ambiente.

## 2. Publicar

- [ ] Mesclar os PRs `#1` a `#6`, nessa ordem. Não há conflito com a `main` nem precisa de rebase. A CI só rodou no `#6`; use **Re-run** (ou um push vazio) nos `#1` a `#5` se quiser vê-la verde em cada um.
- [ ] Revogar o token do GitHub colado numa sessão anterior.
- [ ] Trocar a chave do OpenAlex se não quiser mantê-la no histórico de conversa.

## 3. Verificar contra o mundo real

- [x] Rodar de novo **Buscar PDFs de acesso aberto** e contar por fonte (2026-10-12): nenhum PDF novo; 6 de 14 com PDF (4 OpenAlex, 2 página do artigo). Dos 8 pendentes, OpenAlex e Unpaywall conhecem 1 PDF (PePSIC, 403), Europe PMC 0, e a página do artigo falhou em todos (7 do PePSIC por anti-robô ou 404, 1 timeout da UEL). O gargalo é o PePSIC: só à mão, pela lista de pendentes. Ainda vale avaliar Semantic Scholar, CORE, Redalyc e LA Referencia, mas nenhum resolve o PePSIC.
- [ ] Medir a triagem por IA com critérios detalhados: calibração em decisões humanas reais e o benchmark em mais conjuntos, com um modelo maior (o llama3.1 8B ficou com 93% de sensibilidade e 29% de especificidade num conjunto).
- [ ] Avaliar o agrupamento de motivos de exclusão com volume real (o teste teve 6 motivos distintos, nada para juntar).
- [ ] Testar o assistente de busca com um modelo maior: no teste local faltaram blocos de conceito e houve `[mh]` em termo truncado.
- [ ] Importar exportações reais de SciELO, PePSIC e Portal CAPES (RIS e CSV) e conferir o parser. LILACS/BVS em RIS já foi conferido (22 registros) e gerou correções; veja [docs/buscas.md](docs/buscas.md).
- [ ] Testar um provedor de login único além do Keycloak.

## 4. Funcionalidades que faltam

- [ ] **Triagem por IA no texto completo, lendo o PDF.** Hoje a IA só vale em título e resumo, e o botão fica escondido no texto completo. Plano: texto do PDF principal até `AI_EXTRACT_MAX_CHARS`, pular estudos sem PDF ou escaneados, prompt próprio, prévia de custo contando o texto. ~1 hora.
- [ ] Parar também embeddings, extração por IA e importações (só a triagem por IA para).
- [x] Modelo de embeddings dedicado: a instalação usa `bge-m3`; um modelo de chat nessa tarefa agora gera aviso claro e a indexação mantém a busca por palavras.
- [ ] OCR de PDFs escaneados.
- [ ] Acesso pela instituição (CAFe): adiado. O link pelo proxy do Portal CAPES foi tentado e removido em 2026-10-12 (404 e página inicial do Portal; o proxy não atende `doi.org`). Para retomar, é preciso conferir com login real como o Portal monta o endereço de cada editora.
- [ ] Busca direta em LILACS/BVS (depende de uma chave da API da BVS) e no Portal CAPES (não tem API pública).
- [ ] Título original na importação da BVS: o campo `TI` pode vir em inglês num artigo em português, e a exportação não diz qual título é o original.
- [ ] Pendências do M3: Batch APIs, detecção de idioma e de tipo de estudo, tradução.

## 5. Antes de expor à internet

- [ ] Revisão de segurança dedicada.
- [ ] Restringir a rede: o Ollama escuta em `*:11434` sem autenticação, e o auxiliar do Ollama em `0.0.0.0:11435` (só ligar/desligar, com token). Fechar as duas portas no firewall ou limitar o endereço.
- [ ] Verificar os modos de acesso (rede local, túnel, domínio público) de ponta a ponta.
- [ ] Snowballing e buscas grandes em escala, com os limites reais das bases.
- [ ] Conferir o parser de PDFs de editoras (a maioria bloqueia o download automático).

## Feito recentemente

- [x] Tela IA: o modelo de cada tarefa é uma lista dos modelos do provedor (com "Outro" para digitar).
- [x] Embeddings recusados (modelo de chat) não derrubam a indexação do corpus: aviso na aba Conversa e mensagens claras para provedor fora do ar.
- [x] Busca de PDFs reexecutada com contagem por fonte; par duplicado entre versão online e impressa achado e agrupado para revisão.
- [x] Commit e envio do trabalho para o GitHub; CI verde na `m6-buscas`; sem conflitos nem rebase necessário.
- [x] Porta local 1515 (`HTTP_PORT` e `PUBLIC_URL` em `deploy/.env`).
- [x] Ligar e desligar o Ollama pela tela IA, com auxiliar no computador ([docs/ollama.md](docs/ollama.md)).
- [x] Chave do OpenAlex pela interface.
- [x] Conversa do assistente de busca salva por pessoa e projeto.
- [x] Importação da BVS conferida com exportação real (descritores, `(AU)`, páginas `0-0`, duplicatas entre idiomas).
- [x] Busca de PDFs em cadeia (OpenAlex, Unpaywall, Europe PMC, página do artigo), lista de pendentes com DOI e link ([docs/texto-completo.md](docs/texto-completo.md)).
- [x] Triagem por IA restrita a título e resumo (botão escondido e API recusa no texto completo).
