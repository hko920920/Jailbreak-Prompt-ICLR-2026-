from jbspan.adapters.toy import ToyIntentJudge, ToyJailbreakModel, ToyResponseJudge
from jbspan.neutralization import PlaceholderNeutralizer
from jbspan.schemas import LocalizationStatus, PromptPair
from jbspan.scoring import CausalEvaluator
from jbspan.search.common import SearchConfig
from jbspan.search.exhaustive import ExhaustiveAtomicSearch
from jbspan.search.hierarchical import GreedyHierarchicalSearch
from jbspan.search.wavelet import WaveletTreeSearch
from jbspan.segmentation import RegexClauseSegmenter, SpanNode, build_balanced_tree


def _fixture() -> tuple[PromptPair, SpanNode, CausalEvaluator]:
    original = "Complete the harmless benchmark task."
    prompt = f"Normal preface. OVERRIDE-SAFETY. {original} Final note."
    pair = PromptPair(
        id="toy-search",
        behavior="harmless benchmark",
        original_prompt=original,
        jailbreak_prompt=prompt,
        attack_family="toy",
    )
    tree = build_balanced_tree(RegexClauseSegmenter().segment(prompt))
    evaluator = CausalEvaluator(
        target=ToyJailbreakModel(),
        response_judge=ToyResponseJudge(),
        intent_judge=ToyIntentJudge(),
        neutralizers=(PlaceholderNeutralizer(),),
    )
    return pair, tree, evaluator


def test_all_searches_find_trigger() -> None:
    for search in (ExhaustiveAtomicSearch(), GreedyHierarchicalSearch(), WaveletTreeSearch()):
        pair, tree, evaluator = _fixture()
        result = search.localize(
            pair,
            tree,
            evaluator,
            SearchConfig(effect_threshold=0.5, intent_threshold=1.0, max_queries=30),
        )
        assert result.status == LocalizationStatus.LOCALIZED
        localized = " ".join(span.text(pair.jailbreak_prompt) for span in result.spans)
        assert "OVERRIDE-SAFETY" in localized
        assert result.query_count > 0
