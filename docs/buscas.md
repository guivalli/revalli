# Buscas por API e snowballing

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

## Busca direta nas bases

Na aba **Importar**, o cartão **Buscar direto na base** consulta pela API pública:

| Base | Sintaxe aceita |
|---|---|
| PubMed | A mesma do site: MeSH com `[mh]`, campos como `[tiab]`, `AND`, `OR`, `NOT`, truncamento com `*` |
| OpenAlex | Palavras, frases entre aspas, `AND`, `OR`, `NOT` em maiúsculas e parênteses, sem campos. Com `*` ou `?` a busca vira exata (sem radicalização), exigência do OpenAlex |
| Europe PMC | Campos como `TITLE:`, `ABSTRACT:`, `KW:` e `MESH:`, com `AND`, `OR` e `NOT` |
| SciELO | A do OpenAlex (palavras, aspas, `AND`, `OR`, `NOT`, parênteses; `*` liga a busca exata) |
| PePSIC | A do OpenAlex |

**SciELO e PePSIC** não usam o buscador do SciELO (que bloqueia robôs): o ReValli lista as revistas da coleção (SciELO Brasil, cerca de 430; PePSIC, cerca de 120) pela API ArticleMeta e busca no OpenAlex só nelas. A cobertura é a do OpenAlex nessas revistas, então pode diferir do que o portal mostra. Cada busca faz uma consulta por lote de 50 revistas e soma as contagens; a lista de revistas fica em cache por 24 horas. Se a base pedir calma (HTTP 429) ou falhar por instantes, o ReValli tenta de novo até 4 vezes, esperando mais a cada tentativa; se ainda assim falhar, a tela mostra o motivo devolvido pela base. A busca aparece no PRISMA como "SciELO (via OpenAlex)" ou "PePSIC (via OpenAlex)". O endereço do ArticleMeta é `ARTICLEMETA_URL`. Atenção: a busca do OpenAlex ordena por relevância e aceita resultados que casam só parte dos termos, então a contagem tende a ser larga (num teste real, "ansiedade AND exercício" no SciELO deu 5.724 resultados, com itens fora do tema entre os primeiros). Confira a amostra antes de importar e refine na triagem.

1. Escolha a base e cole a estratégia.
2. **Contar resultados** mostra quantos registros a base tem e os cinco primeiros, para conferir a string.
3. **Importar resultados** traz até o limite escolhido (no máximo `API_SEARCH_MAX`, 10.000 por padrão).

A importação vira uma busca como as feitas por arquivo: data, estratégia, número informado pela base e número importado ficam registrados para o relato PRISMA-S. Depois, a deduplicação roda sozinha.

### LILACS e Portal CAPES (e o buscador do SciELO)

LILACS/BVS e Portal de Periódicos CAPES **não têm busca direta** no ReValli. Testamos (2026-10-11) o acesso programático:

| Base | Resultado do teste | Como usar |
|---|---|---|
| BVS / LILACS | O portal de busca responde 403 com desafio anti-robô; a API oficial exige chave de registro (401 sem ela) | Exporte do portal e importe o arquivo |
| Portal de Periódicos CAPES | Sem API pública; o acesso completo depende da instituição | Exporte e importe |
| Buscador do SciELO e do PePSIC | Mesmo desafio anti-robô (403); a API ArticleMeta só lista revistas e consulta por identificador | Use a busca via OpenAlex acima, ou exporte e importe |

O ReValli não contorna desafios anti-robô. O fluxo para estas bases é:

1. Em **Traduzir a estratégia para outra base**, escolha **BVS / LILACS**, **SciELO**, **PePSIC** ou **Portal de Periódicos CAPES**. A IA adapta a estratégia e sugere sinônimos em português e espanhol.
2. Rode a busca no portal e exporte os resultados em RIS ou CSV.
3. Em **Importar**, envie o arquivo e escolha a base no campo **Base de dados** (LILACS, BVS, SciELO, Portal CAPES e PePSIC já aparecem na lista). A data, a estratégia e o número informado pela base entram no registro da busca (PRISMA-S).

#### O que o ReValli faz com a exportação da BVS

Conferido com uma exportação real em RIS (22 registros, LILACS e INDEXPSI, 2026-10-12):

- **Descritores (DeCS/MeSH):** quando o registro não tem palavras-chave do autor, os descritores entram como palavras-chave.
- **Dois idiomas:** os resumos em português e em inglês ficam juntos no resumo. O título traduzido (campo `TT`) fica no registro bruto e é usado na deduplicação.
- **Duplicatas entre LILACS e INDEXPSI:** o mesmo artigo costuma vir duas vezes, com o título em idiomas diferentes. Mesmo DOI, mesmo primeiro autor e mesmo ano viram duplicata confirmada. Quando o DOI difere (versão eletrônica e impressa) mas o título de um é o título traduzido do outro, o par vai para revisão manual.
- **Limpeza:** aspas e travessões do Windows-1252 que chegam como caracteres de controle voltam ao caractere certo, a marca `(AU)` de resumo de autor sai do texto e páginas `0-0` ficam em branco.
- **Não resolvido:** a exportação não indica qual dos dois títulos é o original. O título principal é o campo `TI`, que pode estar em inglês mesmo com o artigo em português.

### Limites do OpenAlex e a chave gratuita

PubMed, Europe PMC e OpenAlex são consultados sem cadastro, mas o OpenAlex (usado também por SciELO, PePSIC e snowballing) impõe limites que apareceram nos testes:

- **Orçamento diário sem chave:** é pequeno e compartilhado por todos na mesma rede. Quando acaba (volta à meia-noite UTC), a busca falha na hora com o aviso de que é preciso uma chave. SciELO e PePSIC gastam mais, porque fazem uma consulta por lote de 50 revistas.
- **Estratégias grandes:** consultas com mais de 5 operadores `AND`/`OR`/`NOT` ficam limitadas a 1 por segundo (5 por segundo com chave). O ReValli espaça essas chamadas sozinho e respeita o tempo que a base pede; uma contagem no SciELO leva cerca de 12 s por isso.
- **Frases com curinga:** o OpenAlex recusa `"efeito* adverso*"`. O ReValli reescreve para `(efeito* AND adverso*)`, um pouco mais amplo, e mostra a estratégia reescrita em **Como a base interpretou a estratégia**.

**A chave é gratuita:** crie uma conta em openalex.org, copie a chave em `openalex.org/settings/api` e coloque `OPENALEX_API_KEY=...` em `deploy/.env`. Depois, suba de novo os contêineres da API e do worker.

### Conversar com a IA para montar a busca

No cartão **Buscar direto na base**, **Conversar com a IA para montar a busca** recebe a descrição do que você quer pesquisar e das bases (por exemplo, "os efeitos iatrogênicos de falar sobre bullying, no PubMed e no SciELO"). A IA responde o que entendeu, faz até 3 perguntas se faltar algo e escreve **uma estratégia por base**, em blocos de conceitos ligados por `AND`, com sinônimos em português, inglês e espanhol. Responda na própria conversa para refinar.

Cada estratégia tem **Copiar** (para colar no portal da base) e, nas bases com busca direta, **Usar na busca direta**, que a coloca no campo de estratégia. Sem bases citadas, ela propõe PubMed e SciELO. Exige a IA ligada no projeto; usa o modelo de triagem e conta no uso e no orçamento. A conversa fica só na tela (não é salva). Nos testes com um modelo local de 14 bilhões de parâmetros, a estratégia veio boa como ponto de partida, mas com blocos de conceito a menos e, uma vez, um `[mh]` em termo truncado que o PubMed não aceita: **confira a contagem e a amostra antes de importar**.

### Tradução da estratégia (IA)

Em **Traduzir a estratégia para outra base**, a IA adapta campos, vocabulário controlado (MeSH, Emtree, DeCS) e operadores para PubMed, OpenAlex, Europe PMC, Scopus, Web of Science, Embase, CINAHL, APA PsycInfo, Cochrane Library, BVS/LILACS, SciELO, PePSIC ou Portal de Periódicos CAPES. Usa o modelo de triagem configurado em **IA** e respeita o "só IA local" e o orçamento do projeto. A tradução é um rascunho: confira os termos e o número de resultados antes de usar.

## Snowballing

O cartão **Snowballing (busca de citações)** usa os estudos incluídos na fase de texto completo como sementes:

- **Para trás:** as referências bibliográficas de cada semente.
- **Para frente:** os trabalhos que citam cada semente.

Cada semente é localizada no OpenAlex pelo DOI, pelo PMID ou, sem identificador, por um título quase idêntico. Sementes não encontradas aparecem no resumo do resultado.

Registros que já estão no projeto (mesmo DOI, PMID ou ID do OpenAlex) são ignorados. Os novos entram na triagem como uma busca do tipo "busca de citações", e cada registro mostra de quais estudos incluídos veio. No fluxograma PRISMA 2020, eles aparecem em **Outros métodos**, separados das bases de dados.

## Configuração

No `.env` (veja `deploy/.env.example`):

| Variável | Padrão | Uso |
|---|---|---|
| `SEARCH_APIS_ENABLED` | `true` | Desligue em servidores sem internet |
| `ENRICHMENT_CONTACT_EMAIL` | vazio | E-mail de contato enviado ao OpenAlex e ao PubMed (atendimento prioritário) |
| `NCBI_API_KEY` | vazio | Chave gratuita do NCBI; sobe o limite do PubMed de 3 para 10 requisições por segundo |
| `API_SEARCH_MAX` | `10000` | Máximo de registros por busca ou snowballing |

As requisições saem do worker, na fila `remote`, com uma pausa curta entre elas para respeitar os limites das APIs públicas.
