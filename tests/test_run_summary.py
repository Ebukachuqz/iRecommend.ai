import json

from src.utils.run_summary import build_run_summary, save_run_summary


def test_save_run_summary_creates_directory_and_json(tmp_path) -> None:
    output_dir = tmp_path / "missing" / "summaries"
    summary = build_run_summary(
        category="All_Beauty",
        mode="dry_run",
        args={"category": "All_Beauty"},
        result={"uploaded_reviews": 0},
        timestamp="20260101T000000Z",
    )

    path = save_run_summary(output_dir, "All_Beauty", "dry_run", summary, timestamp=summary["timestamp"])

    assert path.exists()
    assert path.name == "All_Beauty_dry_run_20260101T000000Z.json"
    assert json.loads(path.read_text(encoding="utf-8")) == summary
