"""Run built-in benchmark cases safely.

Default mode is dry-run only: it compiles real plans, creates approval locks,
records evidence rows, and never calls a paid video vendor. Use --paid only
when real vendor/storage environment is configured.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from benchmark.batch_runner import missing_paid_benchmark_env, run_benchmark_case_definitions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CineForge benchmark cases.")
    parser.add_argument("--case-id", action="append", default=[], help="Case id to run. Can be repeated or comma-separated.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N selected cases.")
    parser.add_argument("--dry-run", action="store_true", help="Run dry-run only. This is the default and never calls a paid vendor.")
    parser.add_argument("--paid", action="store_true", help="Run paid renders. Requires real vendor/storage env.")
    parser.add_argument(
        "--evidence-path",
        default=str(BACKEND_ROOT / "data" / "benchmarks" / "evidence.jsonl"),
        help="JSONL evidence output path.",
    )
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--min-usable-rate", type=float, default=0.85)
    parser.add_argument("--max-hard-fail-rate", type=float, default=0.10)
    args = parser.parse_args()

    if args.dry_run and args.paid:
        parser.error("--dry-run cannot be combined with --paid")

    case_ids = _parse_case_ids(args.case_id)
    if args.paid:
        missing = missing_paid_benchmark_env()
        if missing:
            print(json.dumps({
                "status": "missing_env",
                "message": "Paid benchmark requires real vendor/storage env. No render job was queued.",
                "missing_env": missing,
                "vendor_calls_performed": False,
            }, ensure_ascii=False, sort_keys=True))
            return 2

    result = run_benchmark_case_definitions(
        case_ids=case_ids or None,
        limit=args.limit,
        evidence_path=args.evidence_path,
        dry_run_only=args.dry_run or not args.paid,
        paid_mode=args.paid,
        min_samples=args.min_samples,
        min_usable_rate=args.min_usable_rate,
        max_hard_fail_rate=args.max_hard_fail_rate,
    )
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _parse_case_ids(values: list[str]) -> set[str]:
    out: set[str] = set()
    for value in values:
        out.update(part.strip() for part in value.split(",") if part.strip())
    return out


if __name__ == "__main__":
    raise SystemExit(main())
