import json

from scripts import create_holdout_split
from scripts import embed_products
from scripts import ingest_amazon as ingest_amazon_script
from scripts import build_user_preference_vectors as build_user_preference_vectors_script
from scripts import run_task_b_recommendation as run_task_b_script
from scripts import regenerate_personas as regenerate_personas_script
from scripts import regenerate_personas

build_holdout_updates = create_holdout_split.build_holdout_updates


def make_review(user_id: str, index: int, parent_asin: str = "asin-1") -> dict:
    return {
        "review_id": f"{user_id}-r{index:02d}",
        "user_id": user_id,
        "parent_asin": parent_asin,
        "rating": 5,
        "timestamp": f"2024-01-{index + 1:02d}T00:00:00Z",
        "task_split": "persona_train",
    }


def split_counts_for_updates(updates: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for update in updates:
        counts[update["task_split"]] = counts.get(update["task_split"], 0) + 1
    return counts


def test_holdout_split_uses_ratio_for_twelve_reviews() -> None:
    updates = build_holdout_updates([make_review("u1", index) for index in range(12)])

    assert split_counts_for_updates(updates) == {
        "persona_train": 8,
        "task_a_holdout": 2,
        "task_b_holdout": 2,
    }


def test_holdout_split_is_deterministic() -> None:
    reviews = [make_review("u1", index) for index in range(12)]

    assert build_holdout_updates(reviews) == build_holdout_updates(list(reversed(reviews)))


def test_holdout_split_is_per_user_not_global() -> None:
    updates = build_holdout_updates(
        [make_review("u1", index) for index in range(12)]
        + [make_review("u2", index) for index in range(12)]
    )

    by_user = {"u1": [], "u2": []}
    for update in updates:
        by_user[update["review_id"].split("-")[0]].append(update)
    assert split_counts_for_updates(by_user["u1"]) == {
        "persona_train": 8,
        "task_a_holdout": 2,
        "task_b_holdout": 2,
    }
    assert split_counts_for_updates(by_user["u2"]) == {
        "persona_train": 8,
        "task_a_holdout": 2,
        "task_b_holdout": 2,
    }


def test_holdout_split_requires_overwrite_when_already_split() -> None:
    reviews = [make_review("u1", index) for index in range(12)]
    reviews[0]["task_split"] = "task_a_holdout"

    try:
        create_holdout_split.ensure_overwrite_allowed(reviews, overwrite=False)
    except ValueError as exc:
        assert "--overwrite" in str(exc)
    else:
        raise AssertionError("existing split should require --overwrite")


def test_holdout_split_category_filter_uses_project_category_only() -> None:
    assert create_holdout_split.product_matches_category(
        {"parent_asin": "p1", "category": "All_Beauty"},
        "All_Beauty",
    )
    assert not create_holdout_split.product_matches_category(
        {"parent_asin": "p2", "categories": [["Beauty", "Skin Care"]]},
        "Skin Care",
    )
    assert not create_holdout_split.product_matches_category(
        {"parent_asin": "p3", "main_category": "Electronics"},
        "Electronics",
    )


class QueryRecorder:
    def __init__(self) -> None:
        self.filters = []
        self.execute_count = 0

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def range(self, _start, _end):
        return self

    def execute(self):
        self.execute_count += 1
        data = [{"user_id": "u1"}] if self.execute_count == 1 else []
        return type("Response", (), {"data": data})()


class ClientRecorder:
    def __init__(self) -> None:
        self.query = QueryRecorder()

    def table(self, _name):
        return self.query


def test_regenerate_user_lookup_does_not_filter_by_category(monkeypatch) -> None:
    client = ClientRecorder()
    monkeypatch.setattr(regenerate_personas, "get_supabase_client", lambda: client)

    assert regenerate_personas.fetch_user_ids() == ["u1"]
    assert not any(column == "category" for column, _value in client.query.filters)


class PersonaGeneratorRecorder:
    def __init__(self) -> None:
        self.calls = []
        self.settings = type(
            "Settings",
            (),
            {
                "groq_model": "test-model",
                "persona_prompt_version": "test-prompt",
            },
        )()

    def regenerate_persona(self, user_id, category, max_reviews=10, store=True):
        self.calls.append((user_id, category, max_reviews, store))
        if user_id == "bad":
            raise RuntimeError("boom")
        return {"source_review_ids": ["r1", "r2"], "review_count_available": 15, "review_count_used": max_reviews}


def test_regenerate_personas_script_logs_progress_and_failures(monkeypatch, capsys, tmp_path) -> None:
    recorder = PersonaGeneratorRecorder()
    monkeypatch.setattr(regenerate_personas_script, "fetch_user_ids", lambda: ["good", "bad"])
    monkeypatch.setattr(regenerate_personas_script, "PersonaGenerator", lambda: recorder)
    monkeypatch.setattr(
        "sys.argv",
        ["regenerate_personas.py", "--category", "All_Beauty", "--output-dir", str(tmp_path)],
    )

    regenerate_personas_script.main()

    assert recorder.calls == [("good", "All_Beauty", 10, True), ("bad", "All_Beauty", 10, True)]
    output = capsys.readouterr().out
    assert "[persona] Starting persona regeneration: category=All_Beauty, users=2" in output
    assert "[persona] Processing user 1/2: user_id=good" in output
    assert "[persona] Persona generation succeeded:" in output
    assert "[persona] Persona generation failed: user_id=bad, error=boom" in output
    assert "[persona] Persona regeneration complete: succeeded=1, failed=1, total=2" in output
    assert "[persona] Run summary saved:" in output
    summary_files = list(tmp_path.glob("All_Beauty_upsert_*.json"))
    assert len(summary_files) == 1
    summary = json.loads(summary_files[0].read_text(encoding="utf-8"))
    assert summary["category"] == "All_Beauty"
    assert summary["args"]["category"] == "All_Beauty"
    assert summary["result"]["personas_generated"] == 1
    assert summary["result"]["personas_upserted"] == 1
    assert summary["result"]["review_count_available"] == 15
    assert summary["result"]["review_count_used"] == 10
    assert summary["result"]["user_review_counts"][0]["source_review_ids"] == ["r1", "r2"]
    assert summary["result"]["failed_users"] == 1
    assert summary["result"]["failure_reasons"] == [{"user_id": "bad", "error": "boom"}]


def test_regenerate_personas_script_max_reviews_override(monkeypatch, tmp_path) -> None:
    recorder = PersonaGeneratorRecorder()
    monkeypatch.setattr(regenerate_personas_script, "fetch_user_ids", lambda: ["good"])
    monkeypatch.setattr(regenerate_personas_script, "PersonaGenerator", lambda: recorder)
    monkeypatch.setattr(
        "sys.argv",
        [
            "regenerate_personas.py",
            "--category",
            "All_Beauty",
            "--max-reviews-per-user",
            "6",
            "--output-dir",
            str(tmp_path),
        ],
    )

    regenerate_personas_script.main()

    assert recorder.calls == [("good", "All_Beauty", 6, True)]


def test_ingest_script_writes_run_summary(monkeypatch, capsys, tmp_path) -> None:
    result = {
        "category": "All_Beauty",
        "uploaded_reviews": 0,
        "uploaded_metadata": 0,
        "dry_run": True,
    }
    monkeypatch.setattr(ingest_amazon_script, "ingest_category", lambda **_kwargs: result)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ingest_amazon.py",
            "--category",
            "All_Beauty",
            "--dry-run",
            "--output-dir",
            str(tmp_path),
        ],
    )

    ingest_amazon_script.main()

    output = capsys.readouterr().out
    assert "[ingestion] Run summary saved:" in output
    assert str(result) in output
    summary_files = list(tmp_path.glob("All_Beauty_dry_run_*.json"))
    assert len(summary_files) == 1
    summary = json.loads(summary_files[0].read_text(encoding="utf-8"))
    assert summary["category"] == "All_Beauty"
    assert summary["mode"] == "dry_run"
    assert summary["args"]["dry_run"] is True
    assert summary["result"] == result


class UpdateQueryRecorder:
    def __init__(self) -> None:
        self.updates = []
        self.review_ids = []

    def update(self, payload):
        self.updates.append(payload)
        return self

    def in_(self, _column, values):
        self.review_ids.append(values)
        return self

    def execute(self):
        return type("Response", (), {"data": []})()


class UpdateClientRecorder:
    def __init__(self) -> None:
        self.query = UpdateQueryRecorder()

    def table(self, _name):
        return self.query


def test_apply_updates_updates_only_task_split(monkeypatch) -> None:
    client = UpdateClientRecorder()
    monkeypatch.setattr(create_holdout_split, "get_supabase_client", lambda: client)

    create_holdout_split.apply_updates(
        [
            {"review_id": "r1", "task_split": "task_a_holdout"},
            {"review_id": "r2", "task_split": "persona_train"},
        ],
        batch_size=10,
    )

    assert all(set(payload) == {"task_split"} for payload in client.query.updates)


class EmbeddingStoreRecorder:
    def __init__(self) -> None:
        self.upserts = []

    def upsert_product_embedding(self, *args):
        self.upserts.append(args)


def test_embed_products_dry_run_does_not_write_or_encode(monkeypatch) -> None:
    store = EmbeddingStoreRecorder()
    monkeypatch.setattr(embed_products, "existing_embedding_ids", lambda parent_asins: set())

    def fail_encode(*_args, **_kwargs):
        raise AssertionError("dry-run should not encode embeddings")

    monkeypatch.setattr(embed_products, "embed_texts", fail_encode)

    result = embed_products.embed_product_batch(
        [
            {
                "parent_asin": "asin-1",
                "title": "Gentle Face Cream",
                "category": "All_Beauty",
                "features": ["hydrating"],
            }
        ],
        store,
        dry_run=True,
    )

    assert result["would_embed"] == 1
    assert result["embedded"] == 0
    assert store.upserts == []


class PreferenceVectorClientRecorder:
    def __init__(self, persona_user_ids: list[str]) -> None:
        self.persona_user_ids = persona_user_ids
        self.tables = []

    def table(self, name: str):
        self.tables.append(name)
        return self

    def select(self, _columns):
        return self

    def eq(self, _column, _value):
        return self

    def range(self, _start, _end):
        return self

    def execute(self):
        # Only used for user_personas pagination in batch mode.
        data = [{"user_id": user_id} for user_id in self.persona_user_ids]
        self.persona_user_ids = []
        return type("Resp", (), {"data": data})()


def test_build_user_preference_vectors_single_user_mode(monkeypatch, capsys) -> None:
    calls = []

    def fake_build_and_store(user_id, category, embedding_model, client=None):
        calls.append((user_id, category, embedding_model))
        return [0.1], ["p1"]

    monkeypatch.setattr(build_user_preference_vectors_script, "get_supabase_client", lambda: object())
    monkeypatch.setattr(build_user_preference_vectors_script, "build_and_store_user_preference_vector", fake_build_and_store)
    monkeypatch.setattr(
        "sys.argv",
        ["build_user_preference_vectors.py", "--user-id", "u1", "--category", "Electronics", "--model", "m1"],
    )

    build_user_preference_vectors_script.main()

    assert calls == [("u1", "Electronics", "m1")]
    output = capsys.readouterr().out
    assert "u1" in output
    assert "Electronics" in output


def test_build_user_preference_vectors_batch_skips_existing_by_default(monkeypatch, capsys) -> None:
    client = PreferenceVectorClientRecorder(["u1", "u2"])
    monkeypatch.setattr(build_user_preference_vectors_script, "get_supabase_client", lambda: client)
    monkeypatch.setattr(build_user_preference_vectors_script, "fetch_user_preference_vector", lambda user_id, _cat, client=None: {"user_id": user_id} if user_id == "u1" else None)
    built = []

    def fake_build_and_store(user_id, category, embedding_model, client=None):
        built.append(user_id)
        return [0.1], ["p1"]

    monkeypatch.setattr(build_user_preference_vectors_script, "build_and_store_user_preference_vector", fake_build_and_store)
    monkeypatch.setattr(
        "sys.argv",
        ["build_user_preference_vectors.py", "--category", "Health_and_Household", "--limit", "20"],
    )

    build_user_preference_vectors_script.main()

    assert built == ["u2"]
    output = capsys.readouterr().out
    assert "skipped_existing" in output


def test_build_user_preference_vectors_batch_force_rebuilds_existing(monkeypatch) -> None:
    client = PreferenceVectorClientRecorder(["u1"])
    monkeypatch.setattr(build_user_preference_vectors_script, "get_supabase_client", lambda: client)
    monkeypatch.setattr(build_user_preference_vectors_script, "fetch_user_preference_vector", lambda _user_id, _cat, client=None: {"user_id": "u1"})
    built = []

    def fake_build_and_store(user_id, category, embedding_model, client=None):
        built.append(user_id)
        return [0.1], ["p1"]

    monkeypatch.setattr(build_user_preference_vectors_script, "build_and_store_user_preference_vector", fake_build_and_store)
    monkeypatch.setattr(
        "sys.argv",
        ["build_user_preference_vectors.py", "--category", "Health_and_Household", "--limit", "1", "--force"],
    )

    build_user_preference_vectors_script.main()

    assert built == ["u1"]


def test_task_b_cli_passes_category_for_user_mode(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(run_task_b_script, "recommend_for_user", lambda *args, **kwargs: captured.update({"args": args, "kwargs": kwargs}) or {"ok": True})
    monkeypatch.setattr(run_task_b_script, "print_json", lambda _payload: None)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_task_b_recommendation.py",
            "--user-id",
            "u1",
            "--category",
            "Electronics",
            "--request",
            "portable charger",
        ],
    )

    run_task_b_script.main()

    assert captured["kwargs"]["category"] == "Electronics"


def test_task_b_cli_passes_category_for_cold_start(monkeypatch) -> None:
    captured = {}

    def fake_recommend(request):
        captured["request"] = request
        return {"ok": True}

    monkeypatch.setattr(run_task_b_script, "recommend", fake_recommend)
    monkeypatch.setattr(run_task_b_script, "print_json", lambda _payload: None)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_task_b_recommendation.py",
            "--cold-start",
            "--category",
            "Electronics",
            "--request",
            "portable charger",
        ],
    )

    run_task_b_script.main()

    assert captured["request"].category == "Electronics"
