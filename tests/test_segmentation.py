from jbspan.segmentation import RegexClauseSegmenter, build_balanced_tree


def test_segmentation_preserves_text_offsets() -> None:
    text = "First clause. Second clause; third clause."
    segments = RegexClauseSegmenter().segment(text)
    assert [segment.text(text) for segment in segments] == [
        "First clause.",
        "Second clause;",
        "third clause.",
    ]


def test_balanced_tree_covers_all_segments() -> None:
    text = "A. B. C. D."
    segments = RegexClauseSegmenter().segment(text)
    tree = build_balanced_tree(segments)
    assert tree.span.text(text) == text
    assert tree.leaves() == segments
