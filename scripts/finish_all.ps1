# Finish the git work on branch recover-wave1-onnx-filter.
# Run from the project root:   powershell -ExecutionPolicy Bypass -File scripts\finish_all.ps1
#   1. Commit the UTF-8 log fix in scripts/protect_and_verify.ps1 (and this script).
#   2. Track the remaining untracked project files: BLOCKED.md, PROGRESS.md, docs/, company/,
#      data/history/*.csv + *.validation.json, runtime-check.json.
#      .env, .venv, *.db, caches stay excluded; aborts if any of them gets staged.
#   3. Shows the result, then ASKS before pushing (default: no push).

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$branch = "recover-wave1-onnx-filter"

# NOTE: must not be named "Git": PowerShell is case-insensitive, so a function "Git"
# shadows git.exe and every plain `git ...` call would recurse into this function.
function Invoke-Git([string[]]$a) {
    $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $out = & git.exe @a 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE; $ErrorActionPreference = $prev
    $out | ForEach-Object { Write-Host $_ }
    if ($code -ne 0) { throw "git $($a -join ' ') failed ($code)" }
}
function Assert-NoSecretsStaged {
    $bad = git diff --cached --name-only | Where-Object { $_ -match '(^|/)\.env$|^\.venv/|\.db$|__pycache__|\.pyc|(^|/)\.orig_for_commit_a/' }
    if ($bad) { git reset -q; throw "Refusing to commit forbidden paths: $($bad -join ', ')" }
}

if ((git rev-parse --abbrev-ref HEAD) -ne $branch) { throw "Not on $branch; run: git checkout $branch" }

# ---- 1. script fixes ----
Invoke-Git @("add", "--", "scripts/protect_and_verify.ps1", "scripts/finish_all.ps1")
Assert-NoSecretsStaged
if (git diff --cached --name-only) { Invoke-Git @("commit", "-q", "-m", "Scripts: UTF-8 verification log; add finish_all.ps1") }

# ---- 2. remaining project files ----
$extra = @("BLOCKED.md", "PROGRESS.md", "docs", "company", "runtime-check.json",
           "data/history/*.csv", "data/history/*.validation.json") |
         Where-Object { Test-Path $_ }
if ($extra) { Invoke-Git (@("add", "--") + $extra) }
Assert-NoSecretsStaged
$staged = git diff --cached --name-only
if ($staged) {
    Write-Host "`nFiles to commit:" -ForegroundColor Cyan; $staged | ForEach-Object { "  $_" }
    Invoke-Git @("commit", "-q", "-m", "Track project docs, progress notes and validated history data")
}

Write-Host "`nUntracked files left (by design or not yet decided):" -ForegroundColor Cyan
git status --short | Select-Object -First 40
git log --oneline -6

# ---- 3. push only with explicit confirmation ----
$remote = git remote
if (-not $remote) { Write-Host "No git remote configured; nothing to push."; exit 0 }
$answer = Read-Host "`nPush branch '$branch' to '$($remote | Select-Object -First 1)'? (y/N)"
if ($answer -match '^(y|yes|c|co)$') {
    Invoke-Git @("push", "-u", ($remote | Select-Object -First 1), $branch)
    Write-Host "Pushed $branch. main was not touched." -ForegroundColor Green
} else {
    Write-Host "Not pushed. Later: git push -u origin $branch" -ForegroundColor Yellow
}
