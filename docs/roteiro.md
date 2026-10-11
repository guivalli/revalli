# Roteiro

Cada marco termina com uma versão utilizável.

| Marco | Conteúdo | Estado |
|---|---|---|
| M0 | Fundação: Docker, login, projetos, membros, convites, CI | pronto |
| M1 | Importação (RIS, BibTeX, PubMed, CSV), registro de buscas, enriquecimento de metadados, deduplicação | pronto |
| M2 | Triagem cega pelo teclado, destaque de palavras-chave, etiquetas, filtros, conflitos, concordância, PRISMA 2020, exportação | pronto |
| M3 | IA plugável (local ou remota), triagem assistida, calibração, controle de custo, aprendizado ativo e critério de parada | pronto (falta medir a meta de recall com um modelo real, veja [benchmark](benchmark.md)) |
| M4 | Texto completo: PDFs, busca de acesso aberto, visualizador, agrupamento de relatórios por estudo | pronto (sem OCR de PDFs escaneados) |
| M5 | Extração de dados e risco de viés, com citação literal verificada no PDF | pronto (falta medir a IA com estudos reais) |
| M6 | Síntese, snowballing, buscas por API, relatórios, conversa com o corpus, API pública e servidor MCP | pronto (buscas por API, snowballing, codificação qualitativa, checklists PRISMA, meta-análise, GRADE, relatório em DOCX/PDF e conversa com os PDFs com citações verificadas, API pública somente leitura, servidor MCP, atualizações automáticas (revisões vivas e sincronização por arquivo de referências) login único (OpenID Connect) e mapa de lacunas de evidência; o login único foi verificado contra um Keycloak real; falta verificar o fluxo completo com PDFs de editoras) |
