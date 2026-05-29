# Task A: Review and Rating Simulation

Task A simulates what rating a specific user would give to a product and generates a realistic review in their voice, given their persona.

---

## Run Review Simulation

Simulate using a specific product:

```powershell
python scripts/run_task_a_simulation.py --user-id <USER_ID> --parent-asin <PARENT_ASIN>
```

Simulate using the user's holdout review as the target product:

```powershell
python scripts/run_task_a_simulation.py --user-id <USER_ID> --use-holdout
```

Nigerian mode (localised persona variant):

```powershell
python scripts/run_task_a_simulation.py --user-id <USER_ID> --parent-asin <PARENT_ASIN> --nigerian-mode
```

Successful simulations are stored in the `simulation_results` table.

---

## Custom Persona and Product JSON

Task A also accepts custom persona and product JSON through `POST /reviews/simulate`. This supports the direct persona + product -> review/rating flow without requiring a stored user in the database.

The backend:

- Normalises common field variants.
- Preserves unknown persona fields under `extra_persona_signals.unmapped_fields`.
- Preserves unknown product fields under `details.custom_fields`.
- Rejects only inputs that are too empty to support the task.

---

## Batch Simulation (Evaluation Prep)

Before running Task A evaluation, generate simulation results for all holdout reviews in a category. The batch script:

- Targets only `task_a_holdout` rows for the specified category.
- Skips reviews already simulated.
- Skips users without a persona.
- Continues on individual failures.

```powershell
python scripts/run_task_a_batch.py --category Health_and_Household --limit 50
python scripts/run_task_a_batch.py --category Electronics --limit 50
python scripts/run_task_a_batch.py --category Beauty_and_Personal_Care --limit 50
```

Preview without calling the LLM:

```powershell
python scripts/run_task_a_batch.py --category Health_and_Household --limit 50 --dry-run
```

---

## Rating Prediction

Ratings blend statistical prediction with LLM prediction via calibrated weighting:

- 65% user average rating (from `persona_train` reviews).
- 35% product average rating.
- Adjustments for product quality, preference match, and price fit.

The final predicted rating is a blend of the statistical estimate and the LLM's own rating prediction.

---

## Outputs

| Table | Contents |
|---|---|
| `simulation_results` | Predicted rating, simulated review text, persona version, model name, prompt version |
