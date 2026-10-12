# Texto completo: PDFs, busca automática e lista de pendentes

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

Na aba **Triagem**, na fase de texto completo, o cartão **PDFs** reúne tudo o que se refere aos arquivos.

## 1. Enviar PDFs

- **Um a um:** na tela de triagem, em cada referência.
- **Em lote (ZIP):** os arquivos são ligados às referências pelo DOI (no texto do PDF ou no nome do arquivo) ou pelo título. O que não casou aparece numa lista para você resolver.

## 2. Buscar PDFs de acesso aberto

O botão **Buscar PDFs de acesso aberto** (só líderes) procura versões gratuitas das referências do texto completo que ainda não têm PDF. Para cada uma, a ordem é:

1. **OpenAlex**, em lotes, por DOI.
2. **Unpaywall**, por DOI. Pede um e-mail de contato: defina `ENRICHMENT_CONTACT_EMAIL` no `deploy/.env`. Sem ele, o Unpaywall é pulado e o resultado avisa.
3. **Europe PMC**, por PMID ou DOI (PubMed Central e preprints).
4. **Página do artigo**, pelo link do registro (o campo `UR` das exportações da BVS, por exemplo), pelo DOI ou por páginas que as fontes anteriores indicaram. O ReValli lê as marcas `citation_pdf_url` e `link rel="alternate"` que SciELO, PePSIC, revistas OJS e a maioria das editoras publicam.

As páginas conhecidas pelo OpenAlex (por exemplo, a do SciELO) também entram como candidatas na etapa 4, mesmo quando o DOI não resolve. Páginas do próprio OpenAlex ficam de fora, porque não são o artigo.

O primeiro PDF válido vale. Todo download passa pela mesma proteção: não alcança a rede interna, tem limite de tamanho e confere que o arquivo é um PDF. Se uma fonte bloquear, o ReValli não tenta contornar: o registro segue para a lista de pendentes.

A busca trata 4 registros ao mesmo tempo e grava o andamento a cada um. Páginas de revista que não respondem em 20 segundos são abandonadas, e, se um endereço do servidor não conecta (comum com IPv6 dentro de contêiner), o próximo é tentado. Servidores que respondem 403 (bloqueio anti-robô, como o do PePSIC pela BVS) caem na lista de pendentes.

O resultado mostra quantas foram verificadas, quantas tinham versão aberta, quantas foram baixadas e **quantas vieram de cada fonte**. Um registro sem DOI também é tentado, se tiver PMID ou link.

## 3. Lista de pendentes (baixar à mão)

O que nenhuma fonte achou fica em **Sem PDF (N)**, com título, ano, **DOI** e o **link** do artigo (`https://doi.org/...`, ou o link do registro quando não há DOI). Você pode:

- abrir cada link e baixar o PDF;
- **Baixar a lista (CSV)**: título, autores, ano, revista, DOI, PMID e link;
- **Copiar DOI e link** para colar numa planilha.

Depois, envie os PDFs pelo ZIP: eles são ligados às referências pelo DOI.
