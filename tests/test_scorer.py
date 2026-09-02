from pdf_nl_search.scorer import compute_idf, score_paragraph, ScoreArgs


def test_compute_idf_rare_term_boosted():
    idf = compute_idf({"rare": 1, "common": 10}, N=10)
    assert idf["rare"] > idf["common"]


def test_score_multi_term_beats_single():
    args = ScoreArgs(weights={"a": 1.0, "b": 1.0}, idf={"a": 1.0, "b": 1.0})
    one = score_paragraph(args, {"a": [(0, 1)]})
    two = score_paragraph(args, {"a": [(0, 1)], "b": [(10, 11)]})
    assert two > one
