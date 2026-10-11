# Extração de dados e risco de viés

> Este projeto é vibecodado: o código foi escrito com auxílio intensivo de IA. Confira os resultados antes de usá-los num artigo.

## Como funciona

1. Na aba **Extração** do projeto, um líder cria um formulário em branco ou a partir de um modelo:
   - **Características dos estudos**: país, delineamento, participantes, intervenções, desfechos e uma tabela de resultados por grupo.
   - **RoB 2**: risco de viés de ensaios randomizados (efeito da atribuição à intervenção). As perguntas sinalizadoras aparecem conforme as respostas anteriores, e o julgamento de cada domínio e o geral são calculados pelo algoritmo do instrumento. A pessoa pode trocar o julgamento calculado.
   - **ROBINS-I**: julgamento por domínio para estudos não randomizados; o julgamento geral segue a regra do instrumento (o pior domínio).
2. Os estudos a extrair são os incluídos na triagem de texto completo. Relatórios agrupados como o mesmo estudo contam uma vez.
3. Cada formulário define quantas pessoas extraem cada estudo de forma independente. Ninguém vê a extração dos outros antes de concluir a sua. Líderes e árbitros veem tudo.
4. Na aba **Comparar e consenso**, as respostas aparecem lado a lado, com as divergências destacadas. Líderes e árbitros montam o consenso campo a campo.
5. A exportação em CSV usa o consenso; sem consenso, usa os valores em que as pessoas concordaram.

As perguntas dos modelos de risco de viés são paráfrases em português, não o texto oficial. Consulte sempre a orientação oficial de cada instrumento:

- RoB 2: Sterne JAC et al. *BMJ* 2019;366:l4898.
- ROBINS-I: Sterne JAC et al. *BMJ* 2016;355:i4919.

## Formulários

Tipos de campo: texto curto, texto longo, número, número inteiro, escolha única, múltipla escolha, sim ou não e tabela (com colunas próprias e, se quiser, linhas fixas como os grupos do estudo). Cada campo tem um identificador estável, que vira o nome da coluna na exportação.

Alterar os campos cria uma versão nova do formulário. Os dados já extraídos ficam ligados aos identificadores dos campos, então mudar o texto ou a ordem não perde nada.

## Extração por IA

Marque nos campos a opção **A IA pode preencher**. Com a IA ligada no projeto e um modelo escolhido para **Extração de dados** em **IA**, o botão **Extrair com IA** roda a extração em todos os estudos que têm PDF com texto.

Para cada campo, o modelo devolve o valor e um trecho copiado do artigo. O ReValli procura esse trecho no texto das páginas:

- **Trecho conferido no PDF**: o trecho foi encontrado (semelhança de 90% ou mais). **Ver no PDF** abre a página e destaca o trecho.
- **Trecho não encontrado**: o modelo pode ter inventado ou parafraseado. Confira antes de usar.

A extração da IA aparece como sugestão ao lado de cada campo e como mais uma coluna na comparação, mas não conta na concordância entre as pessoas.

## Exportação

- **CSV com uma linha por estudo**: uma coluna por campo; tabelas viram uma coluna por coluna da tabela, com os valores das linhas separados por ponto e vírgula.
- **CSV longo**: uma linha por valor (`estudo, campo, linha, coluna, valor`), prático para R e para montar a planilha de uma meta-análise.

A coluna `status` diz de onde veio cada linha: `consensus`, `agreed`, `single` (só uma extração) ou `conflict` (há divergências sem consenso; só os campos em acordo vêm preenchidos).
