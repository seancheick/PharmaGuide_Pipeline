import pytest

from api_audit.pubmed_xml import bound_pmc_text, source_quote_matches


@pytest.mark.parametrize("claim,source", [("32 mg", "3.2 mg"), ("p < 0.05", "p > 0.05"),
    ("10-9 CFU", "109 CFU"), ("", "any text"), ("32 mg", "132 mg"),
    ("5 mg", "3.5 mg"), ("N=10", "N=100")])
def test_quote_cannot_change_numeric_or_empty_claims(claim, source):
    assert not source_quote_matches(claim, source)


def test_formatting_whitespace_and_entities_are_equivalent():
    assert source_quote_matches("400 mg; P < 0.05", "400\nmg; P &lt; 0.05")
    assert source_quote_matches("1.6 g BA/day", "After two weeks. 1.6 g BA/day was given.")


def test_full_text_is_bound_to_its_own_pmid_not_a_reference():
    raw = b'<article><front><article-meta><article-id pub-id-type="pmid">1</article-id></article-meta></front><body><p>3.2 mg</p></body><back><ref>PMID 2; 99 mg</ref></back></article>'
    assert "3.2 mg" in bound_pmc_text(raw, "1")
    assert "99 mg" not in bound_pmc_text(raw, "1")
    with pytest.raises(ValueError, match="PMID mismatch"):
        bound_pmc_text(raw, "2")


def test_detached_article_tables_are_source_text():
    raw = b'<article><front><article-meta><article-id pub-id-type="pmid">1</article-id></article-meta></front><floats-group><table-wrap><table><tr><td>3.2 mg</td></tr></table></table-wrap></floats-group></article>'
    assert source_quote_matches("3.2 mg", bound_pmc_text(raw, "1"))


def test_neighboring_table_cells_do_not_extend_a_strain_identifier():
    raw = b'<article><front><article-meta><article-id pub-id-type="pmid">1</article-id></article-meta></front><body><table><tr><td>LPC 00 ID 1076</td><td>1500 mg</td></tr></table></body></article>'
    text = bound_pmc_text(raw, "1")
    assert source_quote_matches("LPC 00 ID 1076", text)
    assert not source_quote_matches("150 mg", text)
