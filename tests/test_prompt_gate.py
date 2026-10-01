from pathlib import Path

import pytest

from bananatrade.agents.prompt_gate import DraftPromptError, assert_live_allowed, find_draft_prompts


def test_detection_and_leading_empty_lines(tmp_path: Path):
    (tmp_path / "draft.md").write_text("\n  \nDRAFT candidate\n", encoding="utf-8")
    (tmp_path / "live.md").write_text("READY\nDRAFT later\n", encoding="utf-8")
    assert find_draft_prompts(tmp_path) == [tmp_path / "draft.md"]


def test_live_refusal_lists_files(tmp_path: Path):
    draft = tmp_path / "draft.md"
    with pytest.raises(DraftPromptError, match="draft.md"):
        assert_live_allowed([draft], dry_run=False)


def test_dry_run_allowed(tmp_path: Path):
    assert_live_allowed([tmp_path / "draft.md"], dry_run=True)


def test_clean_prompts_allowed(tmp_path: Path):
    assert_live_allowed([], dry_run=False)
