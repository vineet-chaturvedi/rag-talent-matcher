"""
Step 14: every evaluation in one command, with a saved report and a comparison with the last one.

    suite                 script                                   needs
    extraction (code)     evaluate_real_resumes --offline          nothing
    extraction (model)    evaluate_real_resumes                    Ollama, ~10 min   (only with --with-model-extraction)
    retrieval (real)      evaluate_real_retrieval                  Ollama, R1-R9 loaded (scripts.load_real_resumes)
    retrieval (samples)   evaluate_retrieval                       the server + a login
    matching (samples)    evaluate_matching --judge-top-n 0        the server + a login   (rule score only: fast)
    agent                 evaluate_agent                           Ollama, ~1-2 min per question on CPU

Each suite runs as its own process (exactly as if you typed its command), its numbers are read from its output,
and everything goes into evaluation/reports/all-<date-time>.json and .md. Every number is "higher is better";
any number lower than in the previous report is flagged as a REGRESSION, so a change to a prompt, a weight or the
chunking is measured, not guessed.

Run from backend/ (the server running in another terminal for the two sample suites):
    python -m scripts.evaluate_all                       # everything except the slow model extraction
    python -m scripts.evaluate_all --skip agent          # e.g. after a change that can't affect the agent
    python -m scripts.evaluate_all --with-model-extraction
Exit code 0 = every suite ran, passed its own bar and nothing got worse.
"""
import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
REPORTS = BACKEND / "evaluation" / "reports"
TOLERANCE = 0.005          # rounding noise: 0.83 -> 0.825 is not a regression


def _num(pattern: str, text: str, *groups: int) -> list[float] | None:
    m = None
    for m in re.finditer(pattern, text, re.MULTILINE):
        pass                                   # the LAST match: summaries come at the end
    return [float(m.group(g)) for g in groups] if m else None


def parse_extraction(out: str) -> dict:
    v = _num(r"^(\d+) passed, (\d+) failed", out, 1, 2)
    return {"checks_passed_share": round(v[0] / (v[0] + v[1]), 4)} if v else {}


def parse_real_retrieval(out: str) -> dict:
    v = _num(r"^\s+hybrid\s+(\d+)/(\d+)\s+([\d.]+)\s+([\d.]+)\s*$", out, 1, 2, 3, 4)
    return {"hybrid_hit@3": round(v[0] / v[1], 4), "hybrid_R@5": v[2], "hybrid_MRR": v[3]} if v else {}


def parse_retrieval(out: str) -> dict:
    tail = out.split("=== Average", 1)[-1] if "=== Average" in out else ""
    v = _num(r"^\s+hybrid\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$", tail, 1, 2, 3)
    return {"hybrid_R@5": v[0], "hybrid_R@10": v[1], "hybrid_MRR": v[2]} if v else {}


def parse_matching(out: str) -> dict:
    v = _num(r"=== Average over \d+ roles: ndcg@5 ([\d.]+)\s+mrr ([\d.]+)\s+pairs ([\d.]+)", out, 1, 2, 3)
    return {"nDCG@5": v[0], "MRR": v[1], "pairs": v[2]} if v else {}


def parse_agent(out: str) -> dict:
    v = _num(r"^Cases: (\d+)/(\d+) passed.*?checks (\d+)/(\d+)", out, 1, 2, 3, 4)
    return {"cases_passed_share": round(v[0] / v[1], 4), "checks_passed_share": round(v[2] / v[3], 4)} if v else {}


# name -> (command, parser, needs the server, slow/optional)
SUITES = {
    "extraction-code": (["scripts.evaluate_real_resumes", "--offline"], parse_extraction, False, False),
    "extraction-model": (["scripts.evaluate_real_resumes"], parse_extraction, False, True),
    "retrieval-real": (["scripts.evaluate_real_retrieval"], parse_real_retrieval, False, False),
    "retrieval-samples": (["scripts.evaluate_retrieval"], parse_retrieval, True, False),
    "matching-samples": (["scripts.evaluate_matching", "--judge-top-n", "0"], parse_matching, True, False),
    "agent": (["scripts.evaluate_agent", "--no-report"], parse_agent, False, False),
}


def server_up(base_url: str) -> bool:
    try:
        return httpx.get(f"{base_url}/api/health", timeout=5).status_code == 200
    except httpx.HTTPError:
        return False


def previous_results() -> dict[str, dict]:
    """For each suite, its numbers in the most recent report that ran it (a --only run doesn't hide older ones)."""
    latest: dict[str, dict] = {}
    for path in sorted(REPORTS.glob("all-*.json"), reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for name, suite in report.get("suites", {}).items():
            if name not in latest and suite.get("metrics"):
                latest[name] = {"created": report.get("created"), "metrics": suite["metrics"]}
    return latest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--skip", nargs="*", default=[], choices=list(SUITES), help="suites to leave out")
    parser.add_argument("--only", nargs="*", choices=list(SUITES), help="run only these suites")
    parser.add_argument("--with-model-extraction", action="store_true", help="also re-extract R1-R9 with the model")
    parser.add_argument("--note", default="", help="what changed, saved in the report (e.g. 'prompt v4')")
    args = parser.parse_args()

    chosen = [s for s in SUITES if (not args.only or s in args.only) and s not in args.skip
              and (args.only or not SUITES[s][3] or args.with_model_extraction)]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if any(SUITES[s][2] for s in chosen):
        if server_up(args.base_url):
            if not env.get("RTM_EMAIL"):
                env["RTM_EMAIL"] = input("Portal email (for the sample suites): ").strip()
            if not env.get("RTM_PASSWORD"):
                env["RTM_PASSWORD"] = getpass.getpass("Password: ")
        else:
            print(f"The server is not running at {args.base_url}: the sample suites will be skipped.\n")

    before = previous_results()
    suites: dict[str, dict] = {}
    for name in chosen:
        command, parse, needs_server, _ = SUITES[name]
        if needs_server and not server_up(args.base_url):
            suites[name] = {"status": "skipped", "reason": "server not running"}
            print(f"- {name}: skipped (server not running)")
            continue
        extra = ["--base-url", args.base_url] if needs_server else []
        print(f"- {name}: running {' '.join(command)} ...", flush=True)
        started = time.perf_counter()
        proc = subprocess.run([sys.executable, "-m", *command, *extra], cwd=BACKEND, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = proc.stdout + proc.stderr
        metrics = parse(out)
        status = "passed" if proc.returncode == 0 and metrics else "failed" if metrics else "error"
        suites[name] = {"status": status, "exit_code": proc.returncode, "seconds": round(time.perf_counter() - started),
                        "metrics": metrics, "output_tail": out.strip().splitlines()[-25:]}
        shown = "  ".join(f"{k} {v}" for k, v in metrics.items()) or "no numbers found (see the report)"
        print(f"  {status.upper()}  {shown}  ({suites[name]['seconds']} s)")

    # ---- compare with the previous report
    regressions = []
    for name, now in suites.items():
        old = (before.get(name) or {}).get("metrics") or {}
        for key, value in (now.get("metrics") or {}).items():
            if key in old and value < old[key] - TOLERANCE:
                regressions.append(f"{name} {key}: {old[key]} -> {value} (report of {before[name]['created']})")

    created = datetime.now()
    report = {"kind": "all", "created": created.isoformat(timespec="seconds"), "note": args.note,
              "compared_with": {n: b["created"] for n, b in before.items() if n in suites},
              "regressions": regressions, "suites": suites}
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem = REPORTS / f"all-{created:%Y%m%d-%H%M%S}"
    stem.with_suffix(".json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown(report, before), encoding="utf-8")

    print()
    if regressions:
        print("REGRESSIONS (lower than the last report that ran the suite):")
        for r in regressions:
            print("  " + r)
    elif report["compared_with"]:
        print("No regressions against the previous reports.")
    else:
        print("First report: nothing to compare with yet.")
    print(f"Report: {stem.with_suffix('.md').relative_to(BACKEND)}")
    bad = [n for n, s in suites.items() if s["status"] in ("failed", "error")]
    return 0 if not bad and not regressions else 1


def markdown(report: dict, before: dict[str, dict]) -> str:
    lines = [f"# Evaluation report {report['created']}", ""]
    if report["note"]:
        lines += [f"Change: {report['note']}", ""]
    lines += ["| Suite | Status | Numbers | Before | Time |", "|---|---|---|---|---|"]
    for name, s in report["suites"].items():
        old = (before.get(name) or {}).get("metrics") or {}
        now = s.get("metrics") or {}
        nums = ", ".join(f"{k} {v}" for k, v in now.items()) or s.get("reason", "-")
        was = ", ".join(f"{k} {old[k]}" for k in now if k in old) or "-"
        lines.append(f"| {name} | {s['status']} | {nums} | {was} | {s.get('seconds', '-')} s |")
    lines += ["", "**Regressions:** " + ("; ".join(report["regressions"]) if report["regressions"] else "none")]
    for name, s in report["suites"].items():
        if s["status"] in ("failed", "error"):
            lines += ["", f"## {name}: last lines of output", "```", *s.get("output_tail", []), "```"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
