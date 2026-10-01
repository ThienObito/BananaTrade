"""Safety checks preventing draft prompts from reaching live models."""
from pathlib import Path


class DraftPromptError(RuntimeError):
    """Raised when draft prompts are used for a live model call."""


def find_draft_prompts(prompt_dir: Path) -> list[Path]:
    """Return prompt files whose first non-empty line starts with ``DRAFT``."""
    if not prompt_dir.is_dir():
        return []
    drafts: list[Path] = []
    for path in sorted(prompt_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        if next((line.strip() for line in lines if line.strip()), "").startswith("DRAFT"):
            drafts.append(path)
    return drafts


def assert_live_allowed(prompt_files: list[Path], dry_run: bool) -> None:
    """Reject live execution when any supplied prompt is marked as draft."""
    if dry_run or not prompt_files:
        return
    names = ", ".join(str(path) for path in prompt_files)
    raise DraftPromptError(f"Draft prompts are not allowed for live runs: {names}")
