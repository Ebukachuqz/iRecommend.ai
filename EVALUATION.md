# 5. Evaluation

This section presents the empirical evaluation of iRecommend across both core tasks: review and rating simulation (Task A) and personalised product recommendation (Task B). Beyond standard task metrics, we apply a multi-dimensional diagnostic framework adapted from the Dynamic Contextual Responsibility (DCR) model proposed by Ibitoye et al. (2026), which evaluates whether outputs are not only accurate but also responsibly produced: traceable, grounded, and contextually appropriate.

All results reported here are derived from the evaluation run of 28 May 2026, using qwen/qwen3-32b as the language model, sentence-transformers/all-MiniLM-L6-v2 for product embeddings, and v1 personas generated via LangChain and Groq. The full evaluation command, per-row results, and summary statistics are reproducible from the artifacts in `outputs/evaluation/`.

---

## 5.1 Evaluation Design

### Holdout Strategy

iRecommend uses a chronological holdout split rather than random sampling. For each user, reviews are ordered by timestamp and partitioned into three groups via the `task_split` column:

- **persona_train**: the bulk of each user's review history, used exclusively to construct the behavioural persona.
- **task_a_holdout**: the user's most recent review, reserved as ground truth for rating and review simulation evaluation.
- **task_b_holdout**: the second-most-recent review with a rating of 4 or higher, reserved as ground truth for recommendation evaluation.

The choice of chronological over random holdout is deliberate and consequential. iRecommend always predicts future behaviour from past history: the persona is built from earlier reviews, and both simulation and recommendation are forward-looking inferences. A random holdout would allow temporally later reviews to leak into persona construction, inflating evaluation scores by granting the system access to information it would never have in deployment. Chronological splitting simulates real operating conditions, where the system must generalise from a user's history to their next interaction.

### Task-Specific Holdout Design

The two holdout sets serve different evaluation goals. Task A holdout reviews are unrestricted by rating: the system must predict any rating a user might give, including negative ones. Task B holdout reviews are restricted to ratings of 4 or higher because only positively-rated items constitute valid ground truth for a recommendation system. A product the user disliked is not a product the system should have recommended; including it would introduce false negatives into the ranking metrics.

### Sample and Scope

The evaluation covers three Amazon product categories: Health and Household, Electronics, and Beauty and Personal Care. Task A evaluates 50 holdout reviews drawn from 7 users across all three categories. Task B evaluates 100 holdout reviews drawn from 51 users, with a per-user cap of 2 holdout evaluations to ensure user diversity.

A critical precondition for Task B evaluation is that the holdout product must remain eligible in the recommendation candidate pool. If the holdout product were excluded through filtering, deduplication, or a retrieval failure, then HitRate, NDCG, and MRR would be structurally unable to register a hit, rendering the metrics invalid. All 100 Task B evaluations verified this condition: the holdout product was confirmed present in the candidate pool in every case, with zero wrongful exclusions.

---

## 5.2 Task A: Rating and Review Simulation

Task A evaluates the system's ability to simulate how a specific user would rate and review a product they have not yet reviewed. Each evaluation compares the system's predicted rating and generated review text against the user's actual holdout review, using the persona built exclusively from `persona_train` data.

### 5.2.1 Rating Prediction

The practically important metric is within-1-star accuracy: 90% of predicted ratings fell within one star of the true rating on the 1-5 scale. This indicates that the system reliably captures the direction and approximate magnitude of a user's preference, even when it does not predict the exact value.

Exact rating accuracy was 38%. On a 5-point discrete scale, exact match is a strict criterion. A prediction of 4.7 rounded to 5 is counted as correct, but 4.4 rounded to 4 is not, even though the error is small. The 38% rate reflects this strictness rather than a fundamental failure in rating calibration.

The system's MAE of 0.648 did not outperform the user-average baseline MAE of 0.606. The baseline simply predicts each user's mean historical rating from their `persona_train` reviews, with no product-specific adjustment. This result indicates that the additional signals incorporated by the rating predictor (product quality adjustment, preference matching, and price fit) did not, in aggregate, improve over the user's historical average at this sample size. This is a substantive finding: it suggests that the predictor's component signals require either richer persona data, broader category coverage, or recalibrated blending weights to add value beyond the strong prior of user-average behaviour. We treat this as a calibration opportunity rather than a structural limitation.

The system exhibited a slight pessimistic bias of -0.115, meaning it under-predicted ratings by approximately one-tenth of a star on average. This is counterintuitive: LLMs typically exhibit a positivity bias in generative tasks. The pessimistic direction is attributable to the statistical predictor component, which blends the LLM's rating estimate with the user's historical average. Users with moderate average ratings, common among prolific reviewers, pull the blended prediction downward relative to the LLM's typically generous estimate.

### 5.2.2 Review Text Quality

Two complementary metrics assess review text quality. ROUGE-L, which measures longest common subsequence overlap, averaged 0.107. BERTScore F1, which measures contextual semantic similarity using transformer embeddings, averaged 0.751.

The discrepancy between these metrics is informative. Low ROUGE-L with moderate BERTScore indicates that the system captures the semantic content, topic focus, and evaluative stance of user reviews but does not reproduce their lexical phrasing. This divergence is expected and, for this task, acceptable. Review simulation should reproduce a user's *opinions and concerns*, not their exact words. A user who consistently complains about strong scents should produce a scent-sensitivity-focused review. Verbatim reproduction would, paradoxically, indicate memorisation rather than generalisation. BERTScore F1 at 0.751 confirms that the system is generating reviews in the right semantic neighbourhood of the user's actual writing.

The length analysis reveals a persona fidelity gap. Simulated reviews are on average 29.2 words longer than the specific holdout review they are compared against, but 43.6 words shorter than the user's typical review length computed from their training history. This pattern suggests that the simulator converges toward a middle-length output, longer than terse reviews but shorter than verbose ones, rather than faithfully matching the length distribution of each individual user. Capturing per-user verbosity is a dimension of persona fidelity that the current v1 persona representation does not explicitly encode.

### 5.2.3 Summary of Results

| Metric | System | Baseline |
|---|---|---|
| MAE | 0.648 | 0.606 |
| RMSE | 0.892 | n/a |
| Exact rating accuracy | 38% | n/a |
| Within-1-star accuracy | 90% | n/a |
| Optimistic bias | -0.115 | n/a |
| ROUGE-L | 0.107 | n/a |
| BERTScore F1 | 0.751 | n/a |

*Baseline: predict user's mean rating from persona_train reviews. N = 50 holdout reviews, 7 users, 3 categories.*

---

## 5.3 Task B: Personalised Recommendation

Task B evaluates the system's ability to recommend products a user is likely to appreciate, given their persona and a natural-language request. Evaluation uses a leave-one-out protocol: for each holdout review, the system generates a ranked list of 10 recommendations (K = 10), and success is measured by whether the holdout product, a product the user actually liked, appears in that list.

### 5.3.1 Recommendation Performance

| Metric | System | Popularity Baseline |
|---|---|---|
| HitRate@10 | 7% | 1% |
| NDCG@10 | 0.048 | 0.003 |
| MRR@10 | 0.041 | 0.0014 |

The popularity baseline ranks products by `rating_number` descending within the same category, a non-personalised strategy that surfaces the most-reviewed products. Against this baseline, the personalised system achieves a 7x improvement in HitRate@10, approximately 16x in NDCG@10, and approximately 29x in MRR@10. These are not marginal gains; they demonstrate that persona-driven retrieval, intent planning, and LLM reranking collectively produce a qualitatively different recommendation distribution than popularity sorting.

When the system does surface the holdout product, it places it at an average rank of 3.43 out of 10. This means successful recommendations are ranked prominently, in the top third of the list, rather than buried at positions 9 or 10. The combination of moderate hit rate with strong rank quality suggests that when the retrieval and reranking pipeline identifies the right product, it also recognises its relevance.

In absolute terms, a 7% HitRate@10 means the system correctly identifies a specific item a user liked from a pool of thousands of candidates in approximately 1 out of every 14 cases. The task is genuinely hard: predicting a single specific product from a large catalogue, given only a persona and a request, is a needle-in-a-haystack problem. The appropriate frame of reference is not whether 7% is high in isolation, but whether the system meaningfully outperforms the non-personalised alternative. It does, by a substantial margin.

### 5.3.2 Evaluation Integrity

The critical precondition for valid ranking evaluation, that the holdout product must remain in the candidate pool, was verified for all 100 evaluated cases. Zero holdout products were wrongly excluded from the pool through filtering, deduplication, or retrieval failure. This matters because if the holdout had been absent from the candidate set, HitRate, NDCG, and MRR would all be structurally incapable of registering a hit, and the resulting metrics would measure retrieval coverage rather than ranking quality. The 7% HitRate reported here is a genuine measurement of ranking performance, not an artefact of experimental design.

### 5.3.3 Skipping Analysis

Of 713 candidate holdout rows scanned during evaluation, 100 were successfully evaluated and 613 were skipped. The two dominant skip reasons are structural rather than indicative of system failure:

1. **Per-user cap (456 skipped).** The `max_holdouts_per_user=2` constraint deliberately limits each user to at most 2 evaluated holdout reviews. Without this cap, prolific reviewers who may have dozens of holdout items would dominate the evaluation sample, reducing user diversity and inflating or deflating aggregate metrics based on the behaviour of a few individuals. The 456 skipped rows represent valid holdout data from users who had already contributed their maximum allocation.

2. **Missing personas (156 skipped).** These users have review history in the database but have not yet had personas generated. This is a data-readiness gap, not a system error: persona generation is a batch process that had not yet been run for all eligible users at evaluation time. Generating personas for these users would expand the evaluable pool significantly and is a direct path to more comprehensive evaluation.

One additional row was skipped because the holdout product appeared in the user's `persona_train` data, a correct exclusion since recommending a product the user has already reviewed would be meaningless. Zero errors and zero recommendation pipeline failures were recorded across all 713 scanned rows.

---

## 5.4 DCR-Inspired Responsibility Diagnostics

### 5.4.1 Motivation and Framework

Standard recommendation evaluation metrics (ROUGE-L, RMSE, NDCG, HitRate) measure whether system outputs match ground truth. They do not measure whether those outputs were *responsibly produced*. A simulated review can score well on BERTScore while citing a product feature that does not appear in the product's metadata. A recommendation can achieve a hit at position 3 while producing a run with no traceable intent plan, no recorded retrieval sources, and no auditable score breakdown. These are qualitatively different kinds of failure, and standard metrics are blind to them.

Ibitoye et al. (2026) address exactly this gap with the Dynamic Contextual Responsibility (DCR) framework. The paper argues that evaluating LLMs only on task performance metrics obscures contextual and governance failures that matter in socio-technical deployment. DCR proposes five evaluation dimensions (Ethical Foundations E, Contextual Layer C, Behavioural Properties B, Governance Properties G, and Temporal Dynamics T), formalised as $R = F(E, C, B, G, T)$. Their key empirical finding is that approximately 22% of outputs classified as responsible under standard composite metrics were reclassified as at-risk or failing once contextual and governance dimensions were applied. This reveals that scalar benchmarks can mask latent failures that only surface under multi-dimensional scrutiny.

### 5.4.2 Domain Adaptation

iRecommend does not use the benchmarks from Ibitoye et al. (TruthfulQA, FEVER, and HotpotQA), which are designed for general-purpose LLM factuality and reasoning evaluation. A recommendation system requires domain-specific diagnostics. Instead, we adapt the DCR philosophy into three recommender-specific diagnostic dimensions, each grounded in the original framework's conceptual layer:

| DCR Dimension | iRecommend Adaptation |
|---|---|
| **Behavioural (B)** | Hallucination detection in simulated reviews; predicted rating within the valid 1-5 range; review text non-empty and of minimum length; category contradiction check between review content and product metadata |
| **Governance (G)** | Simulation result stored for every Task A output; recommendation run record stored for every Task B output; intent plan stored for every recommendation; retrieval sources, candidate counts, and score breakdowns recorded; model name, prompt version, and persona version recorded for traceability |
| **Contextual (C)** | Correct product category used throughout the pipeline; already-reviewed products excluded from recommendations; holdout product present in the candidate pool during evaluation; recommendation output reflects request constraints |

The stoplight classification is directly adapted from DCR's traffic-light mechanism:

- **Green**: the output passes both standard task metrics *and* all DCR behavioural, governance, and contextual checks. For Task A, this requires absolute rating error of 1.5 stars or less, ROUGE-L of 0.10 or higher, and all checks passing. For Task B, this requires a hit in the top K with a complete audit trail.
- **Yellow**: the output is usable but exhibits a weaker task metric score or incomplete secondary trace. The system produced a valid output but either did not meet the Green threshold on task performance or had a minor governance gap.
- **Red**: a hard failure. This includes hallucinated product facts, missing primary traces (no simulation result or recommendation run stored), wrong category used, a reviewed product appearing in recommendations, or the holdout product being excluded from the candidate pool.

The reclassification analysis adapts DCR's two-pass evaluation methodology. Outputs are first classified using standard task metrics alone (pass/fail on rating error, ROUGE-L, hit@K). They are then re-evaluated with the full set of DCR checks applied. Any output that passed standard metrics but fails a DCR check is *downgraded*, reclassified from Green to Yellow or Red. The downgrade rate measures the gap between metric-apparent quality and responsible-output quality, directly mirroring the methodology that produced the 22% reclassification finding in Ibitoye et al.

### 5.4.3 DCR Findings

**Task A.** Of 50 evaluated outputs, 27 (54%) were classified Green: they passed both standard task metric thresholds and all DCR checks. The remaining 23 (46%) were classified Yellow: they produced valid, usable simulation outputs but fell below the Green threshold on rating error or ROUGE-L. Zero outputs were classified Red. No hallucinations were detected, no category contradictions were found, and all 50 simulation results were fully stored with model name, prompt version, and persona version recorded.

The reclassification analysis found a downgrade rate of 0%. Every output that passed standard task metrics also passed all DCR governance and contextual checks. This indicates that when the simulation pipeline produces quality outputs, outputs that meet the rating error and ROUGE-L thresholds, it also produces traceable, grounded, and category-correct outputs. The two quality dimensions are aligned in the current system.

**Task B.** Of 100 evaluated outputs, 7 (7%) were classified Green: the holdout product appeared in the top 10 recommendations and the full audit trail (recommendation run, intent plan, retrieval sources, candidate storage, and model/prompt versioning) was complete. The remaining 93 (93%) were classified Yellow: the system produced valid recommendation runs with complete governance traces but did not surface the holdout product in the top 10. Zero outputs were classified Red. No recommendation included a product the user had already reviewed, no holdout product was wrongly excluded from the candidate pool, and every evaluated run had a stored intent plan and retrieval source record.

The reclassification analysis found a downgrade rate of 0%. All 7 outputs that achieved a hit@10 also had complete governance and contextual compliance. No successful recommendation lacked an intent plan, retrieval trace, or auditable score breakdown.

**Comparison with DCR's empirical finding.** Ibitoye et al. reported a 22% reclassification rate in their evaluation of general-purpose LLMs. iRecommend found a 0% reclassification rate. Two interpretations are warranted. First, the system may genuinely produce well-grounded outputs when it performs well. Its architecture was designed with traceability as a first-class concern: intent plans, retrieval sources, score breakdowns, and candidate traces are stored for every recommendation run, and simulation results carry model name, prompt version, and persona version metadata by construction. The 0% downgrade rate may reflect this architectural commitment to auditability rather than post-hoc compliance. Second, the evaluation sample is small (50 outputs for Task A and 100 for Task B) and may not be sufficient to surface the reclassification patterns that appear at larger scale. A definitive claim about the system's DCR compliance would require evaluation over hundreds of users and thousands of outputs.

---

## 5.5 Limitations

Several limitations qualify the findings presented above and motivate future work.

**Small evaluation sample.** Task A was evaluated on 50 holdout reviews from 7 users, and Task B on 100 holdout reviews from 51 users. While these samples are sufficient to identify trends and validate the evaluation infrastructure, they are not large enough to establish statistically definitive conclusions. Confidence intervals on metrics like HitRate@10 at 7% over 100 trials are wide. Results should be treated as indicative rather than conclusive.

**Rating predictor did not outperform the baseline.** The system's MAE of 0.648 was higher than the user-average baseline's 0.606. The additional predictor signals (product quality adjustment, preference matching, and price fit) did not collectively improve over simply predicting each user's historical mean rating. This gap motivates recalibration of the signal blending weights, incorporation of richer persona data (e.g., per-category rating distributions), and evaluation across a broader set of product categories where user preferences may exhibit more variance.

**Low lexical overlap in review simulation.** ROUGE-L at 0.107 indicates that the system does not reproduce the lexical patterns of user reviews. While BERTScore F1 at 0.751 confirms semantic similarity, the low ROUGE-L raises an open question: does it reflect poor simulation quality, or does it reflect the inherent variability of human review language, where the same user might express the same opinion with entirely different words on different occasions? Addressing this question would require a human evaluation study comparing simulated reviews against user-written reviews for perceived authenticity.

**Incomplete persona coverage.** 156 Task B holdout rows were skipped because no persona existed for the associated user. These users have review history but have not yet undergone persona generation. Expanding persona coverage is a prerequisite for more comprehensive Task B evaluation and would increase both the number of evaluable users and the diversity of the evaluation sample.

**DCR reclassification analysis is inconclusive at this scale.** The 0% downgrade rate may reflect strong system design, given that the architecture stores audit trails by construction, or it may reflect insufficient sample size to surface the governance and contextual failures that appear at scale. Scaling evaluation to hundreds of users and introducing adversarial test cases (e.g., products with sparse metadata, users with contradictory review histories) would provide a more rigorous test of DCR compliance.

---

## Reproducibility

| Parameter | Value |
|---|---|
| Evaluation date | 28 May 2026 |
| LLM | qwen/qwen3-32b |
| Embedding model | sentence-transformers/all-MiniLM-L6-v2 |
| Persona version | v1 |
| Task A prompt | task_a_simulation_v1 |
| Task B prompts | task_b_intent_v1+task_b_reranker_v1 |
| Categories | Health_and_Household, Electronics, Beauty_and_Personal_Care |
| Task A sample | 50 holdout reviews, 7 users |
| Task B sample | 100 holdout reviews, 51 users |
| K (ranking cutoff) | 10 |
| Max holdouts per user | 2 |

*Evaluation artifacts: [task_a_results.json](outputs/evaluation/task_a_results.json), [task_b_results.json](outputs/evaluation/task_b_results.json), [task_a_summary.json](outputs/evaluation/task_a_summary.json), [task_b_summary.json](outputs/evaluation/task_b_summary.json), [evaluation_manifest.json](outputs/evaluation/evaluation_manifest.json).*

*Reference: Ibitoye, O. et al. (2026). "A Dynamic Contextual Responsibility Framework for Evaluating Large Language Models in Socio-Technical Contexts." AI and Ethics, 6:191. https://doi.org/10.1007/s43681-026-01072-9*
