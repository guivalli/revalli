"""Textos do relatório em DOCX/PDF, em português e inglês."""

TEXTS: dict[str, dict[str, str]] = {
    "pt-BR": {
        "draft_note": (
            "Rascunho gerado automaticamente pelo ReValli em {date}. Revise todo o texto antes de usar. "
            "O ReValli é um projeto vibecodado (escrito com auxílio intensivo de IA)."
        ),
        "review_type_systematic": "Revisão sistemática",
        "review_type_scoping": "Revisão de escopo",
        "review_type_integrative": "Revisão integrativa",
        "review_type_other": "Revisão",
        "methods": "Métodos",
        "eligibility": "Critérios de elegibilidade",
        "inclusion": "Critérios de inclusão",
        "exclusion": "Critérios de exclusão",
        "no_criteria": "Os critérios de elegibilidade não foram registrados no ReValli.",
        "sources": "Fontes de informação e estratégia de busca",
        "sources_text": "Foram pesquisadas {n} fonte(s): {list}.",
        "sources_none": "Nenhuma busca foi registrada no ReValli.",
        "sources_api": "As buscas em {list} foram feitas diretamente pelas APIs das bases.",
        "citation_text": "Também foi feita busca de citações ({list}) a partir dos estudos incluídos.",
        "method_citation_backward": "referências dos estudos",
        "method_citation_forward": "estudos que os citam",
        "strategies_appendix": "As estratégias completas estão no Apêndice A.",
        "selection": "Processo de seleção",
        "selection_text": (
            "Títulos e resumos foram avaliados por {ta} revisor(es) independente(s) por registro e "
            "os textos completos por {ft}. {blind} Divergências foram resolvidas por discussão ou "
            "por um(a) terceiro(a) revisor(a)."
        ),
        "blind": "Os revisores não viam as decisões uns dos outros.",
        "not_blind": "As decisões dos demais revisores ficavam visíveis.",
        "agreement": (
            "A concordância entre revisores na fase de {phase} teve kappa de Cohen médio de {kappa} "
            "({pairs} par(es) de revisores, {n} decisões pareadas)."
        ),
        "phase_title_abstract": "título e resumo",
        "phase_full_text": "texto completo",
        "ai_use": "Uso de inteligência artificial",
        "ai_suggest": (
            "Um modelo de linguagem ({models}) sugeriu decisões de inclusão na triagem. Cada "
            "revisor só via a sugestão depois de registrar a própria decisão, e todas as decisões "
            "finais foram humanas."
        ),
        "ai_second": (
            "Um modelo de linguagem ({models}) atuou como segundo revisor na triagem. As "
            "divergências entre o modelo e o revisor humano foram resolvidas por pessoas."
        ),
        "ai_local": "O modelo rodou no próprio servidor, sem envio de dados a serviços externos.",
        "ai_extraction": (
            "Um modelo de linguagem ({models}) sugeriu respostas de extração com trechos citados do "
            "texto completo; cada sugestão foi conferida por um extrator humano."
        ),
        "ai_translation": "Um modelo de linguagem ajudou a adaptar a estratégia de busca entre as bases.",
        "ai_appendix_ref": "O registro completo de uso da IA está no Apêndice B.",
        "extraction": "Extração de dados",
        "extraction_form": (
            "Os dados foram extraídos com o formulário “{name}”, por {n} extrator(es) "
            "independente(s) por estudo, com consenso quando havia mais de um."
        ),
        "rob": "Avaliação do risco de viés",
        "rob_form": (
            "O risco de viés foi avaliado com “{name}”, por {n} avaliador(es) independente(s) por "
            "estudo."
        ),
        "synthesis": "Métodos de síntese",
        "meta_methods": (
            "Os resultados foram combinados por meta-análise com o método da variância inversa "
            "({models}; medidas: {measures}). A heterogeneidade foi descrita por I², τ² "
            "(DerSimonian-Laird) e pelo teste Q, com intervalo de predição no modelo de efeitos "
            "aleatórios. O viés de publicação foi avaliado pelo gráfico de funil e pelo teste de "
            "Egger quando havia ao menos 10 estudos."
        ),
        "model_random": "efeitos aleatórios",
        "model_fixed": "efeito fixo",
        "grade_methods": (
            "A certeza da evidência de cada desfecho foi avaliada pela abordagem GRADE "
            "(risco de viés, inconsistência, evidência indireta, imprecisão e viés de publicação)."
        ),
        "coding_methods": (
            "Os achados qualitativos foram sintetizados por codificação temática: {excerpts} "
            "trecho(s) dos estudos incluídos foram marcados com {codes} código(s)."
        ),
        "results": "Resultados",
        "study_selection": "Seleção dos estudos",
        "selection_results": (
            "Foram identificados {total} registros, dos quais {dups} eram duplicatas. Dos {screened} "
            "registros triados, {ta_excluded} foram excluídos pelo título e resumo. Foram avaliados "
            "{assessed} textos completos e {ft_excluded} excluídos. Ao final, {included} estudo(s) "
            "({reports} relatório(s)) foram incluídos."
        ),
        "pending_note": "Ainda há {n} registro(s) com triagem pendente; os números podem mudar.",
        "fig_prisma": "Fluxograma PRISMA da seleção dos estudos.",
        "reasons_table": "Motivos de exclusão na fase de texto completo.",
        "reason": "Motivo",
        "no_reason": "Sem motivo registrado",
        "count": "Nº",
        "included_studies": "Estudos incluídos",
        "included_table": "Estudos incluídos.",
        "no_included": "Nenhum estudo foi incluído ainda.",
        "study": "Estudo",
        "title": "Título",
        "year": "Ano",
        "journal": "Periódico",
        "reports": "Relatórios",
        "rob_results": "Risco de viés",
        "rob_table": "Julgamentos de risco de viés ({name}).",
        "rob_none": "Nenhum estudo avaliado com “{name}”.",
        "rob_low": "Baixo",
        "rob_some": "Algumas preocupações",
        "rob_high": "Alto",
        "rob_moderate": "Moderado",
        "rob_serious": "Sério",
        "rob_critical": "Crítico",
        "rob_ni": "Sem informação",
        "meta_results": "Meta-análises",
        "fig_forest": "Forest plot: {name}.",
        "meta_summary": (
            "{k} estudo(s): {measure} {est} (IC 95% {lower} a {upper}), p {p}; "
            "I² = {i2}%, τ² = {tau2}."
        ),
        "meta_prediction": "Intervalo de predição: {lower} a {upper}.",
        "meta_subgroups": "Diferença entre subgrupos: Q = {q} (gl = {df}), p {p}.",
        "meta_egger": "Teste de Egger: intercepto {intercept}, p {p}.",
        "meta_no_data": "Sem dados suficientes para calcular.",
        "grade_results": "Certeza da evidência (GRADE)",
        "grade_table": "Sumário de achados.",
        "outcome": "Desfecho",
        "studies_participants": "Estudos (participantes)",
        "effect": "Efeito",
        "certainty": "Certeza",
        "importance": "Importância",
        "reasons": "Motivos",
        "certainty_high": "Alta",
        "certainty_moderate": "Moderada",
        "certainty_low": "Baixa",
        "certainty_very_low": "Muito baixa",
        "importance_critical": "Crítico",
        "importance_important": "Importante",
        "importance_limited": "Pouco importante",
        "domain_risk_of_bias": "risco de viés",
        "domain_inconsistency": "inconsistência",
        "domain_indirectness": "evidência indireta",
        "domain_imprecision": "imprecisão",
        "domain_publication_bias": "viés de publicação",
        "domain_large_effect": "efeito grande",
        "domain_dose_response": "dose-resposta",
        "domain_confounding": "confundimento",
        "coding_results": "Síntese qualitativa",
        "codes_table": "Códigos, com o número de estudos e de trechos em cada um.",
        "code": "Código",
        "studies": "Estudos",
        "excerpts": "Trechos",
        "appendix_a": "Apêndice A. Estratégias de busca",
        "source": "Fonte",
        "date": "Data",
        "method": "Método",
        "method_database": "Base de dados",
        "records_reported": "Registros (informados / importados)",
        "via_api": "pela API do ReValli",
        "file": "arquivo {name}",
        "query_missing": "Estratégia não registrada.",
        "notes": "Notas",
        "appendix_b": "Apêndice B. Registro de uso da IA",
        "ai_disabled": "A IA não foi usada neste projeto.",
        "ai_settings": (
            "Configuração atual: IA {enabled}; modo {mode}; {local}; orçamento {budget}."
        ),
        "enabled": "ligada",
        "disabled": "desligada",
        "mode_suggest": "sugestão",
        "mode_second_reviewer": "segundo revisor",
        "local_only": "só modelos locais",
        "any_provider": "modelos locais ou remotos",
        "no_budget": "sem limite",
        "usage_table": "Chamadas ao modelo por tarefa.",
        "task": "Tarefa",
        "model": "Modelo",
        "calls": "Chamadas",
        "tokens_in": "Tokens de entrada",
        "tokens_out": "Tokens de saída",
        "cost": "Custo (US$)",
        "task_screening": "Triagem",
        "task_extraction": "Extração",
        "task_query_translation": "Tradução de busca",
        "task_embeddings": "Ordenação por relevância",
        "calibration_table": (
            "Desempenho da IA comparado à decisão humana final (“talvez” conta como inclusão)."
        ),
        "phase": "Fase",
        "compared": "Registros comparados",
        "sensitivity": "Sensibilidade",
        "specificity": "Especificidade",
        "kappa": "Kappa",
        "appendix_c": "Apêndice C. Checklist {name}",
        "checklist_prisma2020": "PRISMA 2020",
        "checklist_prisma_scr": "PRISMA-ScR",
        "item": "Item",
        "description": "Descrição",
        "status": "Situação",
        "location": "Onde",
        "status_pending": "Pendente",
        "status_done": "Feito",
        "status_na": "Não se aplica",
        "table": "Tabela",
        "figure": "Figura",
    },
    "en": {
        "draft_note": (
            "Draft generated automatically by ReValli on {date}. Review all text before use. "
            "ReValli is a vibe-coded project (written with heavy AI assistance)."
        ),
        "review_type_systematic": "Systematic review",
        "review_type_scoping": "Scoping review",
        "review_type_integrative": "Integrative review",
        "review_type_other": "Review",
        "methods": "Methods",
        "eligibility": "Eligibility criteria",
        "inclusion": "Inclusion criteria",
        "exclusion": "Exclusion criteria",
        "no_criteria": "Eligibility criteria were not recorded in ReValli.",
        "sources": "Information sources and search strategy",
        "sources_text": "We searched {n} source(s): {list}.",
        "sources_none": "No search was recorded in ReValli.",
        "sources_api": "Searches in {list} were run directly through the databases' APIs.",
        "citation_text": "We also searched citations ({list}) from the included studies.",
        "method_citation_backward": "reference lists",
        "method_citation_forward": "citing studies",
        "strategies_appendix": "Full search strategies are in Appendix A.",
        "selection": "Selection process",
        "selection_text": (
            "Titles and abstracts were screened by {ta} independent reviewer(s) per record and full "
            "texts by {ft}. {blind} Disagreements were resolved by discussion or by a third "
            "reviewer."
        ),
        "blind": "Reviewers could not see each other's decisions.",
        "not_blind": "Other reviewers' decisions were visible.",
        "agreement": (
            "Inter-rater agreement at the {phase} stage had a mean Cohen's kappa of {kappa} "
            "({pairs} reviewer pair(s), {n} paired decisions)."
        ),
        "phase_title_abstract": "title and abstract",
        "phase_full_text": "full-text",
        "ai_use": "Use of artificial intelligence",
        "ai_suggest": (
            "A language model ({models}) suggested inclusion decisions during screening. Each "
            "reviewer saw the suggestion only after recording their own decision, and all final "
            "decisions were made by humans."
        ),
        "ai_second": (
            "A language model ({models}) acted as second reviewer during screening. Disagreements "
            "between the model and the human reviewer were resolved by people."
        ),
        "ai_local": "The model ran on our own server; no data was sent to external services.",
        "ai_extraction": (
            "A language model ({models}) suggested extraction answers with quotes from the full "
            "text; each suggestion was checked by a human extractor."
        ),
        "ai_translation": "A language model helped adapt the search strategy across databases.",
        "ai_appendix_ref": "The full log of AI use is in Appendix B.",
        "extraction": "Data extraction",
        "extraction_form": (
            "Data were extracted with the “{name}” form by {n} independent extractor(s) per study, "
            "with consensus when there was more than one."
        ),
        "rob": "Risk of bias assessment",
        "rob_form": (
            "Risk of bias was assessed with “{name}” by {n} independent assessor(s) per study."
        ),
        "synthesis": "Synthesis methods",
        "meta_methods": (
            "Results were pooled by inverse-variance meta-analysis ({models}; measures: "
            "{measures}). Heterogeneity was described with I², τ² (DerSimonian-Laird) and the Q "
            "test, with a prediction interval under the random-effects model. Publication bias was "
            "assessed with funnel plots and Egger's test when there were at least 10 studies."
        ),
        "model_random": "random effects",
        "model_fixed": "fixed effect",
        "grade_methods": (
            "Certainty of evidence for each outcome was assessed with the GRADE approach (risk of "
            "bias, inconsistency, indirectness, imprecision and publication bias)."
        ),
        "coding_methods": (
            "Qualitative findings were synthesised by thematic coding: {excerpts} excerpt(s) from "
            "the included studies were tagged with {codes} code(s)."
        ),
        "results": "Results",
        "study_selection": "Study selection",
        "selection_results": (
            "We identified {total} records, of which {dups} were duplicates. Of the {screened} "
            "records screened, {ta_excluded} were excluded on title and abstract. We assessed "
            "{assessed} full texts and excluded {ft_excluded}. In the end, {included} study(ies) "
            "({reports} report(s)) were included."
        ),
        "pending_note": "{n} record(s) still await screening; numbers may change.",
        "fig_prisma": "PRISMA flow diagram of study selection.",
        "reasons_table": "Reasons for exclusion at the full-text stage.",
        "reason": "Reason",
        "no_reason": "No reason recorded",
        "count": "No.",
        "included_studies": "Included studies",
        "included_table": "Included studies.",
        "no_included": "No study has been included yet.",
        "study": "Study",
        "title": "Title",
        "year": "Year",
        "journal": "Journal",
        "reports": "Reports",
        "rob_results": "Risk of bias",
        "rob_table": "Risk of bias judgements ({name}).",
        "rob_none": "No study assessed with “{name}”.",
        "rob_low": "Low",
        "rob_some": "Some concerns",
        "rob_high": "High",
        "rob_moderate": "Moderate",
        "rob_serious": "Serious",
        "rob_critical": "Critical",
        "rob_ni": "No information",
        "meta_results": "Meta-analyses",
        "fig_forest": "Forest plot: {name}.",
        "meta_summary": (
            "{k} study(ies): {measure} {est} (95% CI {lower} to {upper}), p {p}; "
            "I² = {i2}%, τ² = {tau2}."
        ),
        "meta_prediction": "Prediction interval: {lower} to {upper}.",
        "meta_subgroups": "Test for subgroup differences: Q = {q} (df = {df}), p {p}.",
        "meta_egger": "Egger's test: intercept {intercept}, p {p}.",
        "meta_no_data": "Not enough data to calculate.",
        "grade_results": "Certainty of evidence (GRADE)",
        "grade_table": "Summary of findings.",
        "outcome": "Outcome",
        "studies_participants": "Studies (participants)",
        "effect": "Effect",
        "certainty": "Certainty",
        "importance": "Importance",
        "reasons": "Reasons",
        "certainty_high": "High",
        "certainty_moderate": "Moderate",
        "certainty_low": "Low",
        "certainty_very_low": "Very low",
        "importance_critical": "Critical",
        "importance_important": "Important",
        "importance_limited": "Of limited importance",
        "domain_risk_of_bias": "risk of bias",
        "domain_inconsistency": "inconsistency",
        "domain_indirectness": "indirectness",
        "domain_imprecision": "imprecision",
        "domain_publication_bias": "publication bias",
        "domain_large_effect": "large effect",
        "domain_dose_response": "dose-response",
        "domain_confounding": "confounding",
        "coding_results": "Qualitative synthesis",
        "codes_table": "Codes, with the number of studies and excerpts in each.",
        "code": "Code",
        "studies": "Studies",
        "excerpts": "Excerpts",
        "appendix_a": "Appendix A. Search strategies",
        "source": "Source",
        "date": "Date",
        "method": "Method",
        "method_database": "Database",
        "records_reported": "Records (reported / imported)",
        "via_api": "through ReValli's API search",
        "file": "file {name}",
        "query_missing": "Strategy not recorded.",
        "notes": "Notes",
        "appendix_b": "Appendix B. Log of AI use",
        "ai_disabled": "AI was not used in this project.",
        "ai_settings": "Current settings: AI {enabled}; mode {mode}; {local}; budget {budget}.",
        "enabled": "on",
        "disabled": "off",
        "mode_suggest": "suggestion",
        "mode_second_reviewer": "second reviewer",
        "local_only": "local models only",
        "any_provider": "local or remote models",
        "no_budget": "no limit",
        "usage_table": "Model calls by task.",
        "task": "Task",
        "model": "Model",
        "calls": "Calls",
        "tokens_in": "Input tokens",
        "tokens_out": "Output tokens",
        "cost": "Cost (US$)",
        "task_screening": "Screening",
        "task_extraction": "Extraction",
        "task_query_translation": "Search translation",
        "task_embeddings": "Relevance ranking",
        "calibration_table": (
            "AI performance against the final human decision (“maybe” counts as include)."
        ),
        "phase": "Stage",
        "compared": "Records compared",
        "sensitivity": "Sensitivity",
        "specificity": "Specificity",
        "kappa": "Kappa",
        "appendix_c": "Appendix C. {name} checklist",
        "checklist_prisma2020": "PRISMA 2020",
        "checklist_prisma_scr": "PRISMA-ScR",
        "item": "Item",
        "description": "Description",
        "status": "Status",
        "location": "Location",
        "status_pending": "Pending",
        "status_done": "Done",
        "status_na": "Not applicable",
        "table": "Table",
        "figure": "Figure",
    },
}
