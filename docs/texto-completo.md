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

O primeiro PDF válido vale. Todo download passa pela mesma proteção: não alcança a rede interna, tem limite de tamanho e confere que o arquivo é um PDF. Se uma fonte bloquear, o ReValli não tenta contornar: o registro segue para a lista de pendentes.

O resultado mostra quantas foram verificadas, quantas tinham versão aberta, quantas foram baixadas e **quantas vieram de cada fonte**. Um registro sem DOI também é tentado, se tiver PMID ou link.

## 3. Lista de pendentes (baixar à mão)

O que nenhuma fonte achou fica em **Sem PDF (N)**, com título, ano, **DOI** e o **link** do artigo (`https://doi.org/...`, ou o link do registro quando não há DOI). Você pode:

- abrir cada link e baixar o PDF;
- **Baixar a lista (CSV)**: título, autores, ano, revista, DOI, PMID, link e link pela instituição;
- **Copiar DOI e link** para colar numa planilha.

Depois, envie os PDFs pelo ZIP: eles são ligados às referências pelo DOI.

## 4. Acesso pela instituição (CAFe)

Muitos artigos que não são abertos estão disponíveis pela assinatura da sua instituição, via **Portal de Periódicos CAPES com login CAFe**.

**O que o ReValli faz:** guarda o modelo do link do proxy da instituição e, na lista de pendentes, mostra ao lado de cada artigo um segundo link, **Abrir pela instituição**. Você já está (ou entra) logado com a sua conta CAFe no navegador, baixa o PDF e envia.

**Configuração** (administrador): menu **IA**, cartão **Acesso pela instituição (CAFe)**. O modelo usa:

- `{url}`: o endereço inteiro do artigo;
- `{host}`: o servidor, no estilo do EZproxy (pontos viram hífens; hífens viram dois hífens);
- `{path}`: o resto do endereço.

Exemplos:

| Instituição | Modelo |
|---|---|
| Portal CAPES com CAFe | `https://{host}.ezl.periodicos.capes.gov.br{path}` |
| EZproxy por prefixo | `https://ezproxy.suainstituicao.br/login?url={url}` |

Confira o formato do seu caso: faça login no Portal de Periódicos CAPES pela CAFe, abra um artigo e compare o endereço com o modelo. Se o sufixo for diferente (`ezl`, `ez27`...), ajuste o modelo.

**O que o ReValli não faz, de propósito:**

- **Não faz login por você nem guarda a sua senha.** O CAFe usa uma federação com login interativo (SAML), ligada à sua sessão no navegador.
- **Não baixa em lote pelo proxy.** As editoras detectam downloads em sequência e podem bloquear o acesso de toda a instituição. Por isso o fluxo é você abrir e baixar, artigo a artigo.
