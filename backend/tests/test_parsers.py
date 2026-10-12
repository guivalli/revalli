from pathlib import Path

import pytest

from revalli.modules.imports.normalize import (
    first_author_key,
    normalize_doi,
    normalize_title,
)
from revalli.modules.imports.parsers import ImportFormatError, parse_file

FIX = Path(__file__).parent / "fixtures"


def load(name: str):
    return parse_file(name, (FIX / name).read_bytes())


def test_ris():
    fmt, recs = load("sample.ris")
    assert fmt == "ris" and len(recs) == 2
    a, b = recs
    assert a.title == "Physical exercise and anxiety in older adults: a randomized trial"
    assert a.authors == ["Silva, João", "Souza, Maria"]
    assert a.year == 2021 and a.pages == "101-110" and a.volume == "12"
    assert a.doi == "10.1000/abc.123"
    assert a.abstract == "Background: Anxiety is common. Methods: We randomized 120 adults."
    assert a.keywords == ["exercise", "anxiety"]
    assert b.year == 2019 and b.doi == "10.5555/xyz.9" and b.pmid == "31234567"
    assert b.journal == "Revista Brasileira de Geriatria"


def test_ris_latin1():
    _, recs = load("latin1.ris")
    assert recs[0].title == "Ansiedade e atividade física"
    assert recs[0].authors == ["Lima, José"]


def test_medline():
    fmt, recs = load("sample.nbib")
    assert fmt == "medline" and len(recs) == 2
    r = recs[0]
    assert r.pmid == "33445566"
    assert r.title.startswith(
        "Mindfulness for anxiety: a systematic review of randomized controlled"
    )
    assert r.doi == "10.2000/mind.2020.1"
    assert r.authors == ["Costa, Pedro", "Alves, Rita"]
    assert r.year == 2020
    assert "Systematic Review" in r.publication_type
    assert "Anxiety" in r.keywords and "mindfulness" in r.keywords


def test_pubmed_xml():
    fmt, recs = load("sample.xml")
    assert fmt == "pubmed_xml"
    r = recs[0]
    assert r.title == "Sleep and anxiety in adolescents"
    assert r.abstract == "BACKGROUND: Sleep matters. RESULTS: It does."
    assert r.authors == ["Rocha, Bia", "Study Group"]
    assert (r.year, r.doi, r.pmid, r.journal) == (
        2017,
        "10.3000/sleep.17",
        "11122233",
        "Sleep Medicine",
    )


def test_pubmed_xml_rejects_entities():
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><PubmedArticleSet>&b;</PubmedArticleSet>'
    with pytest.raises(ImportFormatError):
        parse_file("x.xml", bomb)


def test_bibtex():
    fmt, recs = load("sample.bib")
    assert fmt == "bibtex" and len(recs) == 2
    a = {r.title: r for r in recs}[
        "Physical Exercise and Anxiety in Older Adults: A Randomized Trial"
    ]
    assert a.authors == ["Silva, João", "Souza, Maria"]
    assert a.pages == "101-110" and a.doi == "10.1000/abc.123"
    assert a.keywords == ["exercise", "anxiety"]
    other = [r for r in recs if r is not a][0]
    assert other.journal == "Proceedings of Things" and other.year == 2015


def test_wos():
    fmt, recs = load("sample_wos.txt")
    assert fmt == "wos" and len(recs) == 1
    r = recs[0]
    assert r.title == "Physical exercise and anxiety in older adults: a randomized trial"
    assert r.authors == ["Silva, Joao", "Souza, Maria"]
    assert r.pmid == "30000001" and r.pages == "101-110"


def test_csv():
    fmt, recs = load("sample.csv")
    assert fmt == "csv" and len(recs) == 2
    assert recs[0].authors == ["Silva J.", "Souza M."]
    assert recs[0].doi == "10.1000/abc.123"
    assert recs[1].pmid == "35555555" and recs[1].doi is None


def test_csv_semicolon_portuguese_headers():
    _, recs = load("sample_semicolon.csv")
    assert recs[0].title == "Ansiedade em universitários"
    assert recs[0].year == 2023 and recs[0].abstract == "Estudo transversal."


def test_unknown_format():
    with pytest.raises(ImportFormatError):
        parse_file("x.pdf", b"%PDF-1.4 binary")


def test_normalizers():
    assert normalize_doi("doi:10.1000/ABC.(1)x") == "10.1000/abc.(1)x"
    assert normalize_doi("sem doi") is None
    assert (
        normalize_title("Efeito do Exercício — na ANSIEDADE!") == "efeito do exercicio na ansiedade"
    )
    assert first_author_key(["Souza-Lima, Maria"]) == "souzalima"
    assert first_author_key(["M. Souza"]) == "souza"


def test_ris_bvs_export():
    """Exportação real da BVS (LILACS e INDEXPSI): TT, MH, páginas zeradas e marca (AU)."""
    fmt, recs = load("sample_bvs.ris")
    assert fmt == "ris" and len(recs) == 7
    editorial, en_title, pt_title = recs[0], recs[1], recs[2]
    # Sem palavras-chave do autor, os descritores (MH) entram como palavras-chave
    assert editorial.keywords == ["Terapia Gestalt"]
    assert editorial.pages == "VI-IX" and editorial.doi is None
    assert editorial.language == "pt"
    # O caractere de controle do Windows-1252 volta a ser a aspa
    assert "\x92" not in en_title.abstract
    assert "doesn’t" in en_title.abstract
    # A marca de resumo de autor não fica no texto
    assert not en_title.abstract.endswith("(AU)") and "(AU)" not in pt_title.abstract
    # Páginas "0-0" não são páginas
    assert pt_title.pages == ""
    # Os dois resumos (inglês e português) ficam juntos
    assert (
        "This text discusses" in en_title.abstract and "Este texto apresenta" in en_title.abstract
    )
    # Palavras-chave do autor têm prioridade sobre os descritores
    assert "Terapia Gestalt" not in en_title.keywords and "Supervisão" in en_title.keywords
    # O título traduzido fica no registro bruto
    assert en_title.raw["TT"].startswith("A Gestalt-terapia na universidade")
