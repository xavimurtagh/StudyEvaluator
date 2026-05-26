"""Tests for ingest.py.

The live network call is exercised by scripts/smoke_test.py; here we focus
on the XML parsing layer because that's where bugs hide -- PubMed's XML is
gnarly and the schema varies by record age.
"""

from __future__ import annotations

from api.pipeline.ingest import build_query, parse_pubmed_xml

SAMPLE_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">99999999</PMID>
      <Article>
        <Journal>
          <Title>Journal of Test Medicine</Title>
        </Journal>
        <ArticleTitle>A randomized trial of test compound for skin health</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Background text.</AbstractText>
          <AbstractText Label="METHODS">We randomized 200 adults to test or placebo for 12 weeks.</AbstractText>
          <AbstractText Label="RESULTS">Test compound significantly improved skin elasticity.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>Smith</LastName><Initials>J</Initials></Author>
          <Author><LastName>Jones</LastName><Initials>K</Initials></Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Randomized Controlled Trial</PublicationType>
        </PublicationTypeList>
      </Article>
      <MeshHeadingList>
        <MeshHeading><DescriptorName>Skin</DescriptorName></MeshHeading>
      </MeshHeadingList>
      <CoiStatement>No conflicts to declare.</CoiStatement>
    </MedlineCitation>
    <PubmedData>
      <History>
        <PubMedPubDate PubStatus="pubmed">
          <Year>2023</Year>
        </PubMedPubDate>
      </History>
      <ArticleIdList>
        <ArticleId IdType="pubmed">99999999</ArticleId>
        <ArticleId IdType="doi">10.1000/test.1</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


def test_parses_pubmed_xml():
    records = parse_pubmed_xml(SAMPLE_XML)
    assert len(records) == 1
    r = records[0]
    assert r.pmid == "99999999"
    assert "randomized trial" in r.title.lower()
    assert "skin elasticity" in r.abstract.lower()
    assert r.journal == "Journal of Test Medicine"
    assert r.year == 2023
    assert "Smith J" in r.authors
    assert r.doi == "10.1000/test.1"
    assert "Skin" in r.mesh_terms
    assert "Randomized Controlled Trial" in r.publication_types
    assert r.has_coi_statement is True


def test_build_query_quotes_multi_word():
    assert '"vitamin d"' in build_query("vitamin d").lower()
    assert 'creatine' in build_query("creatine").lower()
