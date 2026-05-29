# Data Ingestion

This document covers downloading and ingesting Amazon Reviews 2023 data into Supabase, creating holdout splits, and finding test IDs for evaluation.

---

## Dataset Note

The Hugging Face dataset `McAuley-Lab/Amazon-Reviews-2023` uses a dataset loading script. Hugging Face `datasets>=4.0.0` removed loading-script support, so ingestion currently requires `datasets<4.0.0` (see `requirements.txt`).

---

## Validation

Validation is evaluation-focused. Reviews must include `user_id`, `parent_asin` or `asin`, `rating`, `title`, and `text`. Timestamp, verified purchase, and helpful votes are kept when available but are not required.

Product metadata must include `parent_asin`, `title`, a category signal, `description`, `features`, `price`, `average_rating`, `store`, and `details`. `rating_number` is optional by default; pass `--require-rating-number` to drop metadata rows without it.

---

## Ingestion Commands

**Quick dry-run test:**

```powershell
python scripts/ingest_amazon.py --category All_Beauty --min-reviews 15 --max-users 20 --extra-products 100 --dry-run
```

**Normal evaluation rebuild:**

```powershell
python scripts/ingest_amazon.py --category Health_and_Household --min-reviews 15 --max-users 200 --extra-products 150 --verify
```

**Larger final rebuild:**

```powershell
python scripts/ingest_amazon.py --category All_Beauty --min-reviews 15 --max-users 300 --extra-products 5000 --verify
```

---

## Caching Workflow

If Hugging Face streaming is unreliable, cache the category JSONL files once and then ingest from cache.

`--write-cache` streams reviews from Hugging Face and downloads metadata into `data/cache/amazon_reviews_2023/<category>_reviews.jsonl` and `<category>_metadata.jsonl`. Metadata is cached fully; `--review-limit` caps cached reviews. Successful cache files are skipped on rerun; pass `--force-cache` only when you intentionally want to rebuild them.

```powershell
python scripts/ingest_amazon.py --category Electronics --write-cache --cache-dir data/cache/amazon_reviews_2023 --review-limit 200000 --dry-run
python scripts/ingest_amazon.py --category Electronics --from-cache --cache-dir data/cache/amazon_reviews_2023 --min-reviews 15 --max-users 200 --extra-products 150 --review-limit 200000 --verify
```

**Explicit local JSONL files:**

```powershell
python scripts/ingest_amazon.py --category Electronics --reviews-file data/cache/amazon_reviews_2023/Electronics_reviews.jsonl --metadata-file data/cache/amazon_reviews_2023/Electronics_metadata.jsonl --min-reviews 15 --max-users 200 --extra-products 150 --review-limit 200000 --verify
```

---

## Holdout Split

Run after ingestion, before persona generation:

```powershell
python scripts/create_holdout_split.py --category Health_and_Household
python scripts/create_holdout_split.py --category Electronics
python scripts/create_holdout_split.py --category Beauty_and_Personal_Care
```

Holdout splitting is deterministic and per user. Reviews are filtered through matching `amazon_product_metadata` rows because `amazon_reviews` has no category column.

Each user's reviews are split into approximately 70% `persona_train`, 15% `task_a_holdout`, and 15% `task_b_holdout`. For example, 12 reviews become 8 persona reviews, 2 Task A holdout reviews, and 2 Task B holdout reviews.

If a category has already been split, pass `--overwrite` to intentionally re-split it.

---

## Finding Test IDs

Check whether a category is ready for Task A and Task B smoke tests:

```powershell
python scripts/check_category_readiness.py --category Health_and_Household
```

List evaluation-friendly users:

```powershell
python scripts/list_eval_users.py --category Health_and_Household --limit 10
python scripts/list_eval_users.py --category Health_and_Household --task task_a --require-persona --limit 10
python scripts/list_eval_users.py --category Health_and_Household --task task_b --require-persona --require-preference-vector --limit 10
```

**Picking a user for Task A:**

1. Choose a row where `has_persona=true` and `task_a_holdout_count>0`.
2. List their holdout reviews to copy a `review_id` or `parent_asin`:

```powershell
python scripts/list_user_holdouts.py --user-id <USER_ID> --category Health_and_Household
```

**Picking a user for Task B:**

1. Choose a row where `has_persona=true`, `has_preference_vector=true`, and `task_b_holdout_count>0`.

**List embedded products:**

```powershell
python scripts/list_embedded_products.py --category Health_and_Household --limit 10
```
