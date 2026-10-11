# Atualizações automáticas (revisões vivas)

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

Na aba **Importar**, o cartão **Atualizações automáticas** repete uma busca, ou relê um arquivo numa URL, no intervalo que você escolher, e importa só o que o projeto ainda não tem. Serve a revisões vivas e a quem mantém uma biblioteca de referências fora do ReValli.

## Dois tipos

- **Busca numa base** (PubMed, OpenAlex ou Europe PMC): a mesma estratégia da busca direta, rodada de novo.
- **Arquivo numa URL**: um arquivo de referências (RIS, BibTeX, CSL JSON, CSV, MEDLINE ou XML do PubMed) servido por qualquer endereço `http` ou `https`. Um gerenciador de referências que publique a coleção como arquivo, ou outro ReValli (use uma [chave de API](api.md) e a rota `/export?format=ris`), pode ser a origem. Um cabeçalho de autorização opcional (por exemplo, `Bearer ...`) é guardado cifrado.

## O que acontece em cada rodada

1. A busca roda inteira, ou o arquivo é baixado e lido.
2. Cada registro é comparado com o que o projeto já tem, por DOI, PMID e título normalizado. Só os desconhecidos entram.
3. Se houver novos, eles viram uma busca “(atualização)”, com data, estratégia e contagem, para o PRISMA-S e para o fluxograma PRISMA. A deduplicação roda em seguida.
4. Os registros novos entram na triagem, e a visão geral do projeto avisa quantos chegaram.

Se a rodada falhar (base fora do ar, URL inválida, arquivo em formato desconhecido), o erro aparece no cartão e a nova tentativa ocorre em um dia.

## Funcionamento

- O agendador (`scheduler` no Docker Compose, processo `celery beat`) acorda a cada 15 minutos e cria um trabalho para cada atualização vencida. **Deve existir uma única cópia dele.**
- “Rodar agora” executa na hora, sem mudar a frequência.
- Pausar uma atualização a mantém na lista, sem rodar.
- Só a liderança cria, edita e apaga; qualquer membro vê o estado.

## Segurança das URLs

O servidor baixa o endereço que a pessoa digita, então ele se protege de ser usado para alcançar a rede interna:

- o nome é resolvido e o endereço é conferido: recusa loopback, redes privadas, link-local (inclui o endereço de metadados de nuvem), nomes sem ponto (como `db`) e `.local`/`.internal`;
- a conexão vai para o IP conferido (com o nome original no `Host` e no SNI), o que impede a troca de DNS entre a conferência e a conexão;
- cada redirecionamento passa pela mesma conferência, e a credencial só segue para o servidor original;
- tamanho máximo de 100 MB.

Em uma instalação doméstica em que a fonte está na própria rede local, `FEED_ALLOW_PRIVATE=true` desliga a recusa de endereços internos. Ligue só se confiar em quem lidera os projetos.

## Limites

- A busca roda inteira a cada vez (até `API_SEARCH_MAX` registros) e o filtro do que é novo é feito depois. Isso é simples e robusto, mas gasta mais chamadas à base do que uma consulta por data.
- Registros que mudaram de metadados na origem não são atualizados no projeto.
- Os avisos ficam na interface; não há envio de e-mail.
