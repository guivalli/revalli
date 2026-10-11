# Síntese qualitativa e checklists de relato

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

## Codificação qualitativa

A aba **Síntese** serve para revisões integrativas, de escopo e qualitativas. Ela trabalha com os estudos incluídos na fase de texto completo. Relatórios do mesmo estudo contam como um só.

**Códigos.** Crie temas e subtemas em árvore. Quem tem papel de líder, revisor ou extrator pode criar e renomear códigos. Só a liderança apaga ou mescla.
- Apagar um código apaga também os subcódigos. Trechos que ficarem sem nenhum código também são apagados.
- Mesclar um código em outro leva os trechos e os subcódigos para o destino.

**Trechos.** Em **Codificar**, o PDF do estudo abre ao lado.
1. Selecione um trecho com o mouse. O texto e a página entram no formulário.
2. Escolha um ou mais códigos.
3. Clique em **Marcar com os códigos escolhidos**.

Também dá para digitar ou colar um trecho, por exemplo de um estudo sem PDF. **Ver no PDF** destaca o trecho no documento. Cada pessoa pode alterar os próprios trechos; a liderança pode alterar todos.

**Matriz.** Mostra quantos trechos de cada estudo têm cada código, somando os subcódigos. Clique numa célula para ler os trechos.

**Exportação.** **Baixar trechos (CSV)** traz uma linha por trecho e código, com:
- o caminho do código (ex.: `Barreiras > Custo`);
- o estudo e a página;
- o texto e a nota;
- quem codificou.

## Checklists de relato

A aba **Relatório** traz o PRISMA 2020 e o PRISMA-ScR. Revisões de escopo abrem no PRISMA-ScR.

Para cada item, a liderança marca **Atendido** ou **Não se aplica** e registra onde ele está no manuscrito. Quando o ReValli tem dados do projeto, eles aparecem abaixo do item para ajudar a escrever:
- bases e datas das buscas, e quantas têm a estratégia registrada;
- número de revisores, cegamento e uso de IA;
- formulários de extração e de risco de viés;
- números do fluxograma;
- códigos da síntese.

O checklist preenchido pode ser baixado em CSV para enviar com o manuscrito.

Os textos dos itens estão resumidos. Confira sempre a versão oficial de cada checklist.

## Meta-análise

Em **Síntese → Meta-análise**, a liderança cria uma ou mais análises; as demais pessoas veem os resultados.

**Dados.** Escolha a medida e preencha uma linha por estudo:
- **RR, OR e RD**: eventos e total de cada grupo. Um grupo com zero eventos recebe correção de 0,5; estudos sem eventos nos dois grupos ficam de fora.
- **MD e SMD**: n, média e desvio padrão de cada grupo. A SMD é o g de Hedges.
- **HR**: o hazard ratio e o IC 95% relatados.
- **Genérica**: o efeito (na escala log, se for razão) e o erro padrão.

**Adicionar estudos incluídos** cria uma linha por estudo incluído. **Colar de uma planilha** aceita linhas separadas por tabulação. A coluna **Subgrupo** é opcional.

**Cálculo.** Feito no servidor, por variância inversa. O modelo de efeitos aleatórios usa DerSimonian-Laird e mostra τ², I², Q e o intervalo de predição. Com subgrupos, aparecem os subtotais e o teste de diferença entre eles. Os números foram conferidos com um conjunto de dados clássico da literatura (vacina BCG).

**Gráficos.** O forest plot e o gráfico de funil podem ser baixados em SVG ou PNG; os dados calculados, em CSV. O teste de Egger aparece a partir de 3 estudos, com aviso quando há menos de 10.

## GRADE e sumário de achados

Em **Síntese → GRADE**, cada linha é um desfecho:
1. Ligue o desfecho a uma meta-análise (opcional) e clique em **Preencher** para trazer o efeito, o número de estudos e de participantes.
2. Escolha o desenho: ensaios randomizados começam com certeza alta; estudos observacionais, baixa.
3. Para cada domínio, rebaixe ou eleve e escreva a justificativa.

O ReValli sugere justificativas a partir da meta-análise ligada: I² alto, IC que cruza a linha de nenhum efeito, menos de 400 participantes, menos de 10 estudos ou teste de Egger com p < 0,10. As sugestões são só pontos de partida; a decisão é da equipe.

A tabela de sumário de achados mostra a certeza com os símbolos ⊕ e pode ser baixada em CSV.

## Mapa de lacunas de evidência

Na aba **Síntese**, em **Lacunas de evidência**, você cruza duas dimensões dos estudos incluídos (por exemplo, intervenção × desfecho) e vê onde há evidência e onde não há.

- **Dimensões.** Os subcódigos de um código da árvore qualitativa (um estudo está na categoria se algum trecho dele, ou de um subcódigo mais fundo, tem aquele código) ou as opções de um campo de **escolha** ou **múltipla escolha** de um formulário de extração (vale o valor final: consenso, ou o acordo entre extratores).
- **Células.** O número de estudos que estão nas duas categorias; clique para ver quais. Células vazias aparecem tracejadas: são as lacunas.
- **Sem classificação.** Estudos sem categoria numa dimensão ficam numa linha ou coluna própria, para que nada desapareça do mapa.
- Um estudo com vários relatórios conta uma vez. Um estudo pode estar em várias categorias; por isso a soma de uma linha pode passar do total de estudos.
- **CSV.** A exportação traz todas as combinações, inclusive as de zero estudos.

O mapa é calculado na hora, a partir do que está registrado; ele não guarda configuração própria.
