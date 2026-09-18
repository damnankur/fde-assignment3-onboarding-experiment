#!/usr/bin/env python3
"""Analyze onboarding experiment results (A/B test sanity check). Pure stdlib."""
import csv
import json
import math
import sys
from collections import Counter, defaultdict

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "experiment_results.csv"

rows = []
errors = []
seen_ids = {}
with open(CSV_PATH, "r", newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    for i, r in enumerate(reader, start=2):
        uid = r.get("user_id", "").strip()
        seg = r.get("segment", "").strip()
        var = r.get("variant", "").strip()
        conv = r.get("converted", "").strip()
        if not uid or not seg or not var or conv == "":
            errors.append((i, "missing field", r))
            continue
        # re-parse converted (lenient)
        try:
            cv = int(conv)
        except ValueError:
            errors.append((i, "bad converted", conv))
            continue
        if seen_ids.get(uid, "") != "":
            errors.append((i, f"duplicate user_id {uid} seen before at row {seen_ids[uid]}"))
        seen_ids[uid] = i
        rows.append({"uid": uid, "seg": seg, "var": var, "conv": cv})

print("=== OVERVIEW ===")
print("columns:", fields)
print("total rows:", len(rows))
print("unique user_ids:", len(seen_ids))
print("data errors:", len(errors))
for e in errors[:20]:
    print("  ERROR:", e)

variants = sorted(set(r["var"] for r in rows))
segments = sorted(set(r["seg"] for r in rows))
print("variants:", variants)
print("segments:", segments)
print("converted value domain:", sorted(set(r["conv"] for r in rows)))

# ---------- helpers ----------
def pool(rs):
    d = defaultdict(lambda: {"n": 0, "conv": 0})
    for r in rs:
        s = d[r["var"]]
        s["n"] += 1
        s["conv"] += r["conv"]
    return d

def cr(n, c):
    return c / n if n else 0.0

def lift(ctl, trt):
    return (cr(*trt) - cr(*ctl)) * 100.0  # pp

# ---------- Q1 ----------
print("\n=== Q1: OVERALL NAIVE ===")
d = pool(rows)
for v in variants:
    print(f"  {v}: n={d[v]['n']}  converted={d[v]['conv']}  rate={cr(d[v]['n'], d[v]['conv'])*100:.4f}%")
q1_lift = lift((d["control"]["n"], d["control"]["conv"]), (d["treatment"]["n"], d["treatment"]["conv"]))
print(f"  naive lift = {q1_lift:.4f} pp")

# ---------- Q2: by segment ----------
print("\n=== Q2: BY SEGMENT ===")
seg_stats = {}
for s in segments:
    rs = [r for r in rows if r["seg"] == s]
    d = pool(rs)
    c = d["control"]; t = d["treatment"]
    l = lift((c["n"], c["conv"]), (t["n"], t["conv"]))
    seg_stats[s] = {"n": len(rs), "control": c, "treatment": t, "lift_pp": l}
    print(f"  {s}: n_total={len(rs)} | control n={c['n']} rate={cr(c['n'], c['conv'])*100:.3f}% | treatment n={t['n']} rate={cr(t['n'], t['conv'])*100:.3f}% | lift={l:+.3f} pp")

# significance: two-proportion z test (normal approx), stdlib only
def ztest_diff(c, t):
    n1, x1 = c; n2, x2 = t
    p1 = x1 / n1; p2 = x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return float("inf"), 0.0
    z = (p2 - p1) / se
    # two-tailed p via erfc
    pv = math.erfc(abs(z) / math.sqrt(2))
    return z, pv

print("\n  -- significance (two-proportion z) --")
for s in segments:
    c = seg_stats[s]["control"]; t = seg_stats[s]["treatment"]
    z, pv = ztest_diff((c["n"], c["conv"]), (t["n"], t["conv"]))
    print(f"  {s}: z={z:+.3f}  p={pv:.4f}")

# ---------- Q3: mix-adjusted lift ----------
print("\n=== Q3: MIX-ADJUSTED LIFT ===")
total_n = len(rows)
weighted = 0.0
for s in segments:
    w = seg_stats[s]["n"] / total_n
    weighted += w * seg_stats[s]["lift_pp"]
print(f"  population-weighted lift = {weighted:.2f} pp  (exact {weighted:.6f})")

# per-segment weights by segment population share
for s in segments:
    print(f"    {s}: share={seg_stats[s]['n']/total_n:.4f} lift={seg_stats[s]['lift_pp']:+.3f} contribution={seg_stats[s]['n']/total_n*seg_stats[s]['lift_pp']:+.4f}")

# ---------- Q5: assignment balance ----------
print("\n=== Q5: ASSIGNMENT BALANCE ===")
assign = {}
for s in segments:
    rs = [r for r in rows if r["seg"] == s]
    cnt = Counter(r["var"] for r in rs)
    trt = cnt.get("treatment", 0); ctl = cnt.get("control", 0)
    assign[s] = (trt, ctl)
    print(f"  {s}: treatment={trt} ({trt/len(rs)*100:.1f}%) control={ctl} ({ctl/len(rs)*100:.1f}%)")

# overall treatment share
ct = Counter(r["var"] for r in rows)
print(f"  OVERALL: treatment={ct['treatment']} ({ct['treatment']/total_n*100:.1f}%) control={ct['control']} ({ct['control']/total_n*100:.1f}%)")

# ---------- JSON ----------
answers = {
    "q1_naive_lift_pp": round(q1_lift, 6),
    "q1_n_control": d["control"]["n"],
    "q1_n_treatment": d["treatment"]["n"],
    "q2_untrustworthy_segment": "",
    "q3_mix_adjusted_lift_pp": round(weighted, 2),
    "q4_real_effect_segment": "",
}
print("\n=== answers (provisional; qualitative fields filled manually) ===")
print(json.dumps(answers, indent=2))