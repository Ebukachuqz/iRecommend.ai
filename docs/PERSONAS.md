# Persona Generation

This document covers generating user personas from `persona_train` review history.

---

## Overview

Persona generation is category-aware. It uses only `task_split='persona_train'` reviews that belong to the requested `amazon_product_metadata.category`. `task_a_holdout` and `task_b_holdout` reviews are reserved for evaluation and are never used to build personas.

`amazon_reviews` does not have or require a `category` column. The category filter is applied through the join with `amazon_product_metadata`.

---

## Commands

```powershell
python scripts/generate_personas.py --category Health_and_Household --limit 20
python scripts/generate_personas.py --category Electronics --limit 20
python scripts/generate_personas.py --category Beauty_and_Personal_Care --limit 20
```

Limit the number of reviews sent to the LLM per user (default is 10):

```powershell
python scripts/generate_personas.py --category All_Beauty --limit 20 --max-reviews-per-user 10
```

---

## Behaviour

- Skips users who already have a persona in the requested category by default.
- Pass `--force` to intentionally regenerate existing personas.
- Sends at most 10 reviews per user to the LLM by default to keep prompt length manageable. Use `--max-reviews-per-user` to override this for experiments.
- The selected review IDs are stored in `user_personas.source_review_ids` and included in the persona run summary.

---

## Source Review Traceability

The persona run summary includes:

- Which review IDs were selected (`source_review_ids`).
- The persona version used.
- The model and prompt version.

This allows persona regeneration to be traced and reproduced.
