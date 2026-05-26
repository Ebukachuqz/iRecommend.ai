from pathlib import Path

from scripts import check_category_readiness
from scripts import list_embedded_products
from scripts import list_eval_users
from scripts import list_user_holdouts


class Query:
    def __init__(self, client, table: str):
        self.client = client
        self.table = table
        self.filters = []
        self._range = None
        self._limit = None

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, list(values)))
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def limit(self, value):
        self._limit = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        return type("Resp", (), {"data": self.client.respond(self.table, self.filters, self._range, self._limit)})()


class FakeClient:
    def __init__(self, tables: dict[str, list[dict]]):
        self.tables = tables

    def table(self, name: str):
        return Query(self, name)

    def respond(self, table: str, filters, range_value, limit_value):
        rows = list(self.tables.get(table, []))
        for kind, column, value in filters:
            if kind == "eq":
                rows = [r for r in rows if r.get(column) == value]
            elif kind == "in":
                value_set = set(value)
                rows = [r for r in rows if r.get(column) in value_set]
        if range_value is not None:
            start, end = range_value
            rows = rows[start : end + 1]
        if limit_value is not None:
            rows = rows[:limit_value]
        return rows


def test_check_category_readiness_counts_and_flags() -> None:
    category = "Health_and_Household"
    products = [
        {"parent_asin": "p1", "category": category, "main_category": None, "categories": []},
        {"parent_asin": "p2", "category": category, "main_category": None, "categories": []},
    ]
    reviews = [
        {"review_id": "r1", "user_id": "u1", "parent_asin": "p1", "task_split": "persona_train"},
        {"review_id": "r2", "user_id": "u1", "parent_asin": "p2", "task_split": "task_a_holdout"},
        {"review_id": "r3", "user_id": "u1", "parent_asin": "p2", "task_split": "task_b_holdout"},
    ]
    personas = [{"user_id": "u1", "category": category}]
    embeddings = [{"parent_asin": "p1"}, {"parent_asin": "p2"}]
    preference_vectors = [{"user_id": "u1", "category": category}]
    client = FakeClient(
        {
            "amazon_product_metadata": products,
            "amazon_reviews": reviews,
            "user_personas": personas,
            "product_embeddings": embeddings,
            "user_preference_vectors": preference_vectors,
        }
    )

    result = check_category_readiness.compute_category_readiness(client, category)

    assert result["product_metadata_rows"] == 2
    assert result["review_rows_joined"] == 3
    assert result["persona_train_reviews"] == 1
    assert result["task_a_holdout_reviews"] == 1
    assert result["task_b_holdout_reviews"] == 1
    assert result["user_personas"] == 1
    assert result["product_embeddings"] == 2
    assert result["user_preference_vectors"] == 1
    assert result["task_a_smoke_ready"] is True
    assert result["task_b_smoke_ready"] is True


def test_list_eval_users_filters_task_b_and_requires_persona_and_preference() -> None:
    category = "Health_and_Household"
    products = [{"parent_asin": "p1", "category": category, "main_category": None, "categories": []}]
    reviews = [
        {"review_id": "r1", "user_id": "u1", "parent_asin": "p1", "task_split": "task_b_holdout"},
        {"review_id": "r2", "user_id": "u2", "parent_asin": "p1", "task_split": "task_b_holdout"},
    ]
    personas = [{"user_id": "u1", "category": category}]
    preference_vectors = [{"user_id": "u1", "category": category}]
    client = FakeClient(
        {
            "amazon_product_metadata": products,
            "amazon_reviews": reviews,
            "user_personas": personas,
            "user_preference_vectors": preference_vectors,
        }
    )

    rows = list_eval_users.list_eval_users(
        client,
        category,
        limit=10,
        require_persona=True,
        require_preference_vector=True,
        task="task_b",
    )

    assert [row["user_id"] for row in rows] == ["u1"]
    assert rows[0]["has_persona"] is True
    assert rows[0]["has_preference_vector"] is True


def test_list_eval_users_task_b_does_not_require_preference_vector_by_default() -> None:
    category = "Health_and_Household"
    products = [{"parent_asin": "p1", "category": category, "main_category": None, "categories": []}]
    reviews = [
        {"review_id": "r1", "user_id": "u1", "parent_asin": "p1", "task_split": "task_b_holdout"},
        {"review_id": "r2", "user_id": "u2", "parent_asin": "p1", "task_split": "task_b_holdout"},
    ]
    personas = [{"user_id": "u1", "category": category}, {"user_id": "u2", "category": category}]
    preference_vectors = []
    client = FakeClient(
        {
            "amazon_product_metadata": products,
            "amazon_reviews": reviews,
            "user_personas": personas,
            "user_preference_vectors": preference_vectors,
        }
    )

    rows = list_eval_users.list_eval_users(
        client,
        category,
        limit=10,
        require_persona=True,
        require_preference_vector=False,
        task="task_b",
    )

    assert [row["user_id"] for row in rows] == ["u1", "u2"]
    assert all(row["has_preference_vector"] is False for row in rows)


def test_list_eval_users_task_b_with_require_preference_vector_filters() -> None:
    category = "Health_and_Household"
    products = [{"parent_asin": "p1", "category": category, "main_category": None, "categories": []}]
    reviews = [
        {"review_id": "r1", "user_id": "u1", "parent_asin": "p1", "task_split": "task_b_holdout"},
        {"review_id": "r2", "user_id": "u2", "parent_asin": "p1", "task_split": "task_b_holdout"},
    ]
    personas = [{"user_id": "u1", "category": category}, {"user_id": "u2", "category": category}]
    preference_vectors = [{"user_id": "u2", "category": category}]
    client = FakeClient(
        {
            "amazon_product_metadata": products,
            "amazon_reviews": reviews,
            "user_personas": personas,
            "user_preference_vectors": preference_vectors,
        }
    )

    rows = list_eval_users.list_eval_users(
        client,
        category,
        limit=10,
        require_persona=True,
        require_preference_vector=True,
        task="task_b",
    )

    assert [row["user_id"] for row in rows] == ["u2"]


def test_list_user_holdouts_includes_product_titles() -> None:
    category = "Health_and_Household"
    reviews = [
        {
            "task_split": "task_a_holdout",
            "parent_asin": "p1",
            "rating": 5,
            "title": "Great",
            "review_id": "r1",
            "user_id": "u1",
        }
    ]
    meta = [{"parent_asin": "p1", "title": "Product 1"}]
    client = FakeClient({"amazon_reviews": reviews, "amazon_product_metadata": meta})

    rows = list_user_holdouts.list_user_holdouts(client, "u1", category=category)

    assert rows == [
        {
            "task_split": "task_a_holdout",
            "parent_asin": "p1",
            "product_title": "Product 1",
            "rating": 5,
            "review_title": "Great",
            "review_id": "r1",
        }
    ]


def test_list_embedded_products_outputs_expected_fields() -> None:
    category = "Health_and_Household"
    products = [{"parent_asin": "p1", "category": category, "main_category": None, "categories": []}]
    embeddings = [{"parent_asin": "p1", "embedding_model": "m1", "created_at": "2026-01-01T00:00:00Z"}]
    meta = [{"parent_asin": "p1", "title": "Product 1", "category": category, "main_category": None}]
    client = FakeClient(
        {"amazon_product_metadata": products + meta, "product_embeddings": embeddings}
    )

    rows = list_embedded_products.list_embedded_products(client, category, limit=10)

    assert rows == [
        {
            "parent_asin": "p1",
            "title": "Product 1",
            "category": category,
            "main_category": "",
            "embedding_model": "m1",
            "created_at": "2026-01-01T00:00:00Z",
        }
    ]


def test_readme_finding_test_ids_section_exists() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "## Finding Test IDs" in readme
    assert "python scripts/check_category_readiness.py" in readme
    assert "python scripts/list_eval_users.py" in readme
    assert "python scripts/list_user_holdouts.py" in readme
    assert "python scripts/list_embedded_products.py" in readme
