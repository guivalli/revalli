# Benchmark da IA

> O ReValli é um projeto vibecodado (escrito com auxílio intensivo de IA). Meça antes de confiar.

O script `revalli.benchmark` mede a IA sobre um conjunto de referências que já tem a resposta certa (quais foram incluídas numa revisão publicada). Ele não precisa do banco nem da interface.

## O que ele mede

- **Aprendizado ativo.** Simula a triagem na ordem que o modelo sugere, começando com um incluído e um excluído sorteados, e retreinando a cada lote. Mostra quantos registros foi preciso ler para achar 95% dos incluídos, o trabalho economizado em relação à leitura em ordem aleatória (WSS@95) e onde a regra de parada (N exclusões seguidas) teria parado, com o recall naquele ponto.
- **Triagem por IA (opcional).** Pergunta ao modelo de chat sobre cada registro de uma amostra, usando o mesmo prompt do ReValli, e compara com os rótulos: sensibilidade e especificidade. “Talvez” conta como inclusão.

## Dados

Um CSV com as colunas `title`, `abstract` e `label_included` (1 ou 0). Os conjuntos do SYNERGY ([doi:10.34894/HE6NAQ](https://doi.org/10.34894/HE6NAQ)), 26 revisões sistemáticas com os rótulos de inclusão, servem bem; gere os CSVs com títulos e resumos seguindo as instruções que acompanham o conjunto.

## Como rodar

Dentro do container da API (ou num ambiente com o backend instalado):

```bash
# Só o aprendizado ativo, com vetores de termos (sem modelo, roda em qualquer máquina)
python -m revalli.benchmark dados.csv --embedder hashing

# Aprendizado ativo com o modelo de embeddings do Ollama
python -m revalli.benchmark dados.csv --embedder api \
  --base-url http://ollama:11434/v1 --embed-model bge-m3

# Também a triagem por IA, numa amostra de 300 registros
python -m revalli.benchmark dados.csv --screen --criteria criterios.txt --limit 300 \
  --base-url http://ollama:11434/v1 --model qwen3:8b --out relatorio.md
```

Para APIs remotas, passe a chave em `--api-key` ou na variável `REVALLI_AI_API_KEY`. A triagem por IA de um conjunto inteiro pode custar caro numa API paga: comece com `--limit`.

## No CI

Os testes rodam uma versão reduzida da simulação sobre dados sintéticos (`tests/test_benchmark.py`), sem rede e sem modelo, para garantir que o código continua funcionando. O benchmark completo, com modelos reais, roda sob demanda.

## Meta do marco M3

No modo segunda revisora, a IA deve atingir sensibilidade de pelo menos 95% num conjunto do SYNERGY com o modelo escolhido.

## Resultado medido (2026-10-11)

Um conjunto só, um modelo só: serve para calibrar expectativa, não para concluir. Conjunto **Donners_2021** do SYNERGY+ (revisão sistemática sobre a farmacocinética do emicizumabe), com os critérios de elegibilidade publicados da própria revisão: 260 registros, 15 incluídos (5,8%), mas só 93 com resumo (os demais têm apenas o título). Máquina: RTX 2080 Ti, Ollama, `llama3.1` de 8 bilhões de parâmetros para a triagem e `bge-m3` para os embeddings.

**Aprendizado ativo** (5 execuções, parada após 30 exclusões seguidas):

| Vetores | Lidos para 95% de recall | WSS@95 | Recall quando a regra manda parar |
|---|---|---|---|
| termos (hashing) | 90 a 99 de 260 (35 a 38%) | 0,57 a 0,60 | 100% (parou com 46 a 50% lidos) |
| `bge-m3` | 45 a 56 de 260 (17 a 22%) | 0,74 a 0,78 | 100% (parou com 29 a 33% lidos) |

**Triagem por IA** ("talvez" conta como inclusão):

| | Incluídos (15) | Excluídos (245) |
|---|---|---|
| IA diz incluir | 13 | 35 |
| IA diz talvez | 1 | 139 |
| IA diz excluir | 1 | 71 |

- Sensibilidade 93,3% (14 de 15; intervalo de 95% de cerca de 70% a 99%), **abaixo da meta de 95%**, e especificidade 28,6%.
- Quase todos os falsos positivos são “talvez” (139 de 174). O prompt manda priorizar o recall e responder “talvez” quando o registro não dá informação para excluir, e 167 dos 260 registros não têm resumo. Tratando “talvez” como exclusão, a sensibilidade cai para 86,7% e a especificidade sobe para 85,7%: a IA serve para ordenar e para pegar o que o humano deixou passar, não para decidir sozinha.
- O único incluído que a IA excluiu (com confiança 1,0) usa o nome de desenvolvimento do medicamento (ACE910) em vez de “emicizumab”, que é o termo dos critérios. Um modelo pequeno não sabe que são o mesmo. Escrever os sinônimos nos critérios (ou em “instruções extras”) resolve esse tipo de falha.

Para decidir se um modelo serve, repita o benchmark com mais de um conjunto e com os critérios e sinônimos da sua revisão.
