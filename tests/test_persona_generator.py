from src.personas.generator import PersonaGenerator


class QueryRecorder:
    def __init__(self) -> None:
        self.filters = []
        self.payload = None
        self.on_conflict = None

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def upsert(self, payload, on_conflict=None):
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        return type("Response", (), {"data": []})()


class ClientRecorder:
    def __init__(self) -> None:
        self.queries = {}

    def table(self, name):
        query = QueryRecorder()
        self.queries[name] = query
        return query


def test_fetch_user_reviews_does_not_filter_by_category() -> None:
    client = ClientRecorder()
    generator = PersonaGenerator(client=client)

    generator.fetch_user_reviews("user-1")

    filters = client.queries["amazon_reviews"].filters
    assert ("user_id", "user-1") in filters
    assert ("task_split", "persona_train") in filters
    assert not any(column == "category" for column, _value in filters)


def test_store_persona_payload_includes_review_stats() -> None:
    client = ClientRecorder()
    generator = PersonaGenerator(client=client)
    stats = {
        "review_count": 8,
        "average_rating": 4.25,
        "source_review_ids": ["r1", "r2"],
    }

    generator.store_persona("user-1", "All_Beauty", {"writing_style": {}}, stats)

    query = client.queries["user_personas"]
    assert query.on_conflict == "user_id,category"
    assert query.payload["review_count"] == 8
    assert query.payload["average_rating"] == 4.25
    assert query.payload["source_review_ids"] == ["r1", "r2"]


def test_store_persona_logs_upsert_progress(capsys) -> None:
    client = ClientRecorder()
    generator = PersonaGenerator(client=client)
    stats = {
        "review_count": 8,
        "average_rating": 4.25,
        "source_review_ids": ["r1", "r2"],
    }

    generator.store_persona("user-1", "All_Beauty", {"writing_style": {}}, stats)

    output = capsys.readouterr().out
    assert "[persona] Upserting persona: user_id=user-1" in output
    assert "[persona] Persona upsert complete: user_id=user-1, category=All_Beauty" in output


def test_regenerate_persona_logs_when_store_disabled(monkeypatch, capsys) -> None:
    generator = PersonaGenerator(client=ClientRecorder())

    monkeypatch.setattr(
        generator,
        "generate_and_validate",
        lambda *_args, **_kwargs: (
            {"writing_style": {}},
            {"source_review_ids": ["r1", "r2"]},
        ),
    )

    result = generator.regenerate_persona("user-1", "All_Beauty", store=False)

    assert result["source_review_ids"] == ["r1", "r2"]
    output = capsys.readouterr().out
    assert "[persona] Regenerating persona: user_id=user-1" in output
    assert "[persona] Store disabled; persona not upserted: user_id=user-1" in output
    assert "[persona] Persona regeneration complete: user_id=user-1, source_reviews=2" in output


def test_prompt_stats_source_review_ids_match_selected_prompt_reviews() -> None:
    generator = PersonaGenerator(client=ClientRecorder())
    reviews = [
        {
            "review_id": f"r{index}",
            "parent_asin": f"asin-{index}",
            "rating": 5,
            "verified_purchase": True,
            "title": "Useful",
            "text": "Helpful review",
            "product": {"title": "Product"},
        }
        for index in range(30)
    ]

    _context, stats = generator.build_prompt_stats(reviews, reviews, max_reviews=12)

    assert stats["review_count"] == 30
    assert stats["eligible_review_count"] == 30
    assert stats["prompt_review_count"] == 12
    assert stats["review_count_available"] == 30
    assert stats["review_count_used"] == 12
    assert stats["source_review_ids"] == [f"r{index}" for index in range(18, 30)]


def test_prompt_stats_use_at_most_ten_reviews_by_default() -> None:
    generator = PersonaGenerator(client=ClientRecorder())
    reviews = [
        {
            "review_id": f"r{index}",
            "parent_asin": f"asin-{index}",
            "rating": 5,
            "verified_purchase": True,
            "title": "Useful",
            "text": "Helpful review",
            "product": {"title": "Product"},
        }
        for index in range(15)
    ]

    _context, selected_review_ids = generator.format_review_context(reviews)

    assert selected_review_ids == [f"r{index}" for index in range(5, 15)]


def test_prompt_review_selection_prefers_reviews_with_product_metadata() -> None:
    generator = PersonaGenerator(client=ClientRecorder())
    reviews = [
        {
            "review_id": "without-product",
            "parent_asin": "asin-1",
            "rating": 5,
            "title": "Useful",
            "text": "Helpful review",
            "product": {},
        },
        {
            "review_id": "with-product",
            "parent_asin": "asin-2",
            "rating": 5,
            "title": "Useful",
            "text": "Helpful review",
            "product": {"title": "Product"},
        },
    ]

    selected = generator.select_prompt_reviews(reviews, max_reviews=10)

    assert [review["review_id"] for review in selected] == ["with-product"]


def test_persona_review_filter_uses_project_category_not_main_category() -> None:
    generator = PersonaGenerator(client=ClientRecorder())
    reviews = [
        {
            "review_id": "project-category-match",
            "product": {"category": "Electronics", "main_category": "Camera & Photo"},
        },
        {
            "review_id": "main-category-only",
            "product": {"main_category": "Electronics"},
        },
    ]

    filtered = generator.filter_enriched_reviews_by_category(reviews, "Electronics")

    assert [review["review_id"] for review in filtered] == ["project-category-match"]
