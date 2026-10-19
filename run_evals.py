#!/usr/bin/env python3
"""Unified eval runner.

Sends each task's eval harness (Task 1/3: evals/run_evals.py, Task 2: evals/runEvals.ts
and evals/runHoldout.ts) through one model matrix and collects every report into
shared-docs/evals/ plus a summary.json.

Model matrix (live runs, via OpenRouter):
  cheap  anthropic/claude-haiku-4.5
  strong anthropic/claude-sonnet-4.6
Baseline runs (offline, zero live calls):
  Task 1 fake chat + fake embeddings (--store memory), Task 2 rule classifier,
  Task 3 rules extractor.

Cost in every report is priced from shared-docs/evals/pricing.json (tokens x table,
source + retrieval date in the report). The API key is read from the environment or
task .env files and is never printed or written to any report.

Exit codes: 0 = every run completed (case failures are data, not crashes),
1 = at least one run crashed (harness error >=2, timeout, or missing report).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "shared-docs" / "evals"
LOGS = OUT / "logs"
PRICING = OUT / "pricing.json"
TASK_DIRS = {1: ROOT / "task1-knowledge-brain", 2: ROOT / "task2-inbox-agent", 3: ROOT / "task3-meeting-to-scope"}

CHEAP = "anthropic/claude-haiku-4.5"
STRONG = "anthropic/claude-sonnet-4.6"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

SECRET_ENV_KEYS = ("OPENROUTER_API_KEY", "LLM_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY")


def load_openrouter_key() -> str | None:
    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if env_key:
        return env_key
    for env_file in (ROOT / "task1-knowledge-brain" / ".env", ROOT / "task2-inbox-agent" / ".env"):
        try:
            lines = env_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    return None


def _base_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in (
        "LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "OPENROUTER_API_KEY",
        "EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "EMBEDDING_DIMENSIONS",
        "EVAL_MODEL_CHEAP", "EVAL_MODEL_STRONG", "EVAL_MODELS", "EVAL_CASE_IDS",
        "LLM_MIN_DELAY_SECONDS", "LLM_MIN_DELAY_MS", "LLM_REQUEST_DELAY_MS",
    ):
        env.pop(key, None)
    return env


def live_env(model: str, key: str) -> dict[str, str]:
    env = _base_env()
    env.update({
        "LLM_PROVIDER": "openrouter",
        "LLM_BASE_URL": OPENROUTER_BASE,
        "LLM_MODEL": model,
        "LLM_API_KEY": key,
        "OPENROUTER_API_KEY": key,
        "LLM_MIN_DELAY_SECONDS": "0.2",
        "LLM_MIN_DELAY_MS": "200",
        "LLM_REQUEST_DELAY_MS": "100",
    })
    return env


def baseline_env(task: int) -> dict[str, str]:
    env = _base_env()
    env.update({"LLM_MIN_DELAY_SECONDS": "0", "LLM_MIN_DELAY_MS": "0", "LLM_REQUEST_DELAY_MS": "0"})
    if task == 1:
        env.update({
            "LLM_PROVIDER": "fake",
            "EMBEDDING_PROVIDER": "fake",
            "EMBEDDING_MODEL": "fake-embedding",
            "EMBEDDING_DIMENSIONS": "64",
        })
    return env


def npm_argv(args: list[str]) -> list[str]:
    return (["cmd", "/c", "npm"] + args) if os.name == "nt" else (["npm"] + args)


def build_plan(task: int, split: str, model: str | None, key: str | None) -> dict:
    label = "baseline" if model is None else model.rsplit("/", 1)[-1]
    t2_split = "holdout" if split == "holdout" else "tuning"
    effective_split = t2_split if task == 2 else split
    report = OUT / f"task{task}-{effective_split}-{label}.json"
    plan: dict = {
        "task": task,
        "split": effective_split,
        "mode": "baseline" if model is None else "live",
        "model": model,
        "label": label,
        "report": report,
        "log": LOGS / f"task{task}-{effective_split}-{label}.log",
        "collector": None,
        "env": baseline_env(task) if model is None else live_env(model, key or ""),
        "cwd": TASK_DIRS[task],
    }
    if task == 1:
        plan["cmd"] = [sys.executable, "evals/run_evals.py", "--store", "memory",
                       "--split", split, "--json-report", str(report)]
    elif task == 3:
        plan["cmd"] = [sys.executable, "evals/run_evals.py",
                       "--extractor", "rules" if model is None else "llm",
                       "--split", split, "--report", str(report)]
    else:
        if effective_split == "holdout":
            if model is None:
                plan["cmd"] = npm_argv(["run", "evals:holdout:rules"])
                plan["collector"] = TASK_DIRS[2] / "evals" / "reports" / "holdout-20-rules-mock.json"
            else:
                plan["env"].update({"EVAL_MODEL_CHEAP": CHEAP, "EVAL_MODEL_STRONG": STRONG, "EVAL_MODELS": model})
                plan["cmd"] = npm_argv(["run", "evals:holdout"])
                plan["collector"] = TASK_DIRS[2] / "evals" / "reports" / f"holdout-20-{model}.json"
        else:
            plan["cmd"] = npm_argv(["run", "evals"] + ([] if model is None else ["--", "--classifier=llm"]))
            plan["collector"] = TASK_DIRS[2] / "evals" / "report.json"
    plan["overrides"] = sorted(k for k, v in plan["env"].items() if os.environ.get(k) != v)
    return plan


def summarize_report(report: dict, task: int) -> dict:
    cost = report.get("cost") or {}
    metrics = report.get("metrics") or {}
    if task == 2 and "estimated_cost_usd" in metrics:
        cost_usd = metrics.get("estimated_cost_usd")
        input_tokens = metrics.get("input_tokens")
        output_tokens = metrics.get("output_tokens")
        cost_basis = metrics.get("cost_basis")
    else:
        cost_usd = cost.get("cost_usd")
        input_tokens = cost.get("input_tokens")
        output_tokens = cost.get("output_tokens")
        cost_basis = cost.get("cost_basis")
    passed = report.get("passed")
    return {
        "passed": passed,
        "total": report.get("total"),
        "cost_usd": cost_usd,
        "cost_basis": cost_basis,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def run_one(plan: dict, index: int, total: int) -> dict:
    head = f"[{index}/{total}] task{plan['task']} {plan['split']} {plan['label']}"
    print(f"{head}: running { ' '.join(plan['cmd']) } (cwd {plan['cwd'].name})", flush=True)
    started = time.monotonic()
    status = "ok"
    exit_code = None
    note = None
    LOGS.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            plan["cmd"], cwd=plan["cwd"], env=plan["env"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace", timeout=3600,
        )
        exit_code = completed.returncode
        log_text = completed.stdout or ""
    except subprocess.TimeoutExpired as exc:
        status = "crashed"
        note = "timeout after 3600s"
        log_text = _timeout_output(exc)
    except OSError as exc:
        status = "crashed"
        note = f"could not start process: {exc}"
        log_text = ""
    duration = round(time.monotonic() - started, 1)
    plan["log"].write_text(log_text, encoding="utf-8")

    report_path = plan["report"]
    if plan["collector"] is not None and exit_code is not None and exit_code < 2 and plan["collector"].exists():
        report_path.write_bytes(plan["collector"].read_bytes())

    if status != "crashed":
        if exit_code is None or exit_code >= 2 or not report_path.exists():
            status = "crashed"
            note = note or f"harness exit={exit_code} and report missing" if not report_path.exists() else f"harness exit={exit_code}"
        elif exit_code == 0:
            status = "ok"
        else:
            status = "fail"

    record = {
        "task": plan["task"],
        "split": plan["split"],
        "mode": plan["mode"],
        "model": plan["model"],
        "label": plan["label"],
        "status": status,
        "harness_exit": exit_code,
        "duration_s": duration,
        "report": str(report_path.relative_to(ROOT)) if report_path.exists() else None,
        "log": str(plan["log"].relative_to(ROOT)),
        "env_keys": plan["overrides"],
        "note": note,
    }
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            record.update(summarize_report(report, plan["task"]))
        except (json.JSONDecodeError, OSError) as exc:
            record["status"] = "crashed"
            record["note"] = f"report unreadable: {exc}"
    else:
        record.update({"passed": None, "total": None, "cost_usd": None,
                       "cost_basis": None, "input_tokens": None, "output_tokens": None})

    if isinstance(record["passed"], bool):
        score_text = "thresholds=" + ("PASS" if record["passed"] else "FAIL")
    elif record["total"]:
        score_text = f"{record['passed']}/{record['total']}"
    else:
        score_text = str(record["passed"])
    cost_text = f"cost_usd={record['cost_usd']}"
    print(f"{head}: {record['status']} exit={exit_code} {score_text} {cost_text} ({duration}s)", flush=True)
    if record["status"] == "crashed":
        tail = "\n".join(log_text.splitlines()[-12:])
        print(f"--- last log lines ({plan['log'].name}) ---\n{tail}\n---", flush=True)
    return record


def _timeout_output(exc: subprocess.TimeoutExpired) -> str:
    output = exc.stdout
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output or ""


def mask_env_for_display(env: dict[str, str]) -> dict[str, str]:
    return {k: ("***" if k in SECRET_ENV_KEYS and v else v) for k, v in sorted(env.items())}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all task eval harnesses into shared-docs/evals/")
    parser.add_argument("--tasks", default="1,2,3", help="comma list of tasks to run (default 1,2,3)")
    parser.add_argument("--split", choices=["tuning", "holdout", "all"], default="tuning")
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="print the run plan and exit")
    args = parser.parse_args()

    tasks = [int(t) for t in args.tasks.replace(" ", "").split(",") if t]
    if not tasks or any(t not in TASK_DIRS for t in tasks):
        parser.error(f"--tasks must be a subset of {sorted(TASK_DIRS)}")
    if args.split == "holdout" and 2 in tasks and not args.skip_baseline:
        pass  # task 2 holdout baseline = rules harness, supported

    key = load_openrouter_key()
    need_live = not args.skip_live
    if need_live and not key:
        print("error: no OPENROUTER_API_KEY found in environment or task .env files; "
              "use --skip-live for offline baseline runs", file=sys.stderr)
        return 1

    pricing = None
    if PRICING.exists():
        pricing = json.loads(PRICING.read_text(encoding="utf-8"))

    models: list[str | None] = []
    if not args.skip_baseline:
        models.append(None)
    if not args.skip_live:
        models.extend([CHEAP, STRONG])

    plans = [build_plan(task, args.split, model, key) for task in tasks for model in models]

    if args.dry_run:
        for plan in plans:
            print(f"task{plan['task']} {plan['split']} {plan['label']}")
            print(f"  cwd:  {plan['cwd']}")
            print(f"  cmd:  {' '.join(plan['cmd'])}")
            overrides = {k: plan["env"][k] for k in plan["overrides"]}
            print(f"  env:  {json.dumps(mask_env_for_display(overrides), sort_keys=True)}")
            print(f"  ->    {plan['report']}")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"eval run start {started_at} split={args.split} tasks={tasks} "
          f"models={[m or 'baseline' for m in models]}")
    if pricing:
        print(f"pricing table: {PRICING.relative_to(ROOT)} (source: {pricing.get('source')}, "
              f"retrieved: {pricing.get('retrieved_at')})")

    runs = [run_one(plan, i + 1, len(plans)) for i, plan in enumerate(plans)]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started_at,
        "split": args.split,
        "tasks": tasks,
        "models": {"cheap": CHEAP, "strong": STRONG},
        "pricing_table": str(PRICING.relative_to(ROOT)) if PRICING.exists() else None,
        "pricing_source": pricing.get("source") if pricing else None,
        "pricing_retrieved_at": pricing.get("retrieved_at") if pricing else None,
        "key_source": "environment" if os.environ.get("OPENROUTER_API_KEY") else ("task .env" if key else None),
        "runs": runs,
    }
    summary_path = OUT / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    crashed = [r for r in runs if r["status"] == "crashed"]
    print(f"\n{len(runs) - len(crashed)}/{len(runs)} runs completed; summary: {summary_path.relative_to(ROOT)}")
    for record in runs:
        score = f"{record['passed']}/{record['total']}" if record["total"] else str(record["passed"])
        print(f"  task{record['task']} {record['label']}: {record['status']} "
              f"passed={score} cost_usd={record['cost_usd']}")
    if crashed:
        print(f"crashed runs: {', '.join(r['label'] for r in crashed)} (see logs in {LOGS.relative_to(ROOT)})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
