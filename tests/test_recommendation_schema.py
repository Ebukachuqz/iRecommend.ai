from pathlib import Path

from src.task_b_recommendation.schema import RerankerOutput


def test_reranker_output_validates() -> None:
    output = RerankerOutput.model_validate(
        {
            "recommendations": [
                {
                    "parent_asin": "asin-1",
                    "rank": 1,
                    "title": "Gentle cream",
                    "reason": "Matches the user's preference for gentle products.",
                    "confidence": 0.8,
                    "evidence": ["liked gentle products"],
                    "score_breakdown": {"final_score": 0.8},
                }
            ]
        }
    )

    assert output.recommendations[0].rank == 1


def test_no_legacy_split_flag_reference_remains() -> None:
    needle = "used_for" + "_persona"
    root = Path(__file__).resolve().parents[1]
    scan_roots = [root / "src", root / "scripts", root / "docs", root / "tests", root / "README.md"]
    matches = [
        path
        for scan_root in scan_roots
        for path in ([scan_root] if scan_root.is_file() else scan_root.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and needle in path.read_text(encoding="utf-8", errors="ignore")
    ]

    assert matches == []


def test_no_review_category_column_reference_remains() -> None:
    needle = "amazon_reviews" + ".category"
    root = Path(__file__).resolve().parents[1]
    scan_roots = [root / "src", root / "scripts", root / "docs", root / "tests", root / "README.md"]
    matches = [
        path
        for scan_root in scan_roots
        for path in ([scan_root] if scan_root.is_file() else scan_root.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and needle in path.read_text(encoding="utf-8", errors="ignore")
    ]

    assert matches == []
