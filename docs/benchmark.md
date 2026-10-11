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

No modo segunda revisora, a IA deve atingir sensibilidade de pelo menos 95% num conjunto do SYNERGY com o modelo escolhido. Esse número ainda não foi medido com um modelo real: o ambiente em que o ReValli foi desenvolvido não tem GPU nem acesso aos dados. Rode o benchmark no seu servidor e registre o resultado aqui.
