from scripts import ingest_amazon as ingest_script
from src.ingestion import ingest_amazon


def test_readme_documents_holdout_as_separate_step_and_persona_limit() -> None:
    readme = open("README.md", encoding="utf-8").read()

    assert "migrations -> ingestion -> create_holdout_split.py -> regenerate personas" in readme
    assert "python scripts/regenerate_personas.py --category All_Beauty --limit 20" in readme


def valid_review(user_id: str, parent_asin: str, index: int = 1) -> dict:
    return {
        "user_id": user_id,
        "parent_asin": parent_asin,
        "rating": 5,
        "title": f"Review {index}",
        "text": f"Helpful review text {index}",
        "timestamp": f"2024-01-{(index % 28) + 1:02d}T00:00:00Z",
    }


def valid_metadata(parent_asin: str) -> dict:
    return {
        "parent_asin": parent_asin,
        "title": f"Product {parent_asin}",
        "main_category": "Beauty",
        "features": ["hydrating"],
        "description": ["A useful product."],
        "price": 12.99,
        "average_rating": 4.5,
        "rating_number": 120,
        "store": "Test Brand",
        "details": {"skin_type": "dry"},
    }


def sparse_metadata(parent_asin: str) -> dict:
    item = valid_metadata(parent_asin)
    item["details"] = {}
    return item


def test_cli_defaults_are_evaluation_friendly() -> None:
    args = ingest_script.build_parser().parse_args([])

    assert args.min_reviews == 15
    assert args.max_users == 100
    assert args.extra_products == 1000


def test_cli_keeps_backward_compatible_aliases() -> None:
    args = ingest_script.build_parser().parse_args(["--min-user-reviews", "9", "--max-reviews", "50"])

    assert args.min_reviews == 9
    assert args.review_limit == 50


def test_raw_review_count_is_not_enough_when_metadata_is_sparse() -> None:
    reviews = [valid_review("u1", f"p{i}", i) for i in range(15)]
    metadata = [valid_metadata(f"p{i}") for i in range(14)] + [sparse_metadata("p14")]

    plan = ingest_amazon.build_ingestion_plan(
        reviews,
        metadata,
        category="All_Beauty",
        min_reviews=15,
        max_users=100,
        extra_products=0,
    )

    assert plan["valid_review_rows"] == 15
    assert plan["valid_review_product_pairs"] == 14
    assert plan["selected_user_ids"] == []
    assert plan["reviews_to_upload"] == []


def test_users_qualify_only_by_valid_review_product_pairs() -> None:
    u1_reviews = [valid_review("u1", f"a{i}", i) for i in range(16)]
    u2_reviews = [valid_review("u2", f"b{i}", i) for i in range(15)]
    metadata = [valid_metadata(f"a{i}") for i in range(16)] + [valid_metadata(f"b{i}") for i in range(15)]

    plan = ingest_amazon.build_ingestion_plan(
        u2_reviews + u1_reviews,
        metadata,
        category="All_Beauty",
        min_reviews=15,
        max_users=1,
        extra_products=0,
    )

    assert plan["selected_user_ids"] == ["u1"]
    assert {review["user_id"] for review in plan["reviews_to_upload"]} == {"u1"}


def test_max_users_zero_selects_all_eligible_users() -> None:
    reviews = [valid_review("u1", "p1", 1), valid_review("u2", "p2", 2)]
    metadata = [valid_metadata("p1"), valid_metadata("p2")]

    plan = ingest_amazon.build_ingestion_plan(
        reviews,
        metadata,
        category="All_Beauty",
        min_reviews=1,
        max_users=0,
        extra_products=0,
    )

    assert plan["selected_user_ids"] == ["u1", "u2"]


def test_sparse_metadata_and_reviews_pointing_to_it_are_dropped() -> None:
    reviews = [valid_review("u1", "good", 1), valid_review("u1", "sparse", 2), valid_review("u1", "missing", 3)]
    metadata = [valid_metadata("good"), sparse_metadata("sparse")]

    plan = ingest_amazon.build_ingestion_plan(
        reviews,
        metadata,
        category="All_Beauty",
        min_reviews=1,
        max_users=100,
        extra_products=0,
    )

    assert plan["skipped_sparse_metadata"] == 1
    assert plan["valid_review_product_pairs"] == 1
    assert [review["parent_asin"] for review in plan["reviews_to_upload"]] == ["good"]
    assert [item["parent_asin"] for item in plan["metadata_to_upload"]] == ["good"]


def test_invalid_reviews_are_not_counted_or_uploaded() -> None:
    invalid = valid_review("u1", "p2", 2)
    invalid["text"] = ""

    plan = ingest_amazon.build_ingestion_plan(
        [valid_review("u1", "p1", 1), invalid],
        [valid_metadata("p1"), valid_metadata("p2")],
        category="All_Beauty",
        min_reviews=1,
        max_users=100,
        extra_products=0,
    )

    assert plan["skipped_invalid_reviews"] == 1
    assert plan["valid_review_rows"] == 1
    assert [review["parent_asin"] for review in plan["reviews_to_upload"]] == ["p1"]


def test_extra_products_must_be_valid_and_are_deduplicated() -> None:
    reviews = [valid_review("u1", "p1", 1)]
    metadata = [
        valid_metadata("p1"),
        valid_metadata("p1"),
        valid_metadata("extra-1"),
        sparse_metadata("extra-2"),
        valid_metadata("extra-3"),
    ]

    plan = ingest_amazon.build_ingestion_plan(
        reviews,
        metadata,
        category="All_Beauty",
        min_reviews=1,
        max_users=100,
        extra_products=2,
    )

    assert [item["parent_asin"] for item in plan["metadata_to_upload"]] == ["p1", "extra-1", "extra-3"]
    assert [item["parent_asin"] for item in plan["extra_metadata"]] == ["extra-1", "extra-3"]


class StreamingOnlyMetadata:
    def __init__(self, rows):
        self.rows = rows
        self.consumed = 0

    def __iter__(self):
        for row in self.rows:
            self.consumed += 1
            yield row

    def __len__(self):
        raise AssertionError("metadata stream should not be sized")

    def __getitem__(self, _index):
        raise AssertionError("metadata stream should not be indexed")


def test_metadata_iterable_is_consumed_as_stream_not_materialized() -> None:
    metadata = StreamingOnlyMetadata([valid_metadata("p1"), valid_metadata("extra-1"), valid_metadata("extra-2")])

    plan = ingest_amazon.build_ingestion_plan(
        [valid_review("u1", "p1", 1)],
        metadata,
        category="All_Beauty",
        min_reviews=1,
        max_users=100,
        extra_products=1,
    )

    assert metadata.consumed == 3
    assert [item["parent_asin"] for item in plan["metadata_to_upload"]] == ["p1", "extra-1"]


def test_unrelated_metadata_is_not_stored_beyond_extra_product_limit() -> None:
    metadata = [valid_metadata("p1"), valid_metadata("extra-1"), valid_metadata("extra-2"), valid_metadata("extra-3")]

    plan = ingest_amazon.build_ingestion_plan(
        [valid_review("u1", "p1", 1)],
        metadata,
        category="All_Beauty",
        min_reviews=1,
        max_users=100,
        extra_products=1,
    )

    assert [item["parent_asin"] for item in plan["metadata_to_upload"]] == ["p1", "extra-1"]
    assert [item["parent_asin"] for item in plan["extra_metadata"]] == ["extra-1"]


class StreamingOnlyReviews:
    def __init__(self, rows):
        self.rows = rows
        self.iterations = 0
        self.consumed = 0

    def __iter__(self):
        self.iterations += 1
        for row in self.rows:
            self.consumed += 1
            yield row

    def __len__(self):
        raise AssertionError("review stream should not be sized")

    def __getitem__(self, _index):
        raise AssertionError("review stream should not be indexed")


def test_review_iterable_is_consumed_as_stream_not_materialized() -> None:
    reviews = StreamingOnlyReviews([valid_review("u1", "p1", 1), valid_review("u1", "p2", 2)])

    plan = ingest_amazon.build_ingestion_plan(
        reviews,
        [valid_metadata("p1"), valid_metadata("p2")],
        category="All_Beauty",
        min_reviews=2,
        max_users=100,
        extra_products=0,
    )

    assert reviews.iterations == 3
    assert reviews.consumed == 6
    assert plan["selected_user_ids"] == ["u1"]
    assert [review["parent_asin"] for review in plan["reviews_to_upload"]] == ["p1", "p2"]


def test_review_limit_applies_to_each_streaming_review_pass() -> None:
    reviews = StreamingOnlyReviews(
        [
            valid_review("u1", "p1", 1),
            valid_review("u1", "p2", 2),
            valid_review("u1", "p3", 3),
        ]
    )

    plan = ingest_amazon.build_ingestion_plan(
        reviews,
        [valid_metadata("p1"), valid_metadata("p2"), valid_metadata("p3")],
        category="All_Beauty",
        min_reviews=3,
        max_users=100,
        extra_products=0,
        review_limit=2,
    )

    assert reviews.consumed == 6
    assert plan["valid_review_product_pairs"] == 2
    assert plan["selected_user_ids"] == []


class FailingClient:
    def table(self, _name):
        raise AssertionError("dry-run should not upload")


def test_dry_run_performs_no_upload(monkeypatch) -> None:
    monkeypatch.setattr(ingest_amazon, "stream_reviews", lambda _category: [valid_review("u1", "p1", 1)])
    monkeypatch.setattr(ingest_amazon, "stream_metadata", lambda _category: [valid_metadata("p1")])

    result = ingest_amazon.ingest_category(
        category="All_Beauty",
        min_reviews=1,
        max_users=100,
        extra_products=0,
        dry_run=True,
        client=FailingClient(),
    )

    assert result["dry_run"] is True
    assert result["uploaded_reviews"] == 0
    assert result["uploaded_metadata"] == 0
    assert result["selected_eligible_users"] == 1


class SelectQuery:
    def __init__(self, rows):
        self.rows = rows
        self.column = ""
        self.values = []

    def select(self, _columns):
        return self

    def in_(self, column, values):
        self.column = column
        self.values = values
        return self

    def execute(self):
        data = [row for row in self.rows if row.get(self.column) in self.values]
        return type("Response", (), {"data": data})()


class SelectClient:
    def __init__(self):
        self.tables = {
            "amazon_reviews": [
                {"review_id": "r1", "user_id": "u1", "parent_asin": "p1"},
                {"review_id": "r2", "user_id": "u1", "parent_asin": "missing"},
                {"review_id": "r3", "user_id": "u2", "parent_asin": "p2"},
            ],
            "amazon_product_metadata": [{"parent_asin": "p1"}, {"parent_asin": "p2"}],
        }

    def table(self, name):
        return SelectQuery(self.tables[name])


def test_verify_uploaded_counts_reports_matching_and_missing_metadata() -> None:
    result = ingest_amazon.verify_uploaded_counts(
        SelectClient(),
        review_ids=["r1", "r2", "r3"],
        parent_asins=["p1", "p2"],
        min_reviews=1,
    )

    assert result == {
        "db_users_with_min_reviews": 2,
        "db_reviews_with_matching_metadata": 2,
        "db_reviews_missing_metadata": 1,
    }
