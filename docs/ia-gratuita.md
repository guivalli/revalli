# IA com faixas gratuitas de provedores online

> O ReValli é um projeto vibecodado. Os limites abaixo vêm de fontes de terceiros e mudam com frequência: **confira no painel de cada provedor** antes de depender deles.

Serve para quando o computador com GPU está desligado ou não existe. A triagem por título e resumo gasta pouco: cerca de 700 tokens por registro.

## Qual escolher

| Provedor | Modelo para começar | Limite gratuito aproximado | Pontos de atenção |
|---|---|---|---|
| **Google Gemini** | `gemini-2.5-flash-lite` (ou o Flash-Lite mais novo da lista) | ~15 pedidos/min e ~1.000/dia, por projeto Google | Melhor qualidade na faixa gratuita. No plano gratuito os dados podem ser usados para melhorar os modelos. Tem endpoint compatível com OpenAI. |
| **Groq** | `llama-3.1-8b-instant` | 30 pedidos/min, 14.400/dia, 6.000 tokens/min, 500.000 tokens/dia | Muito rápido. O teto de tokens por dia limita a cerca de 700 registros por dia. Não tem embeddings. |
| **Mistral** | `mistral-small-latest` | ~1 pedido/s e até ~1 bilhão de tokens/mês | Mais volume. O plano gratuito (Experiment) pode usar as requisições para treinar modelos. Pede telefone verificado. |
| **OpenRouter** | modelos terminados em `:free` | ~20 pedidos/min e poucas dezenas por dia sem crédito | Bom para testar; a cota diária é pequena. |

Para **embeddings** (busca do chat com os PDFs e aprendizado ativo), o mais simples é continuar com o `bge-m3` no Ollama do seu computador. Nenhum dos provedores acima precisa servir embeddings.

## Como configurar

1. Crie uma chave de API no site do provedor (todos têm cadastro gratuito).
2. No ReValli: menu **IA** → **Adicionar provedor**. Escolha o tipo (Google, Groq, Mistral ou OpenRouter): o endereço vem preenchido.
3. Cole a chave. Confira o **limite de pedidos por minuto**: já vem um valor conservador, mas ajuste ao que o painel do provedor mostrar.
4. Clique em **Testar** (lista os modelos) e escolha o modelo da tarefa **Triagem** em **Modelos por tarefa**.
5. Em cada projeto, aba **IA**, **desligue "só local"** se estiver ligado. Com ele ligado, o projeto só aceita provedores locais.

## O que o ReValli faz por você

- **Espaça os pedidos** para não passar do limite por minuto configurado.
- **Espera e tenta de novo** quando o provedor responde "muitos pedidos" (respeita o tempo que ele indicar).
- **Para com calma** quando a cota do dia acaba: o que já foi analisado fica salvo, a tela mostra o aviso e **Continuar** retoma no dia seguinte.
- **Cai para sem modo JSON** se o modelo não aceitar essa opção.

## Cuidados com os dados

- No plano gratuito, assuma que o que você envia **pode ser usado para treinar modelos**. Use só com títulos e resumos de artigos já publicados.
- Não envie material inédito, dados de pacientes nem texto completo de PDFs sob acordo de sigilo. A triagem por IA no ReValli usa só título e resumo, mas a extração e o chat leem o PDF.
- Para material sensível, use o Ollama local (projeto "só local").

## Qualidade

Modelos pequenos erram mais. No benchmark do projeto, um modelo de 8 bilhões de parâmetros ficou com 93% de sensibilidade e 29% de especificidade num conjunto. Use a IA como **sugestão** ou **segunda opinião**, não como substituta da triagem humana, e meça a calibração (aba IA) antes de confiar.
