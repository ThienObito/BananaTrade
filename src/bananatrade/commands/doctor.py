"""Configuration and runtime health checks."""
import os
from pathlib import Path
from typing import Any

import typer
import yaml


doctor_app = typer.Typer(help="Check BananaTrade configuration and runtime readiness.")
ROOT = Path(__file__).resolve().parents[3]
PLACEHOLDER = "REPLACE_WITH_9ROUTER_MODEL_ID"


def _load_configs(root: Path) -> tuple[bool, list[str], dict[str, Any]]:
    errors: list[str] = []
    configs: dict[str, Any] = {}
    for name in ("models.yaml", "markets.yaml", "risk.yaml"):
        path = root / "config" / name
        try:
            with path.open(encoding="utf-8") as fh:
                configs[name] = yaml.safe_load(fh) or {}
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    return not errors, errors, configs


def _check(root: Path, env: dict[str, str] | None = None) -> list[tuple[str, str, str]]:
    # An explicitly passed empty mapping must be honoured; only None falls back to os.environ.
    env = os.environ if env is None else env
    results: list[tuple[str, str, str]] = []
    loaded, errors, configs = _load_configs(root)
    results.append(("config files load", "PASS" if loaded else "FAIL", "; ".join(errors)))
    models_text = ""
    try:
        models_text = (root / "config" / "models.yaml").read_text(encoding="utf-8")
    except OSError:
        pass
    results.append(("no placeholder model IDs", "FAIL" if PLACEHOLDER in models_text else "PASS", ""))
    models = configs.get("models.yaml")
    if not isinstance(models, dict):
        # Unparseable models.yaml cannot prove tier4 is safe, so it must not report PASS.
        results.append(("tier4 model_id is not combo", "FAIL", "models.yaml not loaded"))
    else:
        tiers = models.get("tiers") or {}
        tier4 = tiers.get("tier4_cio") or {} if isinstance(tiers, dict) else {}
        model_id = tier4.get("model_id", "") if isinstance(tier4, dict) else ""
        is_combo = str(model_id).lower().startswith("combo")
        results.append(("tier4 model_id is not combo", "FAIL" if is_combo else "PASS", ""))
    key_ok = bool(env.get("NINEROUTER_API_KEY"))
    results.append(("NINEROUTER_API_KEY present", "PASS" if key_ok else "FAIL", ""))
    drafts: list[str] = []
    for path in (root / "config").rglob("*"):
        if path.is_file():
            try:
                if "DRAFT" in path.read_text(encoding="utf-8", errors="ignore"):
                    drafts.append(str(path.relative_to(root)))
            except OSError:
                pass
    results.append(("prompts present", "WARN" if drafts else "PASS", ", ".join(drafts)))
    data = root / "data"
    try:
        data.mkdir(parents=True, exist_ok=True)
        probe = data / ".doctor-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        writable = True
    except OSError:
        writable = False
    results.append(("data writable", "PASS" if writable else "FAIL", ""))
    return results


@doctor_app.callback(invoke_without_command=True)
def doctor() -> None:
    """Run readiness checks."""
    failed = False
    for name, status, detail in _check(ROOT):
        typer.echo(f"{status} {name}" + (f": {detail}" if status == "WARN" and detail else ""))
        failed = failed or status == "FAIL"
    if failed:
        raise typer.Exit(code=1)
