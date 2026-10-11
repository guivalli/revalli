# Buscas por API e snowballing

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

## Busca direta nas bases

Na aba **Importar**, o cartão **Buscar direto na base** consulta pela API pública:

| Base | Sintaxe aceita |
|---|---|
| PubMed | A mesma do site: MeSH com `[mh]`, campos como `[tiab]`, `AND`, `OR`, `NOT`, truncamento com `*` |
| OpenAlex | Palavras, frases entre aspas, `AND`, `OR`, `NOT` em maiúsculas e parênteses, sem campos nem truncamento |
| Europe PMC | Campos como `TITLE:`, `ABSTRACT:`, `KW:` e `MESH:`, com `AND`, `OR` e `NOT` |

1. Escolha a base e cole a estratégia.
2. **Contar resultados** mostra quantos registros a base tem e os cinco primeiros, para conferir a string.
3. **Importar resultados** traz até o limite escolhido (no máximo `API_SEARCH_MAX`, 10.000 por padrão).

A importação vira uma busca como as feitas por arquivo: data, estratégia, número informado pela base e número importado ficam registrados para o relato PRISMA-S. Depois, a deduplicação roda sozinha.

### Tradução da estratégia (IA)

Em **Traduzir a estratégia para outra base**, a IA adapta campos, vocabulário controlado (MeSH, Emtree, DeCS) e operadores para PubMed, OpenAlex, Europe PMC, Scopus, Web of Science, Embase, CINAHL, APA PsycInfo, Cochrane Library ou BVS/LILACS. Usa o modelo de triagem configurado em **IA** e respeita o "só IA local" e o orçamento do projeto. A tradução é um rascunho: confira os termos e o número de resultados antes de usar.

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
