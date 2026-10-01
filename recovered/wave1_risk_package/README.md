# Recovered: wave-1 `bananatrade.risk` package (archived, NOT on the import path)

Source: git stash `stash@{0}` ("On main: wave1-original-backup", commit 6f21f15),
untracked-files parent `c3a6caa` (2026-09-26). Restored with
`git checkout c3a6caa -- src/bananatrade/risk` and verified byte-for-byte: compiling these
files with CPython 3.14 yields bytecode identical to the orphaned
`src/bananatrade/risk/__pycache__/*.cpython-314.pyc` (source sizes 288/3214/1855 match).

Why it is archived here instead of `src/bananatrade/risk/`:
the live code uses the single module `src/bananatrade/risk.py` (`RiskEngine.approve/check`,
`RiskConfig`). A package directory `risk/` with an `__init__.py` takes precedence over
`risk.py` on import, so restoring it in place makes `from .risk import RiskEngine` resolve
to this older, API-incompatible engine and breaks `web_server`, `paper_broker` and 5 test
modules. The `risk/` folder that held only `__pycache__` was harmless (no `__init__.py`,
so Python ignored it and imported `risk.py`).
