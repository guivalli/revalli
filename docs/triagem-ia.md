# Critérios, triagem e etiquetas com IA

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

A IA é um apoio: ela sugere, você decide. Tudo isto exige um provedor e um modelo de triagem configurados em **IA** (menu superior) e a IA ligada no projeto (aba **IA**).

## 1. Critérios detalhados

Na aba **Protocolo**, depois de escrever e salvar os critérios de inclusão e exclusão:

1. **Organizar com IA** lê o texto salvo, o título e a descrição do projeto. Ela separa os critérios em itens (uma condição cada), escreve uma definição aplicável a título e resumo, dá exemplos e casos limítrofes e lista as **dúvidas** que encontrou.
2. Responda às dúvidas no campo de respostas e use **Reorganizar com as respostas**.
3. Edite os itens à mão (nome, tipo, definição, exemplos), adicione ou remova.
4. **Aprovar e salvar critérios detalhados**. Só então a triagem passa a usar a lista, no lugar do texto livre.

Nada é salvo antes do passo 4. **Voltar a usar só o texto livre** apaga a lista detalhada.

- **Colocar no texto principal** escreve os itens nos campos de inclusão e exclusão (um por linha, com a definição) e salva a lista detalhada junto. Pede confirmação porque substitui o texto atual.
- **Sem texto nenhum**, a IA propõe um rascunho de critérios a partir do título e da descrição do projeto, com perguntas sobre o que não dá para deduzir. Trate o rascunho como ponto de partida: no teste real ela inventou um período (a partir de 2010) que ninguém pediu.

Mudar os critérios muda o prompt, então as sugestões antigas deixam de valer (o cache é por prompt) e a IA analisa de novo os registros na próxima rodada. Com modelo remoto isso tem custo; a estimativa avisa antes.

## 2. Triar com IA

Na aba **Triagem**, o cartão **Triagem com IA** roda a IA sobre os registros ainda sem decisão da fase aberta. Se o projeto não tem critérios (nem texto, nem lista detalhada), a IA não roda: o cartão avisa e leva você ao **Protocolo**.

Quando roda:

- Com modelo local, ou sem custo, começa direto.
- Com custo, mostra a estimativa e pede confirmação.
- Se a IA estiver desligada no projeto, o cartão oferece ligá-la.

Cada sugestão traz a decisão (incluir, excluir, talvez), a confiança, **o motivo em uma ou duas frases**, o estado de cada critério (✓ atendido, ✗ violado, ? incerto) e até 4 etiquetas.

### Só em título e resumo

A triagem por IA vale **apenas na fase Título e resumo**. O modelo recebe título, ano, revista, palavras-chave e resumo; ele **não lê o PDF**. Por isso a aba **Texto completo** não oferece o botão (e a API recusa com `ai_phase_not_supported`): rodar a IA ali repetiria o resultado do resumo e daria a falsa impressão de que o artigo foi lido. No texto completo, a decisão é sua, com o PDF e o visualizador.

### Parar, continuar e refazer

- **Parar:** enquanto a triagem roda, o botão **Parar** (no cartão e no aviso de andamento no topo do projeto) interrompe a IA no próximo registro. Tudo o que ela já analisou fica salvo.
- **Continuar de onde parou:** analisa só os registros que faltam; os já analisados vêm do cache, sem custo.
- **Refazer tudo:** analisa todos de novo e **substitui** as respostas guardadas. Com modelo remoto, tem custo (a estimativa mostra antes). Útil depois de mudar os critérios ou as instruções.

Só líderes podem parar.

### Ver a sugestão antes ou depois de decidir

- **Por projeto** (aba **IA**, líder): revisores veem a sugestão só depois de decidir (padrão, evita ancoragem) ou antes. Líderes e árbitros sempre a veem.
- **Por pessoa**, na sessão de triagem: a caixa **Mostrar a sugestão da IA antes de eu decidir** vale só para você e fica guardada no navegador. Sem escolha sua, vale o padrão do projeto.

Para um revisor, a opção do projeto é o que a API entrega; a caixa da sessão só esconde ou mostra o que já chegou.

## 3. Motivos de exclusão

Quando a IA exclui um registro, ela também diz o motivo principal em poucas palavras (desligue em **IA → Sugerir o motivo de exclusão**).

**Na sessão de triagem**, ao clicar em **Excluir** com a sugestão visível:

- Se o motivo sugerido já existe no protocolo, **Usar este motivo** o marca.
- Se não existe, o líder vê o texto num campo que pode **editar** e clicar em **Criar e usar**: o motivo entra no protocolo e já fica marcado. O mesmo campo, vazio, serve para criar qualquer motivo novo na hora.
- Revisores que não são líderes veem a sugestão e usam só os motivos que já existem.

**Agrupar:** em **Protocolo**, **Agrupar motivos sugeridos** junta os motivos parecidos em poucos grupos, reaproveitando os que você já tem. Revise, renomeie, desmarque o que não quiser e use **Aplicar selecionados**: os motivos são criados no protocolo e as sugestões antigas passam a apontar para eles. Na mesma tela, **Editar** renomeia um motivo existente.

## 4. Etiquetas

Na aba **Protocolo**, o cartão **Etiquetas do projeto** guarda o vocabulário do projeto (nome e descrição de quando usar):

- Escreva as suas.
- **Sugerir etiquetas com IA** lê uma amostra de até 40 registros e propõe 6 a 15 etiquetas, sem repetir as suas. Se uma etiqueta sua não tem descrição, a IA pode propor uma. Marque as que quer e use **Adicionar selecionadas**, depois **Salvar etiquetas**.

Na triagem, a IA escolhe até 4 etiquetas por registro, de preferência do vocabulário (pode propor 1 nova, mostrada com borda tracejada). Na sessão, clique numa etiqueta sugerida para aplicá-la à sua decisão, ou **Aplicar todas**. As etiquetas do vocabulário também aparecem como sugestão ao digitar. Desligue em **IA → Sugerir etiquetas** se não quiser.

## 5. Editar e excluir o projeto

A aba **Configurações** (só líderes) altera título, descrição e tipo da revisão. A zona de perigo exclui o projeto: apaga referências, PDFs, decisões, extrações e tudo o mais, sem volta, e exige digitar o nome do projeto.

## Limites que medimos

Teste real com o Ollama (qwen2.5:14b) em 8 registros sintéticos sobre exercício e ansiedade, em duas rodadas:

- Os critérios saíram em 7 itens com definição, exemplos e 3 dúvidas relevantes (idade mínima, tipos de exercício, definição de ansiedade), em cerca de 20 s.
- O vocabulário veio com 14 etiquetas em palavras comuns. A primeira rodada devolveu nomes tipo `design_randomizado`; o prompt foi ajustado e a segunda saiu com nomes naturais.
- Os motivos de exclusão vieram em frases curtas e o agrupamento funcionou e aplicou 6 motivos no protocolo, mas com só 6 motivos diferentes (cada um em 1 registro) não houve o que juntar: a qualidade do agrupamento em volume real não foi medida. Uma rodada devolveu um motivo em inglês (copiado de um exemplo do prompt, já corrigido).
- A triagem das 8 levou de 45 a 100 s conforme a rodada. Seis decisões estavam certas; o ensaio de yoga em universitários foi excluído (na primeira rodada por "não são adultos", o que está errado; na segunda por "yoga não é exercício físico", que é discutível) e a meta-análise de treinamento resistido ficou em "talvez".

A IA erra e varia entre rodadas, por isso o motivo aparece junto e a **calibração** (aba **IA**) mede a concordância com as suas decisões. A amostra é pequena e inventada: não é uma medida de qualidade.
