from scripts import ingest_amazon as ingest_script
from src.ingestion import ingest_amazon


def test_readme_documents_holdout_as_separate_step_and_persona_limit() -> None:
    readme = open("README.md", encoding="utf-8").read()

    assert "migrations -> ingestion -> create_holdout_split.py -> generate personas" in readme
    assert "python scripts/generate_personas.py --category All_Beauty --limit 20" in readme


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


class SelectColumnsDataset:
    column_names = ["parent_asin", "title", "images", "bought_together", "details"]

    def __init__(self) -> None:
        self.selected = None

    def select_columns(self, columns):
        self.selected = columns
        return self


class RemoveColumnsDataset:
    column_names = ["parent_asin", "title", "images", "bought_together", "details"]

    def __init__(self) -> None:
        self.removed = None

    def select_columns(self, _columns):
        raise RuntimeError("select unavailable")

    def remove_columns(self, columns):
        self.removed = columns
        return self


class ProblemColumnFallbackDataset:
    column_names = []

    def __init__(self) -> None:
        self.removed = []

    def remove_columns(self, columns):
        self.removed.extend(columns)
        return self


def test_metadata_pruning_prefers_select_columns() -> None:
    dataset = SelectColumnsDataset()

    assert ingest_amazon.prune_metadata_columns(dataset) is dataset
    assert dataset.selected == ["parent_asin", "title", "images", "bought_together", "details"]


def test_metadata_pruning_falls_back_to_remove_columns() -> None:
    dataset = RemoveColumnsDataset()

    assert ingest_amazon.prune_metadata_columns(dataset) is dataset
    assert dataset.removed == ["variants"]


def test_metadata_pruning_removes_known_problem_columns_without_column_names() -> None:
    dataset = ProblemColumnFallbackDataset()

    assert ingest_amazon.prune_metadata_columns(dataset) is dataset
    assert "images" not in dataset.removed
    assert "bought_together" not in dataset.removed
    assert "variants" in dataset.removed


def test_stream_metadata_uses_raw_jsonl_fallback_by_default(monkeypatch) -> None:
    monkeypatch.setattr(ingest_amazon, "stream_metadata_jsonl_fallback", lambda category: [{"category": category}])

    assert list(ingest_amazon.stream_metadata("All_Beauty")) == [{"category": "All_Beauty"}]


class CastFailingMetadata:
    def __iter__(self):
        raise RuntimeError("Unsupported cast from list<item: struct<thumb: string>> to struct using function cast_struct")


def test_metadata_iterable_falls_back_on_nested_cast_error(capsys) -> None:
    rows = list(
        ingest_amazon.MetadataIterableWithFallback(
            CastFailingMetadata(),
            fallback_factory=lambda: [valid_metadata("p1")],
        )
    )

    assert rows == [valid_metadata("p1")]
    assert "falling back to raw JSONL metadata streaming" in capsys.readouterr().out


def test_metadata_iterable_does_not_hide_other_errors() -> None:
    class BrokenMetadata:
        def __iter__(self):
            raise RuntimeError("regular failure")

    try:
        list(ingest_amazon.MetadataIterableWithFallback(BrokenMetadata(), fallback_factory=lambda: []))
    except RuntimeError as exc:
        assert "regular failure" in str(exc)
    else:
        raise AssertionError("expected non-cast errors to propagate")


def test_iter_jsonl_metadata_file_preserves_nested_optional_fields() -> None:
    import io

    raw = (
        '{"parent_asin": "p1", "images": [{"thumb": "https://example.com/t.jpg"}], '
        '"bought_together": ["p2"]}\n'
    )

    rows = list(ingest_amazon.iter_jsonl_metadata_file(io.BytesIO(raw.encode("utf-8"))))

    assert rows == [
        {
            "parent_asin": "p1",
            "images": [{"thumb": "https://example.com/t.jpg"}],
            "bought_together": ["p2"],
        }
    ]


def test_iter_jsonl_file_reads_plain_and_gzipped_jsonl(tmp_path) -> None:
    import gzip

    plain = tmp_path / "reviews.jsonl"
    gzipped = tmp_path / "metadata.jsonl.gz"
    plain.write_text('{"user_id": "u1"}\nnot json\n{"user_id": "u2"}\n', encoding="utf-8")
    with gzip.open(gzipped, "wt", encoding="utf-8") as file_obj:
        file_obj.write('{"parent_asin": "p1"}\n')

    assert list(ingest_amazon.iter_jsonl_file(plain)) == [{"user_id": "u1"}, {"user_id": "u2"}]
    assert list(ingest_amazon.iter_jsonl_file(gzipped)) == [{"parent_asin": "p1"}]


def test_cache_paths_use_requested_category_and_dir(tmp_path) -> None:
    assert ingest_amazon.cache_review_path("Electronics", tmp_path) == tmp_path / "Electronics_reviews.jsonl"
    assert ingest_amazon.cache_metadata_path("Electronics", tmp_path) == tmp_path / "Electronics_metadata.jsonl"


def test_cache_file_ready_uses_line_count_for_review_cache_without_marker(tmp_path) -> None:
    review_file = tmp_path / "Electronics_reviews.jsonl"
    review_file.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")

    assert ingest_amazon.cache_file_ready(review_file, expected_min_lines=2) is True
    assert ingest_amazon.cache_file_ready(review_file, expected_min_lines=3) is False


def test_cache_file_ready_requires_marker_for_metadata_cache(tmp_path) -> None:
    metadata_file = tmp_path / "Electronics_metadata.jsonl"
    metadata_file.write_text('{"a": 1}\n', encoding="utf-8")

    assert ingest_amazon.cache_file_ready(metadata_file) is False
    ingest_amazon.write_cache_complete_marker(metadata_file, 1)
    assert ingest_amazon.cache_file_ready(metadata_file) is True


def test_resolve_ingestion_files_requires_both_explicit_files(tmp_path) -> None:
    review_file = tmp_path / "reviews.jsonl"
    review_file.write_text("", encoding="utf-8")

    try:
        ingest_amazon.resolve_ingestion_files("Electronics", reviews_file=review_file)
    except ValueError as exc:
        assert "--reviews-file and --metadata-file" in str(exc)
    else:
        raise AssertionError("expected paired local files to be required")


def test_resolve_ingestion_files_reads_cache_paths(tmp_path) -> None:
    review_file = tmp_path / "Electronics_reviews.jsonl"
    metadata_file = tmp_path / "Electronics_metadata.jsonl"
    review_file.write_text("", encoding="utf-8")
    metadata_file.write_text("", encoding="utf-8")

    assert ingest_amazon.resolve_ingestion_files("Electronics", from_cache=True, cache_dir=tmp_path) == (
        review_file,
        metadata_file,
    )


def test_write_category_cache_respects_review_limit_and_caches_all_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        ingest_amazon,
        "stream_reviews",
        lambda _category: [valid_review("u1", f"p{i}", i) for i in range(3)],
    )
    monkeypatch.setattr(
        ingest_amazon,
        "download_metadata_cache_with_hub",
        lambda _category, output_path: ingest_amazon.write_jsonl_cache(
            [valid_metadata("p1"), valid_metadata("p2")],
            output_path,
            label="metadata rows",
        ),
    )

    review_file, metadata_file = ingest_amazon.write_category_cache("All_Beauty", cache_dir=tmp_path, review_limit=2)

    assert len(list(ingest_amazon.iter_jsonl_file(review_file))) == 2
    assert len(list(ingest_amazon.iter_jsonl_file(metadata_file))) == 2


def test_write_category_cache_skips_ready_files(tmp_path, monkeypatch) -> None:
    review_file = ingest_amazon.cache_review_path("All_Beauty", tmp_path)
    metadata_file = ingest_amazon.cache_metadata_path("All_Beauty", tmp_path)
    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    metadata_file.write_text('{"parent_asin": "p1"}\n', encoding="utf-8")
    ingest_amazon.write_cache_complete_marker(metadata_file, 1)
    monkeypatch.setattr(
        ingest_amazon,
        "stream_reviews",
        lambda _category: (_ for _ in ()).throw(AssertionError("ready review cache should be skipped")),
    )
    monkeypatch.setattr(
        ingest_amazon,
        "download_metadata_cache_with_hub",
        lambda _category, _output_path: (_ for _ in ()).throw(
            AssertionError("ready metadata cache should be skipped")
        ),
    )

    assert ingest_amazon.write_category_cache("All_Beauty", cache_dir=tmp_path, review_limit=2) == (
        review_file,
        metadata_file,
    )


def test_write_category_cache_force_rebuilds_ready_files(tmp_path, monkeypatch) -> None:
    review_file = ingest_amazon.cache_review_path("All_Beauty", tmp_path)
    metadata_file = ingest_amazon.cache_metadata_path("All_Beauty", tmp_path)
    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    metadata_file.write_text('{"parent_asin": "old"}\n', encoding="utf-8")
    ingest_amazon.write_cache_complete_marker(metadata_file, 1)
    monkeypatch.setattr(ingest_amazon, "stream_reviews", lambda _category: [valid_review("u1", "p1")])
    monkeypatch.setattr(
        ingest_amazon,
        "download_metadata_cache_with_hub",
        lambda _category, output_path: ingest_amazon.write_jsonl_cache(
            [valid_metadata("new")],
            output_path,
            label="metadata rows",
        ),
    )

    ingest_amazon.write_category_cache("All_Beauty", cache_dir=tmp_path, review_limit=1, force_cache=True)

    assert list(ingest_amazon.iter_jsonl_file(review_file))[0]["parent_asin"] == "p1"
    assert list(ingest_amazon.iter_jsonl_file(metadata_file))[0]["parent_asin"] == "new"


def test_cli_defaults_are_evaluation_friendly() -> None:
    args = ingest_script.build_parser().parse_args([])

    assert args.min_reviews == 15
    assert args.max_users == 100
    assert args.extra_products == 1000
    assert args.require_rating_number is False


def test_cli_supports_require_rating_number() -> None:
    args = ingest_script.build_parser().parse_args(["--require-rating-number"])

    assert args.require_rating_number is True


def test_cli_supports_cache_and_local_file_flags() -> None:
    args = ingest_script.build_parser().parse_args(
        [
            "--from-cache",
            "--cache-dir",
            "data/cache/test",
            "--write-cache",
            "--force-cache",
            "--reviews-file",
            "reviews.jsonl",
            "--metadata-file",
            "metadata.jsonl",
        ]
    )

    assert args.from_cache is True
    assert args.cache_dir == "data/cache/test"
    assert args.write_cache is True
    assert args.force_cache is True
    assert args.reviews_file == "reviews.jsonl"
    assert args.metadata_file == "metadata.jsonl"


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


def test_review_missing_title_is_invalid() -> None:
    review = valid_review("u1", "p1", 1)
    review["title"] = ""

    assert ingest_amazon.is_valid_review(review) is False


def test_review_missing_text_is_invalid() -> None:
    review = valid_review("u1", "p1", 1)
    review["text"] = ""

    assert ingest_amazon.is_valid_review(review) is False


def test_review_missing_timestamp_is_valid() -> None:
    review = valid_review("u1", "p1", 1)
    review.pop("timestamp")

    assert ingest_amazon.is_valid_review(review) is True


def test_product_required_metadata_fields_are_enforced() -> None:
    required_fields = [
        "description",
        "features",
        "price",
        "average_rating",
        "store",
        "details",
    ]

    for field in required_fields:
        item = valid_metadata(f"missing-{field}")
        item[field] = [] if field in {"description", "features"} else None
        if field == "details":
            item[field] = {}

        assert ingest_amazon.is_valid_metadata(item, "All_Beauty") is False, field


def test_product_details_dict_is_valid() -> None:
    item = valid_metadata("p1")

    assert ingest_amazon.normalize_details_value(item["details"]) == {"skin_type": "dry"}
    assert ingest_amazon.is_valid_metadata(item, "All_Beauty") is True


def test_product_details_json_string_dict_is_valid() -> None:
    item = valid_metadata("p1")
    item["details"] = '{"Color": "As Shown", "Manufacturer": "Lurrose"}'

    assert ingest_amazon.normalize_details_value(item["details"]) == {
        "Color": "As Shown",
        "Manufacturer": "Lurrose",
    }
    assert ingest_amazon.is_valid_metadata(item, "All_Beauty") is True


def test_product_details_invalid_json_string_is_invalid() -> None:
    item = valid_metadata("p1")
    item["details"] = '{"Color": "As Shown"'

    assert ingest_amazon.normalize_details_value(item["details"]) is None
    assert ingest_amazon.is_valid_metadata(item, "All_Beauty") is False


def test_product_details_non_dict_json_is_invalid() -> None:
    for raw_details in ('["Color"]', '"Color"'):
        item = valid_metadata("p1")
        item["details"] = raw_details

        assert ingest_amazon.normalize_details_value(item["details"]) is None
        assert ingest_amazon.is_valid_metadata(item, "All_Beauty") is False


def test_normalize_metadata_converts_json_string_details_to_dict() -> None:
    item = valid_metadata("p1")
    item["details"] = '{"Color": "As Shown", "Manufacturer": "Lurrose"}'

    normalized = ingest_amazon.normalize_metadata(item, "All_Beauty")

    assert normalized["details"] == {"Color": "As Shown", "Manufacturer": "Lurrose"}
    assert normalized["raw_metadata"]["details"] == '{"Color": "As Shown", "Manufacturer": "Lurrose"}'


def test_optional_images_and_bought_together_are_not_required() -> None:
    item = valid_metadata("p1")
    item.pop("images", None)
    item.pop("bought_together", None)

    normalized = ingest_amazon.normalize_metadata(item, "All_Beauty")

    assert ingest_amazon.is_valid_metadata(item, "All_Beauty") is True
    assert normalized["images"] == []
    assert normalized["bought_together"] == []


def test_normalize_metadata_preserves_optional_image_and_related_fields() -> None:
    item = valid_metadata("p1")
    item["images"] = [
        {"hi_res": "https://example.com/hi.jpg", "thumb": "https://example.com/thumb.jpg"},
        "https://example.com/plain.jpg",
    ]
    item["bought_together"] = ["B001", {"parent_asin": "B002"}]

    normalized = ingest_amazon.normalize_metadata(item, "All_Beauty")

    assert normalized["images"] == item["images"]
    assert normalized["bought_together"] == item["bought_together"]


def test_optional_metadata_fields_accept_dict_and_json_strings() -> None:
    item = valid_metadata("p1")
    item["images"] = '{"thumb": "https://example.com/thumb.jpg"}'
    item["bought_together"] = '["B001", {"parent_asin": "B002"}]'

    normalized = ingest_amazon.normalize_metadata(item, "All_Beauty")

    assert normalized["images"] == [{"thumb": "https://example.com/thumb.jpg"}]
    assert normalized["bought_together"] == ["B001", {"parent_asin": "B002"}]


def test_optional_metadata_fields_drop_invalid_values() -> None:
    item = valid_metadata("p1")
    item["images"] = '{"thumb": "missing close brace"'
    item["bought_together"] = 123

    normalized = ingest_amazon.normalize_metadata(item, "All_Beauty")

    assert normalized["images"] == []
    assert normalized["bought_together"] == []


def test_product_missing_rating_number_is_valid_by_default() -> None:
    item = valid_metadata("p1")
    item["rating_number"] = None

    assert ingest_amazon.is_valid_metadata(item, "All_Beauty") is True


def test_product_missing_rating_number_is_invalid_when_required() -> None:
    item = valid_metadata("p1")
    item["rating_number"] = None

    assert ingest_amazon.is_valid_metadata(item, "All_Beauty", require_rating_number=True) is False


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


def test_duplicate_reviews_do_not_count_toward_user_eligibility() -> None:
    duplicate = valid_review("u1", "p1", 1)

    plan = ingest_amazon.build_ingestion_plan(
        [duplicate, dict(duplicate)],
        [valid_metadata("p1")],
        category="All_Beauty",
        min_reviews=2,
        max_users=100,
        extra_products=0,
    )

    assert plan["valid_review_rows"] == 1
    assert plan["valid_review_product_pairs"] == 1
    assert plan["duplicate_review_ids_skipped"] == 1
    assert plan["selected_user_ids"] == []


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


def test_rating_number_requirement_affects_valid_pair_selection() -> None:
    metadata = valid_metadata("p1")
    metadata["rating_number"] = None

    plan = ingest_amazon.build_ingestion_plan(
        [valid_review("u1", "p1", 1)],
        [metadata],
        category="All_Beauty",
        min_reviews=1,
        max_users=100,
        extra_products=0,
        require_rating_number=True,
    )

    assert plan["selected_user_ids"] == []
    assert plan["valid_review_product_pairs"] == 0


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


def test_dry_run_performs_no_upload(monkeypatch, capsys) -> None:
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
    output = capsys.readouterr().out
    assert "[ingestion] Prepared upload:" in output
    assert "[ingestion] Dry run enabled; no Supabase upserts will be performed." in output
    assert "[ingestion] Final result:" in output


def test_ingest_category_reads_from_cache_without_hugging_face(tmp_path, monkeypatch) -> None:
    review_file = ingest_amazon.cache_review_path("All_Beauty", tmp_path)
    metadata_file = ingest_amazon.cache_metadata_path("All_Beauty", tmp_path)
    review_file.write_text(
        "\n".join(
            [
                '{"user_id": "u1", "parent_asin": "p1", "rating": 5, "title": "Great", "text": "Useful"}',
                '{"user_id": "u1", "parent_asin": "p2", "rating": 5, "title": "Great", "text": "Useful"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    metadata_file.write_text(
        "\n".join(
            [
                '{"parent_asin": "p1", "title": "P1", "main_category": "Beauty", "features": ["a"], '
                '"description": ["d"], "price": 1.0, "average_rating": 4.5, "store": "S", "details": {"k": "v"}}',
                '{"parent_asin": "p2", "title": "P2", "main_category": "Beauty", "features": ["a"], '
                '"description": ["d"], "price": 1.0, "average_rating": 4.5, "store": "S", "details": {"k": "v"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        ingest_amazon,
        "stream_reviews",
        lambda _category: (_ for _ in ()).throw(AssertionError("should not stream reviews from Hugging Face")),
    )
    monkeypatch.setattr(
        ingest_amazon,
        "stream_metadata",
        lambda _category: (_ for _ in ()).throw(AssertionError("should not stream metadata from Hugging Face")),
    )

    result = ingest_amazon.ingest_category(
        category="All_Beauty",
        min_reviews=2,
        max_users=100,
        extra_products=0,
        from_cache=True,
        cache_dir=tmp_path,
        dry_run=True,
    )

    assert result["selected_eligible_users"] == 1
    assert result["valid_review_product_pairs"] == 2


class UpsertQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name

    def upsert(self, rows, on_conflict):
        self.client.upserts.append(
            {
                "table": self.table_name,
                "rows": list(rows),
                "on_conflict": on_conflict,
            }
        )
        return self

    def execute(self):
        return type("Response", (), {"data": []})()


class UpsertClient:
    def __init__(self):
        self.upserts = []

    def table(self, name):
        return UpsertQuery(self, name)


def test_upsert_reviews_deduplicates_batch_by_review_id(capsys) -> None:
    client = UpsertClient()
    rows = [
        {"review_id": "r1", "user_id": "u1", "parent_asin": "p1"},
        {"review_id": "r1", "user_id": "u1", "parent_asin": "p1"},
    ]

    uploaded = ingest_amazon.upsert_reviews(client, rows)

    assert uploaded == 1
    assert len(client.upserts[0]["rows"]) == 1
    assert "Skipped 1 duplicate review_id rows before upsert." in capsys.readouterr().out


def test_upsert_metadata_deduplicates_batch_by_parent_asin(capsys) -> None:
    client = UpsertClient()
    rows = [
        {"parent_asin": "p1", "title": "one"},
        {"parent_asin": "p1", "title": "one duplicate"},
    ]

    uploaded = ingest_amazon.upsert_metadata(client, rows)

    assert uploaded == 1
    assert len(client.upserts[0]["rows"]) == 1
    assert "Skipped 1 duplicate parent_asin metadata rows before upsert." in capsys.readouterr().out


class FailingUpsertQuery(UpsertQuery):
    def execute(self):
        raise RuntimeError("ON CONFLICT DO UPDATE command cannot affect row a second time")


class FailingUpsertClient:
    def __init__(self):
        self.upserts = []

    def table(self, name):
        return FailingUpsertQuery(self, name)


def test_upsert_error_message_is_readable() -> None:
    try:
        ingest_amazon.upsert_reviews(
            FailingUpsertClient(),
            [{"review_id": "r1", "user_id": "u1", "parent_asin": "p1"}],
            batch_label="review batch 9",
        )
    except ingest_amazon.IngestionUploadError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected IngestionUploadError")

    assert "Failed to upsert amazon_reviews (review batch 9)" in message
    assert "same review_id appeared more than once" in message


def test_real_upload_path_logs_batches_and_preserves_counts(monkeypatch, capsys) -> None:
    reviews = [valid_review("u1", "p1", 1), valid_review("u1", "p2", 2), valid_review("u1", "p3", 3)]
    metadata = [valid_metadata("p1"), valid_metadata("p2"), valid_metadata("p3")]
    monkeypatch.setattr(ingest_amazon, "stream_reviews", lambda _category: reviews)
    monkeypatch.setattr(ingest_amazon, "stream_metadata", lambda _category: metadata)
    client = UpsertClient()

    result = ingest_amazon.ingest_category(
        category="All_Beauty",
        min_reviews=1,
        max_users=100,
        extra_products=0,
        batch_size=2,
        dry_run=False,
        client=client,
    )

    assert result["uploaded_reviews"] == 3
    assert result["uploaded_metadata"] == 3
    assert [len(call["rows"]) for call in client.upserts] == [2, 1, 2, 1]
    output = capsys.readouterr().out
    assert "[ingestion] Review upsert starting." in output
    assert "[ingestion] Upserting review batch 1: 2 rows" in output
    assert "[ingestion] Upserting review batch 2: 1 rows" in output
    assert "[ingestion] Review upsert complete: 3 rows" in output
    assert "[ingestion] Metadata upsert starting." in output
    assert "[ingestion] Upserting metadata batch 1: 2 rows" in output
    assert "[ingestion] Upserting metadata batch 2: 1 rows" in output
    assert "[ingestion] Metadata upsert complete: 3 rows" in output


def test_verify_path_logs_verification_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(ingest_amazon, "stream_reviews", lambda _category: [valid_review("u1", "p1", 1)])
    monkeypatch.setattr(ingest_amazon, "stream_metadata", lambda _category: [valid_metadata("p1")])
    monkeypatch.setattr(
        ingest_amazon,
        "verify_uploaded_counts",
        lambda *_args, **_kwargs: {
            "db_users_with_min_reviews": 1,
            "db_reviews_with_matching_metadata": 1,
            "db_reviews_missing_metadata": 0,
        },
    )

    result = ingest_amazon.ingest_category(
        category="All_Beauty",
        min_reviews=1,
        max_users=100,
        extra_products=0,
        dry_run=False,
        verify=True,
        client=UpsertClient(),
    )

    assert result["db_users_with_min_reviews"] == 1
    output = capsys.readouterr().out
    assert "[ingestion] DB verification starting." in output
    assert "[ingestion] DB verification result: users_with_min_reviews=1" in output


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
