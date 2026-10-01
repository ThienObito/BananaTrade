from pathlib import Path

from typer.testing import CliRunner

from bananatrade.cli import app
from bananatrade.commands.doctor import _check


def make_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "config" / "models.yaml").write_text(
        "tiers:\n  tier4_cio:\n    model_id: cc/claude-opus\n", encoding="utf-8"
    )
    for name in ("markets.yaml", "risk.yaml"):
        (tmp_path / "config" / name).write_text("{}\n", encoding="utf-8")
    return tmp_path


def statuses(root, env):
    return {name: status for name, status, _ in _check(root, env)}


def test_doctor_pass_checks(tmp_path):
    result = statuses(make_root(tmp_path), {"NINEROUTER_API_KEY": "secret-value"})
    assert all(result[name] == "PASS" for name in result if name != "prompts present")


def test_doctor_failures_and_key_not_printed(tmp_path):
    root = make_root(tmp_path)
    (root / "config" / "models.yaml").write_text(
        "tiers:\n  tier4_cio:\n    model_id: combo-mix\nREPLACE_WITH_9ROUTER_MODEL_ID\n", encoding="utf-8"
    )
    statuses_seen = statuses(root, {})
    assert statuses_seen["no placeholder model IDs"] == "FAIL"
    assert statuses_seen["tier4 model_id is not combo"] == "FAIL"
    runner = CliRunner()
    output = runner.invoke(app, ["doctor"]).output
    assert "secret-value" not in output
