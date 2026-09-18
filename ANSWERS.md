# A/B Test Sanity Check — ANSWERS

**Data:** `experiment_results.csv` — 14,000 rows, 14,000 unique `user_id`s, columns `user_id, segment, variant, converted`. No missing values, no malformed rows, `converted ∈ {0,1}`.

**Segments analysed:** `app_store`, `influencer`, `organic`, `paid_search`, `referral`.

---

## Q1 — Overall (naive) treatment vs control

| Variant | Users (n) | Converted | Conversion rate |
|---|---|---|---|
| control | 7,136 | 1,414 | 19.815022% |
| treatment | 6,864 | 1,814 | 26.427739% |

**Naive difference in conversion rate = +6.6127 pp** (treatment − control).

---

## Q2 — Breakdown by segment

| Segment | Total n | Control n | Control conv.% | Treatment n | Treatment conv.% | Lift (pp) |
|---|---|---|---|---|---|---|
| app_store | 1,885 | 925 | 8.757% | 960 | 20.000% | **+11.243** |
| influencer | 250 | 119 | 23.529% | 131 | 16.794% | **−6.736** |
| organic | 4,215 | 1,298 | 35.285% | 2,917 | 35.070% | −0.215 |
| paid_search | 4,812 | 3,353 | 15.180% | 1,459 | 14.393% | −0.787 |
| referral | 2,838 | 1,441 | 23.456% | 1,397 | 26.271% | **+2.815** |

Significance (two-proportion z-test): `app_store` p≈0.0000 (z=6.93), `influencer` p=0.1836, `organic` p=0.8927, `paid_search` p=0.4815, `referral` p=0.0828.

**Segment whose lift looks impressive but is NOT trustworthy: `influencer`.**
Its −6.736 pp swing is the largest per-segment effect in the data (a −28.6% relative drop from 23.5% → 16.8%), which looks dramatic. But it has only **250 users** (119 control / 131 treatment), its 95% CI spans [−16.69, +3.22] pp (crosses zero), and p=0.18 — far from significant. The "effect" is well within random noise for a sample that small; you cannot trust a point estimate from 119–131 observations.

---

## Q3 — Mix-adjusted overall lift

**+1.63 pp** (exactly 1.628943 pp, computed below).

Weight each segment's own treatment-vs-control lift by that segment's share of the total population (14,000), not by its sample size inside treatment:

| Segment | Population share | Segment lift (pp) | Contribution (pp) |
|---|---|---|---|
| app_store | 0.13464 | +11.243 | +1.5138 |
| influencer | 0.01786 | −6.736 | −0.1203 |
| organic | 0.30107 | −0.215 | −0.0647 |
| paid_search | 0.34371 | −0.787 | −0.2705 |
| referral | 0.20271 | +2.815 | +0.5706 |
| **Sum** | 1.0000 | | **+1.6289** |

**Why is this different from Q1 (6.61 vs 1.63)?**

The naive 6.61 pp is inflated by **assignment imbalance across segments** (and the resulting composition difference between the arms), not by the treatment itself. Treatment was heavily over-served to `organic` (69.2% of organic users are treatment) while control was heavily over-served to `paid_search` (69.7% of paid_search users are control). Since `organic` converts at ~35% no matter the variant and `paid_search` at ~15%, the treatment arm's *mix* was richer in high-converting users than the control arm's. Weighting each segment equally by population share isolates the treatment effect from that compositional luck — and the residual effect is only ~1.63 pp. Standardized (same-mix) rates confirm this: applied to the identical population mix, control = 22.195%, treatment = 23.824%, difference = 1.629 pp.

---

## Q4 — Segment with a real, meaningful positive effect

**`app_store`.**

Evidence: largest lift in the data (+11.243 pp, 8.76% → 20.00%), based on a healthy sample (1,885 users; 925/960 split), statistically significant beyond any reasonable doubt (z=6.93, p<0.0001), 95% CI [+8.13, +14.36] pp entirely above zero, and — unlike every other segment — assignment inside app_store is balanced (50.9% treatment, 49.1% control), so the comparison isn't confounded by mix. `referral` (+2.8 pp) is suggestive but not conclusive (p=0.08, CI crosses zero), so it is not called a real effect.

---

## Q5 — Bonus: assignment mechanics

Overall treatment share is 49.0% (6,864/14,000), close to 50/50 — but the split is **not uniform within segments**:

| Segment | n | Treatment share |
|---|---|---|
| app_store | 1,885 | 50.9% |
| influencer | 250 | 52.4% |
| organic | 4,215 | **69.2%** |
| paid_search | 4,812 | **30.3%** |
| referral | 2,838 | 49.2% |

A chi-square test of independence (segment × variant) gives χ² = 1364.5 on 4 df (p ≈ 10⁻²⁹⁰+) — assignment is wildly non-random with respect to segment. If the 50/50 flag had been applied globally with per-user coins, each segment should sit within ~±1.5–2.5 pp of 50%; organic and paid_search are ~19–20 pp off.

So: **yes, something looks off.** The new flow was not randomly assigned across the population — it was systematically biased toward organic users and away from paid_search users. Additional checks (user_id min/max/mean, parity, and interleaving across the 100001–114000 range) show the IDs are well-mixed in both arms, so this isn't a chronological cohort artifact; it's a genuine per-segment assignment bias that renders the top-line comparison misleading and is exactly why the mix-adjusted number (Q3) correctly drops from 6.61 → 1.63 pp.

---

## How I got the numbers (reproducibility)

Scripts in this directory:

- `analyze_experiment.py` — first pass: overall rates, segment table, two-proportion z-tests, population-weighted lift, assignment balance (pure Python stdlib).
- `verify_experiment.py` — independent second pass written with different logic (per-cell counters, Wald 95% CIs, same-mix standardization, duplicate/malformed check) to cross-check every headline number.

Both scripts print the exact values quoted above. Run: `python analyze_experiment.py experiment_results.csv` and `python verify_experiment.py experiment_results.csv`.

Numeric answers also in `answers.json` for automated fact-checking.

---

## Investigation process (what I did and what turned out to be dead ends)

- Loaded the CSV and validated it first: 14,000 rows, 14,000 unique `user_id`s, 0 malformed rows, `converted` strictly 0/1, exactly 5 segments × 2 variants.
- Computed Q1 naive rates and lift (+6.6127 pp) and sample sizes per variant.
- Broke the comparison down by segment; ran two-proportion z-tests per segment to get significance rather than relying on eyeballing.
- Flagged `influencer` as impressive-looking but unreliable solely on sample size (250 users) — p=0.18 and a CI crossing zero.
- Computed the population-weighted lift (1.628943 → 1.63 pp) and verified it a second, independent way by standardizing both arms onto the same population mix (difference = 1.628943 pp, exact match).
- Investigated why naive ≠ adjusted: compared segment composition of each arm, which exposed the imbalance (organic over-treated, paid_search over-controlled).
- Computed χ² (1364.5, 4 df) to confirm assignment non-independence and rule out chance.
- **Dead end #1:** I initially suspected a chronological/cohort artifact (e.g., treatment assigned to early IDs then the flow changed). Checked min/max/mean/parity of user_id per variant+segment: IDs are fully interleaved across the whole 100001–114000 range with near-identical means (~107,000) — no cohort/ordering explanation, which only reinforces that the bias is structural per-segment.
- **Dead end #2:** Suspected the `referral` segment might carry a real positive effect. Its +2.8 pp and p=0.08 are suggestive (and 49.2% treatment share is balanced), but the CI crosses zero, so I did not elevate it to a "real effect" — app_store is the only defensible one.
- **Dead end #3:** Considered whether `app_store`'s impressive +11.2 pp could be a small-sample fluke like influencer. Ruled out: n=1,885, balanced 50.9% assignment, p<0.0001, tight CI — it is the one robust finding.