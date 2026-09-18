#!/usr/bin/env python3
"""Independent verification pass for the onboarding experiment analysis.

Recomputes every headline number from the raw CSV using different logic than
analyze_experiment.py (dict-of-tuples vs the earlier per-variant dicts),
checks internal consistency, and computes Wald 95% CIs for segment lifts.
"""
import csv, math, statistics, sys
from collections import Counter

path = sys.argv[1] if len(sys.argv) > 1 else "experiment_results.csv"

agg = {}          # (segment, variant) -> [n, converts, sum_userid]
cnt = Counter()   # (segment, variant) -> count
converts = Counter()

with open(path, newline="", encoding="utf-16") as f:
    rd = csv.reader(f)
    header = next(rd)
    assert header == ["user_id", "segment", "variant", "converted"], header
    uid_seen = set()
    for row in rd:
        uid, seg, var, conv = row
        assert conv in ("0", "1"), conv
        assert (uid, seg, var) and var in ("control", "treatment")
        assert uid not in uid_seen, f"dup {uid}"
        uid_seen.add(uid)
        key = (seg, var)
        cnt[key] += 1
        converts[key] += int(conv)

segments = ["app_store", "influencer", "organic", "paid_search", "referral"]
variants = ["control", "treatment"]

def rate(seg, var):
    n = cnt[(seg, var)]
    return converts[(seg, var)] / n if n else 0.0

N_total = sum(cnt.values())
print(f"rows={N_total} unique_ids={len(uid_seen)}")

# ---- recompute overall (any code path must equal the earlier run) ----
nc = sum(cnt[(s, "control")] for s in segments)
nt = sum(cnt[(s, "treatment")] for s in segments)
xc = sum(converts[(s, "control")] for s in segments)
xt = sum(converts[(s, "treatment")] for s in segments)
rc, rt = xc / nc, xt / nt
print(f"\nQ1 overall:  control n={nc} rate={rc*100:.6f}% | treatment n={nt} rate={rt*100:.6f}%")
print(f"Q1 naive lift = {(rt-rc)*100:.6f} pp  (rounded {(rt-rc)*100:.4f})")

# ---- segment table + CI + assignment ----
print("\nQ2 segment table (rate%, lift pp, 95% CI, assignment balance):")
seg_lift = {}
for s in segments:
    r0, r1 = rate(s, "control"), rate(s, "treatment")
    d = (r1 - r0) * 100
    # Wald CI for the difference in proportions
    z = 1.96
    se = math.sqrt(r0 * (1 - r0) / cnt[(s, "control")] + r1 * (1 - r1) / cnt[(s, "treatment")])
    ci = (d - z * se * 100, d + z * se * 100)
    seg_lift[s] = d
    tot = cnt[(s, "control")] + cnt[(s, "treatment")]
    trt_f = cnt[(s, "treatment")] / tot
    print(f"  {s:12s} n={tot:6d} | ctrl {cnt[(s,'control')]:5d} {r0*100:7.3f}% | trt {cnt[(s,'treatment')]:5d} {r1*100:7.3f}% | lift {d:+7.3f} pp | 95%CI [{ci[0]:+.2f},{ci[1]:+.2f}] | trt share {trt_f*100:.1f}%")

# ---- mix-adjusted ----
print("\nQ3 mix-adjusted lift:")
w = 0.0
for s in segments:
    sh = (cnt[(s, "control")] + cnt[(s, "treatment")]) / N_total
    w += sh * seg_lift[s]
print(f"  sum(segment_share * segment_lift) = {w:.6f} pp -> {w:.2f}")

# ---- recompute weighted lift the other way: standardize on same population mix ----
# Both arms evaluated on the overall population mix -> difference must equal mix-adjusted lift.
rc2 = sum((cnt[(s,"control")]+cnt[(s,"treatment")])/N_total * rate(s,"control") for s in segments)
rt2 = sum((cnt[(s,"control")]+cnt[(s,"treatment")])/N_total * rate(s,"treatment") for s in segments)
print(f"  standardized (same-mix) rates: ctrl {rc2*100:.6f}% trt {rt2*100:.6f}% -> diff {(rt2-rc2)*100:.6f} pp (must equal mix-adjusted lift above)")

# ---- composition of the two arms (why naive != adjusted) ----
print("\n  arm composition (segment share within each arm):")
for v in variants:
    nv = sum(cnt[(s, v)] for s in segments)
    parts = {s: cnt[(s, v)] / nv * 100 for s in segments}
    print(f"  {v:9s}: " + "  ".join(f"{s}={p:.1f}%" for s, p in parts.items()))

# ---- user_id sanity (random vs sequential assignment) ----
print("\nQ5 user_id sanity per variant:")
for v in variants:
    ids = []
    for s in segments:
        # re-read file... simpler: track from second pass
        pass
# re-read to collect ids
arms = {"control": [], "treatment": []}
with open(path, newline="", encoding="utf-16") as f:
    next(csv.reader(f))
    for row in csv.reader(f):
        arms[row[2]].append(int(row[0]))
for v in variants:
    a = arms[v]
    print(f"  {v:9s} n={len(a)} min={min(a)} max={max(a)} mean={statistics.mean(a):.1f}")

print("\nALL RE-CHECKS PASSED IF: weighted rates == Q1 rates above, and sums add up.")