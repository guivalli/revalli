# Checklist do que falta

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

Lista viva do que falta. O que cada marco já entrega está no [roteiro](docs/roteiro.md). Marque com `x` ao concluir.

Estado em 2026-10-12: tudo commitado e enviado na branch `m6-buscas` (CI verde); a stack local roda em `http://localhost:1515`; 205 testes do backend passam.

## 1. Fechar o trabalho recente

- [ ] Ver no navegador as telas novas que ainda não foram conferidas: aba Configurações do projeto, cartões do Protocolo (critérios detalhados, etiquetas, motivos), painel de sugestão na sessão de triagem, assistente de busca em Importar (conversa salva e **Recomeçar**).
- [ ] Testar **Parar** e **Continuar** a triagem por IA com o worker real pelo navegador (os testes cobrem o mecanismo, não o clique).
- [ ] Conferir o clique na tela do cartão **Chave do OpenAlex** (menu IA) e, se quiser, passar a chave do `deploy/.env` para a interface.
- [ ] Salvar o modelo da CAFe (menu IA → Acesso pela instituição): `https://{host}.ez128.periodicos.capes.gov.br{path}`. Conferir se o link que parte do `doi.org` funciona pelo proxy; se não, resolver o endereço da editora antes de aplicar o modelo.
- [ ] Apagar `erropdf.png` (captura de tela na raiz, não versionada) e arquivar ou apagar o `HANDOFF.md`, que descreve outro ambiente.

## 2. Publicar

- [ ] Mesclar os PRs `#1` a `#6`, nessa ordem. Não há conflito com a `main` nem precisa de rebase. A CI só rodou no `#6`; use **Re-run** (ou um push vazio) nos `#1` a `#5` se quiser vê-la verde em cada um.
- [ ] Revogar o token do GitHub colado numa sessão anterior.
- [ ] Trocar a chave do OpenAlex se não quiser mantê-la no histórico de conversa.

## 3. Verificar contra o mundo real

- [ ] Rodar de novo **Buscar PDFs de acesso aberto** (a cadeia nova: paralelismo, páginas do OpenAlex, IPv6) e contar quantos vêm de cada fonte. No teste anterior, 6 de 14 baixaram e 8 ficaram pendentes (PePSIC responde 403 por anti-robô; DOIs que não resolvem; servidores lentos). Se os pendentes forem muitos, avaliar Semantic Scholar, CORE, Redalyc e LA Referencia como fontes.
- [ ] Medir a triagem por IA com critérios detalhados: calibração em decisões humanas reais e o benchmark em mais conjuntos, com um modelo maior (o llama3.1 8B ficou com 93% de sensibilidade e 29% de especificidade num conjunto).
- [ ] Avaliar o agrupamento de motivos de exclusão com volume real (o teste teve 6 motivos distintos, nada para juntar).
- [ ] Testar o assistente de busca com um modelo maior: no teste local faltaram blocos de conceito e houve `[mh]` em termo truncado.
- [ ] Importar exportações reais de SciELO, PePSIC e Portal CAPES (RIS e CSV) e conferir o parser. LILACS/BVS em RIS já foi conferido (22 registros) e gerou correções; veja [docs/buscas.md](docs/buscas.md).
- [ ] Testar um provedor de login único além do Keycloak.

## 4. Funcionalidades que faltam

- [ ] **Triagem por IA no texto completo, lendo o PDF.** Hoje a IA só vale em título e resumo, e o botão fica escondido no texto completo. Plano: texto do PDF principal até `AI_EXTRACT_MAX_CHARS`, pular estudos sem PDF ou escaneados, prompt próprio, prévia de custo contando o texto. ~1 hora.
- [ ] Parar também embeddings, extração por IA e importações (só a triagem por IA para).
- [ ] Modelo de embeddings dedicado (`bge-m3` ou `nomic-embed-text`): a configuração atual usa `qwen2.5:14b` também para embeddings, o que é lento e fraco.
- [ ] OCR de PDFs escaneados.
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

- [x] Commit e envio do trabalho para o GitHub; CI verde na `m6-buscas`; sem conflitos nem rebase necessário.
- [x] Porta local 1515 (`HTTP_PORT` e `PUBLIC_URL` em `deploy/.env`).
- [x] Ligar e desligar o Ollama pela tela IA, com auxiliar no computador ([docs/ollama.md](docs/ollama.md)).
- [x] Chave do OpenAlex pela interface.
- [x] Conversa do assistente de busca salva por pessoa e projeto.
- [x] Importação da BVS conferida com exportação real (descritores, `(AU)`, páginas `0-0`, duplicatas entre idiomas).
- [x] Busca de PDFs em cadeia (OpenAlex, Unpaywall, Europe PMC, página do artigo), lista de pendentes com DOI e link, e link pela CAFe ([docs/texto-completo.md](docs/texto-completo.md)).
- [x] Triagem por IA restrita a título e resumo (botão escondido e API recusa no texto completo).
