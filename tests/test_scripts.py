from scripts import create_holdout_split
from scripts import embed_products
from scripts import regenerate_personas as regenerate_personas_script
from scripts import regenerate_personas

build_holdout_updates = create_holdout_split.build_holdout_updates


def test_holdout_split_does_not_require_review_category() -> None:
    updates = build_holdout_updates(
        [
            {"review_id": "old", "user_id": "u1", "rating": 5, "timestamp": "2024-01-01T00:00:00Z"},
            {"review_id": "mid", "user_id": "u1", "rating": 4, "timestamp": "2024-02-01T00:00:00Z"},
            {"review_id": "new", "user_id": "u1", "rating": 3, "timestamp": "2024-03-01T00:00:00Z"},
        ]
    )

    by_id = {update["review_id"]: update for update in updates}
    assert by_id["new"]["task_split"] == "task_a_holdout"
    assert by_id["mid"]["task_split"] == "task_b_holdout"
    assert by_id["old"]["task_split"] == "persona_train"


def test_holdout_split_uses_most_recent_high_rated_review_for_task_b() -> None:
    updates = build_holdout_updates(
        [
            {"review_id": "old-liked", "user_id": "u1", "rating": 5, "timestamp": "2024-01-01T00:00:00Z"},
            {"review_id": "mid-low", "user_id": "u1", "rating": 2, "timestamp": "2024-02-01T00:00:00Z"},
            {"review_id": "new-low", "user_id": "u1", "rating": 3, "timestamp": "2024-03-01T00:00:00Z"},
        ]
    )

    by_id = {update["review_id"]: update for update in updates}
    assert by_id["new-low"] == {"review_id": "new-low", "task_split": "task_a_holdout"}
    assert by_id["old-liked"] == {"review_id": "old-liked", "task_split": "task_b_holdout"}
    assert by_id["mid-low"] == {"review_id": "mid-low", "task_split": "persona_train"}


def test_holdout_split_leaves_no_task_b_when_no_high_rated_candidate() -> None:
    updates = build_holdout_updates(
        [
            {"review_id": "old-low", "user_id": "u1", "rating": 2, "timestamp": "2024-01-01T00:00:00Z"},
            {"review_id": "new-low", "user_id": "u1", "rating": 3, "timestamp": "2024-02-01T00:00:00Z"},
        ]
    )

    assert {update["task_split"] for update in updates} == {"task_a_holdout", "persona_train"}


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

    def regenerate_persona(self, user_id, category, store=True):
        self.calls.append((user_id, category, store))
        if user_id == "bad":
            raise RuntimeError("boom")
        return {"source_review_ids": ["r1", "r2"]}


def test_regenerate_personas_script_logs_progress_and_failures(monkeypatch, capsys) -> None:
    recorder = PersonaGeneratorRecorder()
    monkeypatch.setattr(regenerate_personas_script, "fetch_user_ids", lambda: ["good", "bad"])
    monkeypatch.setattr(regenerate_personas_script, "PersonaGenerator", lambda: recorder)
    monkeypatch.setattr(
        "sys.argv",
        ["regenerate_personas.py", "--category", "All_Beauty"],
    )

    regenerate_personas_script.main()

    assert recorder.calls == [("good", "All_Beauty", True), ("bad", "All_Beauty", True)]
    output = capsys.readouterr().out
    assert "[persona] Starting persona regeneration: category=All_Beauty, users=2" in output
    assert "[persona] Processing user 1/2: user_id=good" in output
    assert "[persona] Persona generation succeeded:" in output
    assert "[persona] Persona generation failed: user_id=bad, error=boom" in output
    assert "[persona] Persona regeneration complete: succeeded=1, failed=1, total=2" in output


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
