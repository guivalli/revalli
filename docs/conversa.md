# Conversa com os PDFs

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

Na aba **Conversa**, você faz perguntas sobre os estudos do projeto e recebe uma resposta construída só com o que os PDFs dizem. Cada afirmação aponta para um trecho e uma página, e cada citação é procurada no texto do PDF.

## Antes de usar

1. A IA precisa estar ligada no projeto (aba **IA**) e a administração precisa ter configurado um modelo de conversa em **Configuração da IA**. Se a tarefa **Conversa com os PDFs** ficar vazia, o ReValli usa o modelo da triagem.
2. Os PDFs precisam estar no projeto, com texto (PDFs escaneados ainda não têm OCR).
3. A liderança clica em **Indexar PDFs**. O texto de cada página é dividido em trechos de cerca de 1.100 caracteres, que nunca atravessam páginas. Se houver um modelo de **embeddings** configurado, cada trecho também recebe um vetor, e a busca passa a considerar o significado além das palavras. Indexar de novo só trata os PDFs novos.

## Perguntando

- **Onde procurar:** os estudos incluídos na fase de texto completo (com todos os relatórios de cada estudo) ou todos os PDFs do projeto.
- **É continuação da pergunta anterior:** usa a pergunta e a resposta anteriores como contexto, para perguntas como “e no grupo controle?”.
- O histórico é pessoal: cada pessoa vê só as próprias perguntas, e pode apagá-las.

## Como a resposta é montada

1. O modelo reescreve a pergunta como até 3 consultas curtas de palavras-chave (em inglês e, se for outro o idioma da pergunta, nele). Isso importa porque os artigos costumam estar em inglês e a pergunta, em português. Se essa chamada falhar, a pergunta original basta.
2. A pergunta e as consultas buscam os trechos mais parecidos: busca de texto do próprio Postgres (qualquer idioma) e, quando há embeddings, similaridade de vetores. As listas são combinadas por fusão de posições (RRF).
3. No máximo 8 trechos entram, com no máximo 3 por artigo e cerca de 9.000 caracteres, para um artigo não dominar a resposta.
4. O modelo recebe os trechos numerados e é instruído a usar só eles, citar `[n]` depois de cada afirmação e copiar uma frase literal de cada fonte. Se os trechos não respondem, ele deve dizer isso (a resposta fica marcada como “sem resposta nos trechos”).
5. Para cada citação, o ReValli procura a frase no texto do trecho. Com semelhança de 90 ou mais, a citação fica **conferida** (✓). Caso contrário, fica **não encontrada** (⚠). Marcadores `[n]` que apontam para fontes que não existem são removidos.
6. Todo número da resposta (exceto algarismos soltos) precisa aparecer nos trechos citados. Os que não aparecem são listados num aviso.
7. Se a resposta afirma algo e nenhuma citação for conferida, ela é marcada como não confiável.

Se nenhum trecho combina com a pergunta, o modelo nem é chamado para responder.

## O que foi verificado com um modelo real

Em 2026-10-11, com o Ollama (llama3.1 de 8 bilhões de parâmetros, e bge-m3 para os embeddings) e o texto completo de 3 artigos reais de acesso aberto sobre metformina no diabetes gestacional (os PDFs foram gerados a partir do texto completo obtido pela API do Europe PMC), 5 perguntas:

- As duas perguntas em inglês com números (535 randomizadas, 268 e 267 por grupo; 110 e 107 no ensaio original, 109 e 107 na análise secundária) saíram corretas, com citação conferida.
- Uma pergunta em português sobre um corpus em inglês só foi respondida corretamente com os embeddings (bge-m3); só com busca de texto, o modelo respondeu outra coisa (“98%”), a partir de um trecho que realmente existe no PDF. É o limite descrito abaixo: a citação existe, mas não responde à pergunta.
- Uma pergunta sem resposta nos PDFs foi recusada (“sem resposta nos trechos”).

É uma amostra pequena, de um único modelo, e não mede nada de forma estatística. Em geral, **ligue os embeddings** quando o corpus e as perguntas estiverem em idiomas diferentes.

## Limites que importam

- A conferência mostra que a frase **existe** no PDF, não que ela **sustenta** a afirmação. Abra o PDF pelo marcador `[n]` e leia o contexto.
- Modelos pequenos erram mais, principalmente ao somar ou comparar números de vários estudos. Use a conversa para localizar informação, e a aba **Extração** (com dupla extração) para dados que entram na análise.
- Os trechos dos PDFs são enviados ao modelo configurado. Com um provedor remoto, isso é o texto dos artigos saindo do servidor; use **só local** no projeto se isso for um problema.
- As chamadas contam no orçamento do projeto e aparecem no registro de uso da IA como “Conversa com os PDFs”.
- A recuperação carrega os vetores do escopo na memória a cada pergunta: serve bem para centenas de artigos, não para dezenas de milhares.

## API

Todas as rotas ficam em `/api/projects/{id}/corpus`.

| Rota | O que faz |
|---|---|
| `GET /status` | trechos indexados, PDFs pendentes, vetores e modelos |
| `POST /index` | cria o trabalho de indexação (liderança) |
| `POST /ask` | `{question, scope, follow_up}`, devolve a resposta e as fontes |
| `GET /messages` | histórico de quem pergunta |
| `DELETE /messages/{id}` | apaga uma pergunta do próprio histórico |
