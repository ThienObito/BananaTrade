"""Allow-listed local task runner so the assistant can run tests / MT5 dry-runs on this PC.

Start it once (it keeps running until Ctrl+C):
    .\\.venv\\Scripts\\python scripts\\claude_runner.py

How it works: the assistant writes .claude_runner/request.json, e.g.
    {"id": 3, "task": "mt5_run", "symbol": "EURUSD"}
and this runner executes ONLY the matching fixed command below, writing the output to
.claude_runner/result_3.txt. Nothing else can be executed.

Safety (enforced here, independent of the request):
  * fixed allow-list of tasks; no shell, no arbitrary commands, no git, no pip;
  * BT_MT5_EXECUTION_ENABLED is forced to "false" -> MT5 runs are always dry-run
    (on top of the bot's own demo-only guard);
  * symbol must match ^[A-Za-z0-9._]{1,24}$; each task has a timeout.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOX = ROOT / ".claude_runner"
PY = sys.executable
SYMBOL_RE = re.compile(r"^[A-Za-z0-9._]{1,24}$")
TASKS = {
    # faulthandler_timeout dumps the stack of any test stuck > 60s, so a hang is diagnosable.
    "pytest": (lambda req: [PY, "-B", "-m", "pytest", "-n", "auto", "-q", "-p", "no:cacheprovider",
                            "-o", "faulthandler_timeout=60"], 600),
    "mt5_run": (lambda req: [PY, "-m", "bananatrade", "run", req["symbol"], "--broker", "mt5"], 180),
    "mt5_probe": (lambda req: [PY, str(ROOT / "scripts" / "mt5_probe.py"), req["symbol"]], 120),
}


def run(req: dict) -> str:
    task = req.get("task")
    if task not in TASKS:
        return f"REFUSED: unknown task {task!r}; allowed: {sorted(TASKS)}"
    if task != "pytest" and not SYMBOL_RE.match(str(req.get("symbol", ""))):
        return "REFUSED: invalid symbol"
    build, timeout = TASKS[task]
    cmd = build(req)
    env = {**os.environ, "BT_MT5_EXECUTION_ENABLED": "false", "PYTHONIOENCODING": "utf-8"}
    started = time.time()
    log = BOX / "current_output.log"
    # Output goes to a file, not pipes: on Windows, pytest-xdist workers inherit pipe handles,
    # so after a timeout kill the pipes never close and the runner would hang forever.
    with log.open("w", encoding="utf-8", errors="replace") as handle:
        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT)
        try:
            code = proc.wait(timeout=timeout)
            status = f"exit={code}"
        except subprocess.TimeoutExpired:
            # Kill the whole process tree (xdist workers included).
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
            proc.wait(timeout=30)
            status = f"TIMEOUT after {timeout}s (process tree killed)"
    body = f"{status}\n--- output ---\n{log.read_text(encoding='utf-8', errors='replace')}"
    return f"task={task} cmd={' '.join(cmd[1:])}\nseconds={time.time() - started:.1f}\n{body}"


def main() -> None:
    BOX.mkdir(exist_ok=True)
    req_path = BOX / "request.json"
    print(f"claude_runner ready; watching {req_path} (Ctrl+C to stop). Allowed: {sorted(TASKS)}")
    done: set[int] = set()
    while True:
        try:
            if req_path.exists():
                req = json.loads(req_path.read_text(encoding="utf-8"))
                rid = int(req.get("id", -1))
                if rid >= 0 and rid not in done:
                    done.add(rid)
                    print(f"[{time.strftime('%H:%M:%S')}] running #{rid}: {req.get('task')} {req.get('symbol', '')}")
                    out = run(req)
                    (BOX / f"result_{rid}.txt").write_text(out, encoding="utf-8")
                    print(f"[{time.strftime('%H:%M:%S')}] done #{rid}: {out.splitlines()[2] if len(out.splitlines()) > 2 else ''}")
        except (ValueError, OSError) as exc:
            print(f"bad request ignored: {exc}")
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("stopped")
