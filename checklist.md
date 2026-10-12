# Checklist do que falta

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

Lista viva do que falta. O que cada marco já entrega está no [roteiro](docs/roteiro.md). Marque com `x` ao concluir.

## 1. Fechar o trabalho recente

- [ ] Fazer o commit das mudanças ainda soltas na branch `m6-buscas` (critérios detalhados, etiquetas, motivos de exclusão, assistente de busca, SciELO e PePSIC, parar e refazer, editar e excluir projeto).
- [ ] Ver no navegador as telas novas: aba Configurações, cartões do Protocolo, painel de sugestão na sessão de triagem, assistente em Importar, Parar/Continuar/Refazer. Hoje só passaram por tipos, build e testes de API.
- [ ] Testar Parar e Continuar com o worker real pelo navegador (os testes cobrem o mecanismo, não o clique).
- [x] Trocar a porta local de 8080 para 1515 (`HTTP_PORT` e `PUBLIC_URL` em `deploy/.env`).
- [x] Instalar o auxiliar do Ollama (`bash deploy/ollama-helper/install.sh`) e testar Ligar/Desligar na tela IA. Veja [docs/ollama.md](docs/ollama.md).
- [ ] Arquivar ou apagar o `HANDOFF.md`, que descreve outro ambiente.

## 2. Publicar

- [ ] Conferir a CI dos PRs abertos e decidir o rebase das branches de marco sobre a `main`.
- [ ] Enviar o trabalho recente para o GitHub (nada disso foi publicado).
- [ ] Revogar o token do GitHub colado numa sessão anterior.
- [ ] Trocar a chave do OpenAlex se não quiser mantê-la no histórico de conversa.

## 3. Verificar contra o mundo real

- [ ] Medir a triagem por IA com critérios detalhados: calibração em decisões humanas reais e o benchmark em mais conjuntos, com um modelo maior (o llama3.1 8B ficou com 93% de sensibilidade e 29% de especificidade num conjunto).
- [ ] Avaliar o agrupamento de motivos de exclusão com volume real (o teste teve 6 motivos distintos, nada para juntar).
- [ ] Testar o assistente de busca com um modelo maior: no teste local faltaram blocos de conceito e houve `[mh]` em termo truncado.
- [ ] Importar exportações reais de SciELO, PePSIC e Portal CAPES (RIS e CSV) e conferir o parser. LILACS/BVS em RIS já foi conferido com uma exportação real (22 registros) e gerou correções; veja [docs/buscas.md](docs/buscas.md).
- [ ] Testar um provedor de login único além do Keycloak.

## 4. Funcionalidades que faltam

- [ ] OCR de PDFs escaneados.
- [ ] Busca direta em LILACS/BVS (depende de uma chave da API da BVS) e no Portal CAPES (não tem API pública).
- [x] Campo na interface para a chave do OpenAlex (menu IA, cartão Chave do OpenAlex).
- [ ] Salvar a conversa do assistente de busca (hoje fica só na tela).
- [ ] Parar também embeddings, extração por IA e importações (só a triagem por IA para).
- [ ] Pendências do M3: Batch APIs, detecção de idioma e de tipo de estudo, tradução.

## 5. Antes de expor à internet

- [ ] Revisão de segurança dedicada.
- [ ] Verificar os modos de acesso (rede local, túnel, domínio público) de ponta a ponta.
- [ ] Snowballing e buscas grandes em escala, com os limites reais das bases.
- [ ] Conferir o parser de PDFs de editoras (a maioria bloqueia o download automático).
