from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path when run directly as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from src.evaluation.task_a_eval import run_task_a_eval
from src.evaluation.task_b_eval import run_task_b_eval
from src.evaluation.dcr.dcr_classifier import (
    apply_task_a_classifications,
    apply_task_b_classifications,
)
from src.evaluation.reclassification import (
    run_task_a_reclassification,
    run_task_b_reclassification,
)
from src.evaluation.utils import (
    fetch_all_paginated,
    write_evaluation_outputs,
    VALID_CATEGORIES,
)
from src.db.supabase_client import get_supabase_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = "outputs/evaluation"

TASK_A_CSV = f"{OUTPUT_DIR}/task_a_results.csv"
TASK_A_JSON = f"{OUTPUT_DIR}/task_a_results.json"
TASK_A_SUMMARY = f"{OUTPUT_DIR}/task_a_summary.json"
TASK_B_CSV = f"{OUTPUT_DIR}/task_b_results.csv"
TASK_B_JSON = f"{OUTPUT_DIR}/task_b_results.json"
TASK_B_SUMMARY = f"{OUTPUT_DIR}/task_b_summary.json"
MANIFEST_PATH = f"{OUTPUT_DIR}/evaluation_manifest.json"


def _most_frequent(rows: list[dict], key: str) -> str | None:
    vals = [r.get(key) for r in rows if r.get(key)]
    if not vals:
        return None
    return Counter(vals).most_common(1)[0][0]


def _dcr_counts(rows: list[dict]) -> dict:
    return {
        "green": sum(1 for r in rows if r.get("dcr_classification") == "Green"),
        "yellow": sum(1 for r in rows if r.get("dcr_classification") == "Yellow"),
        "red": sum(1 for r in rows if r.get("dcr_classification") == "Red"),
        "unclassified": sum(1 for r in rows if r.get("dcr_classification") is None),
    }


def _fetch_product_snapshots(asins: list[str], supabase: Any) -> dict[str, dict]:
    if not asins:
        return {}
    result = {}
    chunk = 500
    for start in range(0, len(asins), chunk):
        rows = fetch_all_paginated(
            supabase,
            "amazon_product_metadata",
            filters=[("parent_asin", "in_", asins[start : start + chunk])],
        )
        for row in rows:
            result[row["parent_asin"]] = row
    return result


def _fetch_persona_train_asins(user_ids: list[str], supabase: Any) -> dict[str, list[str]]:
    if not user_ids:
        return {}
    result: dict[str, list[str]] = {}
    chunk = 500
    for start in range(0, len(user_ids), chunk):
        rows = fetch_all_paginated(
            supabase,
            "amazon_reviews",
            select="user_id,parent_asin",
            filters=[
                ("user_id", "in_", user_ids[start : start + chunk]),
                ("task_split", "eq", "persona_train"),
            ],
        )
        for row in rows:
            result.setdefault(row["user_id"], []).append(row["parent_asin"])
    return result


def _task_section(rows: list[dict], limit_applied: int | None) -> dict:
    success = [r for r in rows if r.get("status") == "success"]
    return {
        "users_evaluated": len(set(r.get("user_id") for r in success if r.get("user_id"))),
        "holdout_reviews_used": len(success),
        "limit_applied": limit_applied,
        "skipped": sum(1 for r in rows if r.get("status") == "skipped"),
        "errors": sum(1 for r in rows if r.get("status") == "error"),
    }


def run(args: argparse.Namespace) -> None:
    supabase = get_supabase_client()
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    rows_a: list[dict] = []
    rows_b: list[dict] = []
    summary_a: dict = {}
    summary_b: dict = {}
    run_a = args.task in ("a", "both")
    run_b = args.task in ("b", "both")

    if run_a:
        t0 = time.time()
        try:
            rows_a, summary_a = run_task_a_eval(
                categories=args.categories,
                limit=args.task_a_limit,
                skip_bertscore=args.skip_bertscore,
                supabase_client=supabase,
            )

            a_asins = list(set(r.get("parent_asin") for r in rows_a if r.get("parent_asin")))
            product_snapshots_a = _fetch_product_snapshots(a_asins, supabase)

            rows_a = apply_task_a_classifications(rows_a, product_snapshots_a, supabase)

            reclassification_a = run_task_a_reclassification(rows_a)
            summary_a["reclassification_analysis"] = reclassification_a

            write_evaluation_outputs(
                rows=rows_a, summary=summary_a,
                csv_path=TASK_A_CSV, json_path=TASK_A_JSON, summary_path=TASK_A_SUMMARY,
            )
            logger.info("Task A complete in %.1fs", time.time() - t0)
        except Exception:
            logger.exception("Task A failed")
            rows_a, summary_a = [], {}
            write_evaluation_outputs(
                rows=[], summary={},
                csv_path=TASK_A_CSV, json_path=TASK_A_JSON, summary_path=TASK_A_SUMMARY,
            )

    if run_b:
        t0 = time.time()
        try:
            rows_b, summary_b = run_task_b_eval(
                categories=args.categories,
                k=args.k,
                limit=args.task_b_limit,
                force_rerun=args.force_rerun,
                supabase_client=supabase,
            )

            b_asins = list(set(
                r.get("holdout_asin") or r.get("parent_asin")
                for r in rows_b if r.get("holdout_asin") or r.get("parent_asin")
            ))
            product_snapshots_b = _fetch_product_snapshots(b_asins, supabase)

            b_user_ids = list(set(r.get("user_id") for r in rows_b if r.get("user_id")))
            persona_train_asins = _fetch_persona_train_asins(b_user_ids, supabase)

            rows_b = apply_task_b_classifications(
                rows_b, product_snapshots_b, persona_train_asins, supabase,
            )

            reclassification_b = run_task_b_reclassification(rows_b)
            summary_b["reclassification_analysis"] = reclassification_b

            write_evaluation_outputs(
                rows=rows_b, summary=summary_b,
                csv_path=TASK_B_CSV, json_path=TASK_B_JSON, summary_path=TASK_B_SUMMARY,
            )
            logger.info("Task B complete in %.1fs", time.time() - t0)
        except Exception:
            logger.exception("Task B failed")
            rows_b, summary_b = [], {}
            write_evaluation_outputs(
                rows=[], summary={},
                csv_path=TASK_B_CSV, json_path=TASK_B_JSON, summary_path=TASK_B_SUMMARY,
            )

    all_rows = rows_a + rows_b
    a_counts = _dcr_counts(rows_a)
    b_counts = _dcr_counts(rows_b)

    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "categories_evaluated": args.categories,
        "task_a": _task_section(rows_a, args.task_a_limit),
        "task_b": _task_section(rows_b, args.task_b_limit),
        "k": args.k,
        "skip_bertscore": args.skip_bertscore,
        "force_rerun": args.force_rerun,
        "model_name": _most_frequent(all_rows, "model_name"),
        "prompt_version": _most_frequent(all_rows, "prompt_version"),
        "persona_version": _most_frequent(all_rows, "persona_version"),
        "embedding_model": _most_frequent(rows_b, "embedding_model"),
        "evaluation_command": " ".join(sys.argv),
        "output_files": {
            "task_a_results_csv": TASK_A_CSV,
            "task_a_results_json": TASK_A_JSON,
            "task_a_summary_json": TASK_A_SUMMARY,
            "task_b_results_csv": TASK_B_CSV,
            "task_b_results_json": TASK_B_JSON,
            "task_b_summary_json": TASK_B_SUMMARY,
            "manifest": MANIFEST_PATH,
        },
        "failure_counts": {
            "task_a_green": a_counts["green"],
            "task_a_yellow": a_counts["yellow"],
            "task_a_red": a_counts["red"],
            "task_a_unclassified": a_counts["unclassified"],
            "task_b_green": b_counts["green"],
            "task_b_yellow": b_counts["yellow"],
            "task_b_red": b_counts["red"],
            "task_b_unclassified": b_counts["unclassified"],
        },
    }

    Path(MANIFEST_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(MANIFEST_PATH).write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8",
    )
    logger.info("Evaluation manifest written to %s", MANIFEST_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run iRecommend evaluation pipeline.")
    parser.add_argument("--task", choices=["a", "b", "both"], default="both")
    parser.add_argument("--categories", nargs="+", default=list(VALID_CATEGORIES))
    parser.add_argument("--task-a-limit", type=int, default=None)
    parser.add_argument("--task-b-limit", type=int, default=None)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--skip-bertscore", action="store_true", default=False)
    parser.add_argument("--force-rerun", action="store_true", default=False)

    args = parser.parse_args()

    for cat in args.categories:
        if cat not in VALID_CATEGORIES:
            parser.error(f"Invalid category: {cat!r}. Must be one of {VALID_CATEGORIES}")

    run(args)


if __name__ == "__main__":
    main()
