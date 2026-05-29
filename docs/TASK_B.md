# Task B: Personalised Recommendation

Task B delivers personalised product recommendations given a user persona and a free-text request. It uses multi-source retrieval, transparent scoring, and LLM reranking.

---

## Prerequisites

Task B requires product embeddings and user preference vectors to be built before meaningful semantic retrieval is possible.

---

## Step 1: Embed Products

Product embeddings enable semantic retrieval. Build embeddings for a category:

```powershell
python scripts/embed_products.py --category Health_and_Household --limit 100
python scripts/embed_products.py --category All_Beauty --limit 100 --dry-run
python scripts/embed_products.py --category All_Beauty --force-reembed
```

**What goes into the embedding text:**

Product embeddings are built from rich metadata: title, broad project category, Amazon `main_category`, Amazon `categories` hierarchy, features, description, brand/store, price tier, and useful details.

The exact raw price is not embedded. The script uses semantic tiers (budget, mid-range, premium, luxury) because those meanings are more stable than a changing seller price. The text used for each embedding is stored in `product_embeddings.product_text` for debugging and reproducibility.

Re-run with `--force-reembed` when the product text strategy changes, especially after category hierarchy text changes.

---

## Step 2: Build User Preference Vectors

Preference vectors represent a user's aggregate taste in a category, built from their liked `persona_train` products.

Build for a single user:

```powershell
python scripts/build_user_preference_vectors.py --user-id <USER_ID> --category All_Beauty
```

Build for a batch of users in a category (from `user_personas`):

```powershell
python scripts/build_user_preference_vectors.py --category Health_and_Household --limit 20
python scripts/build_user_preference_vectors.py --category Electronics --limit 20
python scripts/build_user_preference_vectors.py --category Beauty_and_Personal_Care --limit 20
```

Preference vectors are category-specific and unit-normalised after averaging liked product embeddings. They are built from rating >= 4 `persona_train` reviews whose products match the requested metadata category.

---

## Step 3: Run Recommendations

```powershell
python scripts/run_task_b_recommendation.py --user-id <USER_ID> --request "I want something affordable and gentle"
```

Cold-start (no stored persona or preference vector required):

```powershell
python scripts/run_task_b_recommendation.py --cold-start --request "I need affordable skincare for oily skin"
```

---

## Retrieval Sources

Task B retrieves candidates from six sources before scoring:

| Source | Description |
|---|---|
| Preference vector search | Semantic similarity to the user's preference vector |
| Request query search | Semantic similarity to the user's free-text request |
| Collaborative filtering | Signals from similar users' preference vectors |
| Bought-together | Related products from liked `persona_train` items |
| Attribute matching | Persona and intent attribute-based filtering |
| Quality/popularity fallback | Top-rated products as a fallback when retrieval is sparse |

---

## Special Modes

**Cold-start:** Builds a low-confidence starter persona from the request and context signals. Does not require a stored preference vector.

**Cross-domain:** Cross-domain recommendations are conservative. Close categories (e.g., beauty and skincare) stay in-domain. Meaningfully different domains (e.g., beauty -> electronics) use transferable values such as price sensitivity, quality, reliability, simplicity, durability, and value for money.

**Multi-turn sessions:** Refine active constraints and exclude products already shown in the same session. Multi-turn context is managed through session state.

---

## Custom Persona JSON

Task B accepts a custom persona JSON through `POST /recommendations/generate`. This supports the direct persona -> recommendations flow without requiring a stored user.

The normaliser supports common fields including `likes`, `interests`, `preferred_products`, `dislikes`, `avoid`, `concerns`, `values`, `priorities`, `budget`, `tone`, `average_rating`, and category signals. It does not attempt to map every possible arbitrary schema.

---

## Audit Trail

Task B stores a complete audit trail for evaluation and debugging:

| Table | Contents |
|---|---|
| `recommendation_runs` | Final recommendations, model name, prompt version, persona version |
| `intent_plans` | Structured reasoning brief produced by the intent planner |
| `recommendation_candidates` | Retrieved and scored candidate pool with before/after rerank ranks |

Intent and candidate traces are best-effort: a trace insert failure does not block recommendation generation.
