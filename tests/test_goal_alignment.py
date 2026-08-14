import pytest

from jbspan.schemas import GoalAlignment, PromptPair


def test_prompt_pair_defaults_to_unreviewed_goal_alignment() -> None:
    pair = PromptPair(
        id="example",
        behavior="test",
        original_prompt="original",
        jailbreak_prompt="jailbreak",
        attack_family="test",
    )
    assert pair.goal_alignment is GoalAlignment.UNREVIEWED


def test_prompt_pair_accepts_reviewed_goal_alignment() -> None:
    pair = PromptPair(
        id="example",
        behavior="test",
        original_prompt="original",
        jailbreak_prompt="jailbreak",
        attack_family="test",
        metadata={"goal_alignment": "FULL"},
    )
    assert pair.goal_alignment is GoalAlignment.FULL


def test_prompt_pair_rejects_invalid_goal_alignment() -> None:
    with pytest.raises(ValueError, match="goal_alignment"):
        PromptPair(
            id="example",
            behavior="test",
            original_prompt="original",
            jailbreak_prompt="jailbreak",
            attack_family="test",
            metadata={"goal_alignment": "SAME_ENOUGH"},
        )
