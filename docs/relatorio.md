# Relatório da revisão em DOCX ou PDF

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

Na aba **Relatório**, o cartão **Relatório da revisão (DOCX ou PDF)** gera um rascunho a partir dos dados do projeto. Qualquer membro pode gerar. Escolha:
- o formato: Word (DOCX), para continuar escrevendo, ou PDF;
- o idioma: português ou inglês;
- as partes que entram.

## O que entra

**Métodos.** Critérios de elegibilidade, fontes e datas das buscas, como foi a triagem (revisores por fase, cegamento) e a concordância entre revisores (kappa médio por fase). Também entram o uso de IA, os formulários de extração e de risco de viés, e os métodos de síntese (meta-análise, GRADE, codificação qualitativa), conforme o que o projeto usou.

**Resultados.**
- Números da seleção, com o fluxograma PRISMA e os motivos de exclusão no texto completo.
- Tabela dos estudos incluídos.
- Julgamentos de risco de viés de cada formulário.
- Para cada meta-análise: forest plot, estimativa, heterogeneidade, intervalo de predição, teste de subgrupos e teste de Egger (com 10 estudos ou mais).
- Tabela GRADE de sumário de achados.
- Tabela de códigos, com o número de estudos e de trechos.

**Apêndices.**
- A: estratégia completa de cada busca, com data, origem (arquivo ou API) e número de registros.
- B: registro de uso da IA: configuração, chamadas por tarefa e modelo (tokens e custo) e desempenho da IA frente à decisão humana final.
- C: checklist PRISMA 2020 (ou PRISMA-ScR, em revisões de escopo) com a situação e o local de cada item.

## Como funciona

As figuras (fluxograma e forest plots) são desenhadas pela interface, no idioma escolhido, e enviadas em PNG junto com o pedido. O servidor monta o texto e gera o arquivo; nada fica salvo. Pela API, o mesmo relatório sai de `POST /api/projects/{id}/report/document` (sem figuras, se elas não forem enviadas).

O texto é um ponto de partida: ele descreve o que está registrado no ReValli, não o que a equipe decidiu fora dele. Leia e ajuste tudo antes de usar.
