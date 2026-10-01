# Protect the BananaTrade source with git and verify it on Windows.
# Run from the project root:   powershell -ExecutionPolicy Bypass -File scripts\protect_and_verify.ps1
#
# What it does (stops at the first failure, never pushes):
#   0. Sanity checks: project root, clean index, .gitignore covers secrets/venv/db/caches.
#   1. Creates branch recover-wave1-onnx-filter (main is not modified).
#   2. Deletes __pycache__ dirs and *.pyc / *.pyc.<n> files under src/ and tests/.
#   3. Commit A: the whole previously-untracked source tree, in its ORIGINAL (pre-session)
#      state. Done before tests so protection never depends on test results.
#   4. pip install -e ".[dev,ml]" into .venv, import check, CLI --help, pytest -n auto.
#      Output is saved to reports\windows_verify.log. B/C are committed only if this passes.
#   5. Commit B: wave1 recovery + doctor/test fixes + disabled ONNX filter.
#   6. Commit C: BacktestEngine quantity_step sizing fix + strategy diagnosis.
# .env is never added; the script aborts if it ever appears in the index.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$root = Get-Location
$py = Join-Path $root ".venv\Scripts\python.exe"
$log = Join-Path $root "reports\windows_verify.log"
$branch = "recover-wave1-onnx-filter"
$orig = Join-Path $root ".orig_for_commit_a"

function Run([string]$what, [scriptblock]$cmd) {
    Write-Host "==> $what" -ForegroundColor Cyan
    "==> $what" | Out-File $log -Append -Encoding utf8
    $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"  # pip/pytest write to stderr
    & $cmd 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append
    $ErrorActionPreference = $prev
    if ($LASTEXITCODE -ne 0) { throw "FAILED: $what (exit $LASTEXITCODE). See $log" }
}

function Assert-NoSecretsStaged {
    $bad = git diff --cached --name-only | Where-Object { $_ -match '(^|/)\.env$|^\.venv/|\.db$|__pycache__|\.pyc' }
    if ($bad) { throw "Refusing to commit forbidden paths: $($bad -join ', ')" }
}

# ---------- 0. sanity ----------
if (-not (Test-Path "pyproject.toml") -or -not (Test-Path ".git")) { throw "Run from E:\Trade-AI\BananaTrade" }
if (-not (Test-Path $py)) { throw ".venv\Scripts\python.exe not found" }
if (git diff --cached --name-only) { throw "Index is not clean; commit or unstage first." }
New-Item -ItemType Directory -Force reports | Out-Null
"BananaTrade Windows verification $(Get-Date -Format o)" | Out-File $log -Encoding utf8

$need = @(".env", ".venv/", "data/*.db", "__pycache__/", "*.pyc", ".pytest-tmp*/", ".hypothesis/", "tmpx/", "trades/", ".orig_for_commit_a/")
$gi = if (Test-Path .gitignore) { Get-Content .gitignore } else { @() }
$missing = $need | Where-Object { $gi -notcontains $_ }
if ($missing) {
    Add-Content .gitignore -Value ("`n# added by protect_and_verify.ps1`n" + ($missing -join "`n"))
    Write-Host "Added to .gitignore: $($missing -join ', ')"
}
foreach ($p in @(".env", ".venv/x", "data/x.db", "src/__pycache__/x.pyc")) {
    git check-ignore -q $p
    if ($LASTEXITCODE -ne 0) { throw ".gitignore does not exclude $p" }
}

# ---------- 1. branch ----------
$current = git rev-parse --abbrev-ref HEAD
if ($current -ne $branch) {
    git show-ref --verify --quiet "refs/heads/$branch"
    if ($LASTEXITCODE -eq 0) { Run "checkout $branch" { git checkout $branch } }
    else { Run "create branch $branch" { git checkout -b $branch } }
}

# ---------- 2. clean bytecode ----------
Get-ChildItem src, tests -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem src, tests -Recurse -File -Include *.pyc, *.pyc.* -ErrorAction SilentlyContinue | Remove-Item -Force
$left = @(Get-ChildItem src, tests -Recurse -File -Include *.pyc, *.pyc.* -ErrorAction SilentlyContinue).Count
"remaining .pyc files: $left" | Tee-Object -FilePath $log -Append
if ($left -ne 0) { throw "bytecode cleanup incomplete" }

# ---------- 3. commit A (before tests: protection must not depend on test results) ----------
$srcPaths = @("src", "tests", "scripts", "config", "prompts", "web", "pyproject.toml", "README.md", ".gitignore", ".env.example")
# files created this/previous session -> belong to commits B/C, not A
$newB = @(
  "src/bananatrade/core", "src/bananatrade/evaluation", "src/bananatrade/execution", "src/bananatrade/commands", "src/bananatrade/notify",
  "src/bananatrade/agents/decision_schemas.py", "src/bananatrade/agents/decision_validator.py", "src/bananatrade/agents/prompt_gate.py",
  "src/bananatrade/storage/migrations.py",
  "tests/test_clock.py", "tests/test_cmd_doctor.py", "tests/test_decision_validator.py", "tests/test_metrics.py",
  "tests/test_notifier.py", "tests/test_portfolio.py", "tests/test_prompt_gate.py",
  "src/bananatrade/engine/entry_filter.py", "src/bananatrade/research/entry_filter_eval.py",
  "scripts/train_entry_filter.py", "tests/test_entry_filter.py")
$newC = @("scripts/diagnose_strategy.py", "scripts/protect_and_verify.ps1")
# files edited in-session: commit A stores their ORIGINAL content from .orig_for_commit_a
$edited = @("src/bananatrade/brain.py", "src/bananatrade/cli.py", "config/risk.yaml", "pyproject.toml",
  "tests/test_config_regime_ensemble.py", "src/bananatrade/backtest/engine.py", "tests/test_backtest_realistic.py")

git add -- $srcPaths
git reset -q -- ($newB + $newC)
foreach ($f in $edited) {
    $o = Join-Path $orig $f
    if (-not (Test-Path $o)) { throw "missing original $o" }
    $hash = git hash-object -w -- $o
    git update-index --add --cacheinfo "100644,$hash,$f"
}
Assert-NoSecretsStaged
if (git diff --cached --name-only) {
    Run "commit A" { git commit -q -m "Track full source tree that was never committed (original state)" }
}

# ---------- 4. install + verify (commits B/C only happen if this passes) ----------
Run "pip install -e .[dev,ml]" { & $py -m pip install -e ".[dev,ml]" }
Run "import check" { & $py -B -c "import bananatrade.web_server, bananatrade.paper_broker; print('import OK')" }
Run "CLI --help" { & $py -B -m bananatrade --help }
Run "pytest -n auto" { & $py -B -m pytest -n auto -q -p no:cacheprovider }

# ---------- 5. commit B: wave1 recovery + fixes + disabled ONNX filter ----------
git add -- ($newB + @("recovered", "models", "reports/entry_filter_report.json",
  "src/bananatrade/brain.py", "src/bananatrade/cli.py", "config/risk.yaml", "pyproject.toml",
  "tests/test_config_regime_ensemble.py"))
Assert-NoSecretsStaged
Run "commit B" { git commit -q -m "Restore wave1 modules from stash, fix doctor/test defects, add disabled ONNX entry filter" }

# ---------- 6. commit C: sizing fix + diagnosis ----------
git add -- ($newC + @("src/bananatrade/backtest/engine.py", "tests/test_backtest_realistic.py",
  "reports/strategy_diagnosis.json", "reports/strategy_diagnosis.md", "reports/windows_verify.log", ".gitignore"))
Assert-NoSecretsStaged
Run "commit C" { git commit -q -m "BacktestEngine: fractional quantity_step; add honest strategy diagnosis" }

Remove-Item -Recurse -Force $orig
git status --short | Select-Object -First 30
git log --oneline -4
Write-Host "Done. Nothing was pushed. Test results: $log" -ForegroundColor Green
