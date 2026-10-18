"""
development_event_forensics.py

DEVELOPMENT-ONLY forensic characterisation of the frozen Code 3B candidate events found by the
Gaussian adequacy study. Decides WHERE a robustness mechanism belongs (LEVEL / OBSERVATION / EDGE /
COMBINATION / INCONCLUSIVE). Characterisation only: no model fitted, no forecasting, no MAE.

Reads ONLY local files (this script imports no network library, so nothing can be downloaded):
  development_adequacy/candidate_jump_events.csv     frozen Code 3B event table
  development_adequacy/dev_split.csv                 dev-train / dev-val membership and denominators
  code4_outputs/code4_cohort_manifest.csv            settled_minutes, canonical_tid
  vitaldb_bt_cache/<tid>.csv.gz                      cached raw tracks (cross-check + single-minute jumps)
  final_holdout_freeze/*                             protection checks only

Event coordinates: start_min / end_min are minutes on the settled clock (tau = 0 at first plausible
BT sample + 15 min). Last observed settled minute = settled_minutes - 1 (the settled series ends at
its last observed minute), cross-checked against the cached tracks.

DISCLOSURE: the Task 8 decision rule below was written AFTER the aggregate pattern counts were shown
in the request, so it is not blind to them. Only round, natural criteria are used (simple majority
for "most events"; one quarter for "credible presence"), stated in the report.
"""

import hashlib
import json
import os

import numpy as np
import pandas as pd

ADQ = "development_adequacy"
CODE4_DIR = "code4_outputs"
FREEZE_DIR = "final_holdout_freeze"
CACHE_DIR = "vitaldb_bt_cache"
OUT = ADQ

PLAUS_LO, PLAUS_HI, EQUIL_MIN, BIN_S = 25.0, 43.0, 15, 60           # frozen Code 4 rules
NEAR_END_MIN = 5                                                      # user-defined group B
DIST_BINS = [(0, 0, "0"), (1, 5, "1-5"), (6, 15, "6-15"), (16, 30, "16-30"), (31, 10 ** 9, ">30")]
FRAC_BINS = [(0, .25, "<25%"), (.25, .50, "25-50%"), (.50, .75, "50-75%"), (.75, .90, "75-90%"), (.90, 10.0, ">90%")]
MAG_LEVELS = [5, 8, 10]
QS = [0.5, 0.9, 0.99]

# ---- Task 8 rule (see DISCLOSURE) ----
CREDIBLE_SHARE = 0.25     # a pattern is "credibly present" if >= 1/4 of interior post-data events, in BOTH splits
EDGE_MAJORITY = 0.50      # edge handling "required" if > 1/2 of all events OR of large (|peak| >= 5 C) events
                          # are terminal-associated, in BOTH splits


# ============================================================================
# TASK 10 (start) — protection
# ============================================================================
def hash_tree(d):
    out = {}
    for root, _, files in os.walk(d):
        for f in sorted(files):
            p = os.path.join(root, f)
            with open(p, "rb") as fh:
                out[p] = hashlib.sha256(fh.read()).hexdigest()
    return out


for d in (CODE4_DIR, FREEZE_DIR, ADQ):
    if not os.path.isdir(d):
        raise SystemExit(f"STOP: required local folder {d}/ is missing.")
HASH_BEFORE = {**hash_tree(CODE4_DIR), **hash_tree(FREEZE_DIR)}
final_ids = set(pd.read_csv(os.path.join(FREEZE_DIR, "final_holdout_case_ids.csv"))["caseid"].astype(int))
dev_ids = set(pd.read_csv(os.path.join(FREEZE_DIR, "development_case_ids.csv"))["caseid"].astype(int))
fman = json.load(open(os.path.join(FREEZE_DIR, "freeze_manifest.json")))
protect = {
    "final_holdout_hash_matches_manifest":
        hashlib.sha256(",".join(str(i) for i in sorted(final_ids)).encode()).hexdigest() == fman["final_holdout_ids_sha256"],
    "development_disjoint_from_final_holdout": not (dev_ids & final_ids),
}
if not all(protect.values()):
    raise SystemExit(f"STOP: protection failed before start: {protect}")

# ============================================================================
# LOAD LOCAL INPUTS (development only)
# ============================================================================
split = pd.read_csv(os.path.join(ADQ, "dev_split.csv"))
ev = pd.read_csv(os.path.join(ADQ, "candidate_jump_events.csv"))
ev["set"] = ev["set"].astype(str)
LOADED = set(ev.caseid.astype(int)) | set(split.caseid.astype(int))
protect["all_loaded_cases_in_development"] = LOADED <= dev_ids
protect["no_final_holdout_case_in_inputs"] = not (LOADED & final_ids)
if not (protect["all_loaded_cases_in_development"] and protect["no_final_holdout_case_in_inputs"]):
    raise SystemExit(f"STOP: inputs contain non-development case IDs: {protect}")
N_CASES = split.dev_split.value_counts().rename({"dev_train": "dev_train", "dev_val": "dev_val"}).to_dict()

man = pd.read_csv(os.path.join(CODE4_DIR, "code4_cohort_manifest.csv"))
man = man[man.caseid.isin(dev_ids)].set_index("caseid")                       # holdout rows dropped at once
missing = []
if "settled_minutes" not in man.columns:
    missing.append("code4_cohort_manifest.csv has no settled_minutes column")


def cached_settled(cid):
    """Same rules as Code 4 / adequacy study. Returns the settled series or None if not cached locally."""
    assert cid in dev_ids and cid not in final_ids
    tid = str(man.loc[cid, "canonical_tid"])
    path = os.path.join(CACHE_DIR, f"{tid}.csv.gz")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path).iloc[:, :2]
    df.columns = ["t", "v"]
    df = df.apply(pd.to_numeric, errors="coerce").dropna().sort_values("t").drop_duplicates("t")
    df = df[(df.v >= PLAUS_LO) & (df.v <= PLAUS_HI)]
    if not len(df):
        return np.array([])
    med = df.v.groupby((df.t // BIN_S).astype(int)).median()
    s0 = int(np.ceil((df.t.iloc[0] + EQUIL_MIN * 60) / BIN_S))
    keep = med[med.index >= s0]
    if not len(keep):
        return np.array([])
    y = np.full(int(med.index.max()) - s0 + 1, np.nan)
    y[keep.index.to_numpy() - s0] = keep.to_numpy()
    return y


ev_cases = sorted(set(ev.caseid.astype(int)))
last_cache, max1 = {}, {}
not_cached = []
for c in ev_cases:
    y = cached_settled(c)
    if y is None:
        not_cached.append(c)
        continue
    last_cache[c] = int(np.where(~np.isnan(y))[0].max()) if np.any(~np.isnan(y)) else np.nan
    max1[c] = y
last_man = {c: int(man.loc[c, "settled_minutes"]) - 1 for c in ev_cases
            if "settled_minutes" in man.columns and pd.notna(man.loc[c, "settled_minutes"])}

if missing and not_cached:
    raise SystemExit(f"STOP: last observed minute unrecoverable locally for {len(not_cached)} cases and {missing}.")
mismatch = [c for c in ev_cases if c in last_man and c in last_cache and last_man[c] != last_cache[c]]
if mismatch:
    raise SystemExit(f"STOP: manifest and cache disagree on last observed minute for {len(mismatch)} cases "
                     f"(e.g. {mismatch[:5]}); not resolving silently.")
LAST = {c: last_man.get(c, last_cache.get(c, np.nan)) for c in ev_cases}
if any(pd.isna(v) for v in LAST.values()):
    raise SystemExit("STOP: last observed settled minute missing for some event cases.")

ev["last_observed_settled_minute"] = ev.caseid.map(LAST)
if (ev.end_min > ev.last_observed_settled_minute).any():
    raise SystemExit("STOP: some events end after the last observed minute — clocks inconsistent.")
ev["distance_to_last_observed_minute"] = ev.last_observed_settled_minute - ev.end_min
ev["no_post_window"] = ev.post_level_C.isna()
ev["near_recording_end"] = ev.distance_to_last_observed_minute <= NEAR_END_MIN
ev["interior_supported"] = ev.supported.astype(bool) & ev.post_level_C.notna()
ev["terminal_associated"] = ev.no_post_window | ev.near_recording_end
ev["group_exclusive"] = np.select([ev.no_post_window, ev.near_recording_end, ev.interior_supported],
                                  ["A_no_post_window", "B_near_recording_end", "C_interior_supported"],
                                  "D_other_intermediate")
ev["event_end_fraction"] = np.where(ev.last_observed_settled_minute > 0,
                                    ev.end_min / ev.last_observed_settled_minute, np.nan)
ev["abs_net"] = ev.net_change_C.abs()
ev["abs_peak"] = ev.peak_excursion_C.abs()
ev["direction_net"] = np.select([ev.net_change_C < 0, ev.net_change_C > 0], ["down", "up"], "undefined")
ev["direction_peak"] = np.select([ev.peak_excursion_C < 0, ev.peak_excursion_C > 0], ["down", "up"], "undefined")


def max_single_minute(row):
    y = max1.get(int(row.caseid))
    if y is None:
        return np.nan
    best = np.nan
    for t in range(int(row.start_min), int(row.end_min) + 1):
        if 1 <= t < len(y) and not np.isnan(y[t]) and not np.isnan(y[t - 1]):
            d = abs(y[t] - y[t - 1])
            best = d if np.isnan(best) else max(best, d)
    return best


ev["max_single_minute_jump_C"] = ev.apply(max_single_minute, axis=1)


# ============================================================================
# helpers
# ============================================================================
def qtxt(s):
    s = pd.Series(s).dropna()
    return {f"q{int(q * 100)}": (round(float(s.quantile(q)), 3) if len(s) else None) for q in QS}


def group_stats(e, n_cases_split, label):
    zf = e.z_event.dropna()
    return dict(group=label, events=int(len(e)), cases=int(e.caseid.nunique()),
                pct_of_cases=round(100 * e.caseid.nunique() / n_cases_split, 2),
                patterns=e.pattern.value_counts().to_dict(),
                abs_net=qtxt(e.abs_net), abs_peak=qtxt(e.abs_peak), duration_min=qtxt(e.duration_min),
                direction_net=e.direction_net.value_counts().to_dict(),
                direction_peak=e.direction_peak.value_counts().to_dict(),
                distance_to_end=qtxt(e.distance_to_last_observed_minute),
                MODEL_BASED_event_z4_share=(round(float((zf.abs() > 4).mean()), 3) if len(zf) else None),
                MODEL_BASED_n_with_z=int(len(zf)))


def bin_counts(series, bins, total):
    out = {}
    for lo, hi, lab in bins:
        n = int(((series >= lo) & (series <= hi)).sum()) if bins is DIST_BINS else int(((series >= lo) & (series < hi)).sum())
        out[lab] = dict(n=n, pct=round(100 * n / total, 2) if total else None)
    return out


SPLITS = ["dev_train", "dev_val"]
R = {s: {} for s in SPLITS}
rows_summary = []
for s in SPLITS:
    e = ev[ev.set == s]
    nE, nC = len(e), N_CASES[s]
    # ---- Task 1 ----
    dist = {}
    for lo, hi, lab in DIST_BINS:
        m = (e.distance_to_last_observed_minute >= lo) & (e.distance_to_last_observed_minute <= hi)
        dist[lab] = dict(events=int(m.sum()), pct_of_events=round(100 * m.sum() / nE, 2),
                         cases=int(e[m].caseid.nunique()), pct_of_cases=round(100 * e[m].caseid.nunique() / nC, 2))
    R[s]["task1_distance_bins"] = dist
    R[s]["task1_counts"] = dict(no_post_window=int(e.no_post_window.sum()),
                                within_5_min_of_end=int(e.near_recording_end.sum()),
                                both=int((e.no_post_window & e.near_recording_end).sum()),
                                no_post_window_but_more_than_5_min_from_end=int((e.no_post_window & ~e.near_recording_end).sum()),
                                events=nE, cases_in_split=nC)
    # ---- Task 2 (overlapping definitions as specified, plus exclusive version) ----
    R[s]["task2_groups_as_defined"] = [group_stats(e[e.no_post_window], nC, "A_no_post_window"),
                                       group_stats(e[e.near_recording_end], nC, "B_near_recording_end"),
                                       group_stats(e[e.interior_supported], nC, "C_interior_supported"),
                                       group_stats(e[~(e.no_post_window | e.near_recording_end | e.interior_supported)], nC,
                                                   "D_other_intermediate")]
    R[s]["task2_groups_exclusive"] = [group_stats(e[e.group_exclusive == g], nC, g) for g in sorted(e.group_exclusive.unique())]
    # ---- Task 4 ----
    mags = []
    for col in ("abs_net", "abs_peak"):
        for L in MAG_LEVELS:
            m = e[e[col] >= L]
            k = max(len(m), 1)
            mags.append(dict(measure=col, threshold_C=L, events=int(len(m)), cases=int(m.caseid.nunique()),
                             frac_no_post_window=round(m.no_post_window.sum() / k, 3),
                             frac_within_5_min_of_end=round(m.near_recording_end.sum() / k, 3),
                             frac_interior_supported=round(m.interior_supported.sum() / k, 3),
                             frac_persistent_shift=round((m.pattern == "persistent_shift").sum() / k, 3),
                             frac_isolated_returning=round((m.pattern == "isolated_returning").sum() / k, 3),
                             frac_undetermined=round((m.pattern == "undetermined").sum() / k, 3),
                             direction_net=m.direction_net.value_counts().to_dict(),
                             direction_peak=m.direction_peak.value_counts().to_dict(),
                             distance_to_end_bins={k: v["n"] for k, v in bin_counts(m.distance_to_last_observed_minute, DIST_BINS, len(m)).items()},
                             timing_bins={k: v["n"] for k, v in bin_counts(m.event_end_fraction, FRAC_BINS, len(m)).items()}))
    R[s]["task4_large"] = mags
    # ---- Task 5 ----
    pdat = e[e.post_level_C.notna()]
    t5 = {}
    for p in ["persistent_shift", "isolated_returning", "partial_return", "undetermined"]:
        m = pdat[pdat.pattern == p]
        t5[p] = dict(n=int(len(m)), pct_of_post_data_events=round(100 * len(m) / max(len(pdat), 1), 2),
                     abs_net=qtxt(m.abs_net), abs_peak=qtxt(m.abs_peak), duration_min=qtxt(m.duration_min),
                     timing=bin_counts(m.event_end_fraction, FRAC_BINS, len(m)),
                     direction_net=m.direction_net.value_counts().to_dict(),
                     within_5_min_of_end=int(m.near_recording_end.sum()))
    R[s]["task5_post_data_events"] = dict(n=int(len(pdat)), by_pattern=t5)
    # ---- Task 6 ----
    t6 = {}
    for g, m in [("persistent_shift", e[e.pattern == "persistent_shift"]), ("isolated_returning", e[e.pattern == "isolated_returning"]),
                 ("partial_return", e[e.pattern == "partial_return"]), ("undetermined", e[e.pattern == "undetermined"]),
                 ("no_post_window", e[e.no_post_window])]:
        t6[g] = dict(n=int(len(m)), bins=bin_counts(m.event_end_fraction, FRAC_BINS, len(m)))
        for lab, d in t6[g]["bins"].items():
            rows_summary.append(dict(set=s, table="timing", group=g, bin=lab, n=d["n"], pct=d["pct"]))
    R[s]["task6_timing"] = t6
    # ---- Task 7 geometry ----
    R[s]["task7"] = dict(events_per_case=round(nE / nC, 3), pct_cases_with_event=round(100 * e.caseid.nunique() / nC, 2),
                         pct_no_post_window=round(100 * e.no_post_window.mean(), 2),
                         pct_within_5_min_of_end=round(100 * e.near_recording_end.mean(), 2),
                         pct_terminal_associated=round(100 * e.terminal_associated.mean(), 2),
                         patterns_pct={k: round(100 * v, 2) for k, v in e.pattern.value_counts(normalize=True).items()},
                         pct_abs_peak_ge5=round(100 * (e.abs_peak >= 5).mean(), 2),
                         pct_abs_peak_ge10=round(100 * (e.abs_peak >= 10).mean(), 2),
                         abs_net=qtxt(e.abs_net), abs_peak=qtxt(e.abs_peak), duration_min=qtxt(e.duration_min),
                         direction_peak_pct={k: round(100 * v, 2) for k, v in e.direction_peak.value_counts(normalize=True).items()},
                         largest_single_minute_jump_C=(round(float(e.max_single_minute_jump_C.max()), 3)
                                                       if e.max_single_minute_jump_C.notna().any() else None))
    for k, v in R[s]["task7"].items():
        rows_summary.append(dict(set=s, table="geometry", group=k, bin="", n=None, pct=json.dumps(v) if isinstance(v, dict) else v))

# ---- Task 3 extreme tables (both splits pooled, split labelled) ----
cols = ["caseid", "set", "start_min", "end_min", "duration_min", "pre_level_C", "post_level_C", "net_change_C",
        "peak_excursion_C", "max_single_minute_jump_C", "distance_to_last_observed_minute", "no_post_window",
        "supported", "pattern", "terminal_associated"]
TA = ev[ev.net_change_C.notna()].sort_values("abs_net", ascending=False).head(20)[cols]
TB = ev[ev.peak_excursion_C.notna()].sort_values("abs_peak", ascending=False).head(20)[cols]
TA.to_csv(os.path.join(OUT, "extreme_event_table_net_change.csv"), index=False)
TB.to_csv(os.path.join(OUT, "extreme_event_table_peak_excursion.csv"), index=False)
T3 = {name: dict(terminal_associated=int(t.terminal_associated.sum()), within_5_min_of_end=int((t.distance_to_last_observed_minute <= 5).sum()),
                 missing_post_window=int(t.no_post_window.sum())) for name, t in (("table_A_net", TA), ("table_B_peak", TB))}
LARGEST_1MIN = (round(float(ev.max_single_minute_jump_C.max()), 3) if ev.max_single_minute_jump_C.notna().any() else None)

# ============================================================================
# TASK 8 — where robustness belongs (rule disclosed above)
# ============================================================================
verdict = {}
for s in SPLITS:
    e = ev[ev.set == s]
    interior_post = e[e.post_level_C.notna() & ~e.near_recording_end]
    n_ip = max(len(interior_post), 1)
    big = e[e.abs_peak >= 5]
    verdict[s] = dict(
        n_interior_post_data=int(len(interior_post)),
        share_persistent_interior=round((interior_post.pattern == "persistent_shift").sum() / n_ip, 3),
        share_returning_interior=round((interior_post.pattern == "isolated_returning").sum() / n_ip, 3),
        share_terminal_all=round(e.terminal_associated.mean(), 3),
        share_terminal_large=round(big.terminal_associated.mean(), 3) if len(big) else np.nan)
    ip_pers = interior_post[interior_post.pattern == "persistent_shift"]
    k_ = max(len(ip_pers), 1)
    verdict[s]["DESCRIPTIVE_interior_persistent_in_last_10pct_of_recording"] = round((ip_pers.event_end_fraction > 0.9).sum() / k_, 3)
    verdict[s]["DESCRIPTIVE_interior_persistent_ending_6_30_min_before_end"] = round(
        ip_pers.distance_to_last_observed_minute.between(6, 30).sum() / k_, 3)
    verdict[s]["DESCRIPTIVE_interior_persistent_abs_net_ge5_share"] = round((ip_pers.abs_net >= 5).sum() / k_, 3)
    v = verdict[s]
    v["level_credible"] = bool(v["share_persistent_interior"] >= CREDIBLE_SHARE)
    v["observation_credible"] = bool(v["share_returning_interior"] >= CREDIBLE_SHARE)
    v["edge_required"] = bool((v["share_terminal_all"] > EDGE_MAJORITY) or (np.isfinite(v["share_terminal_large"])
                                                                          and v["share_terminal_large"] > EDGE_MAJORITY))
consistent = all(verdict["dev_train"][k] == verdict["dev_val"][k] for k in ("level_credible", "observation_credible", "edge_required"))
vt = verdict["dev_train"]
if not consistent:
    LOCATION = "INCONCLUSIVE"
elif vt["level_credible"] and vt["observation_credible"]:
    LOCATION = "COMBINATION"
elif vt["level_credible"]:
    LOCATION = "LEVEL"
elif vt["observation_credible"]:
    LOCATION = "OBSERVATION"
elif vt["edge_required"]:
    LOCATION = "EDGE"
else:
    LOCATION = "INCONCLUSIVE"
EDGE_ALSO = bool(vt["edge_required"]) and LOCATION in ("LEVEL", "OBSERVATION")

# ============================================================================
# OUTPUTS + protection re-check
# ============================================================================
ev.to_csv(os.path.join(OUT, "event_forensics_events_annotated.csv"), index=False)
pd.DataFrame(rows_summary).to_csv(os.path.join(OUT, "event_timing_summary.csv"), index=False)
summ = []
for s in SPLITS:
    for k, d in R[s]["task1_distance_bins"].items():
        summ.append(dict(set=s, section="task1_distance_to_end", item=k, **d))
    for k, v in R[s]["task1_counts"].items():
        summ.append(dict(set=s, section="task1_counts", item=k, events=v))
    for g in R[s]["task2_groups_as_defined"]:
        summ.append(dict(set=s, section="task2_group_as_defined", item=g["group"], events=g["events"], cases=g["cases"],
                         pct_of_cases=g["pct_of_cases"]))
    for m in R[s]["task4_large"]:
        summ.append(dict(set=s, section=f"task4_{m['measure']}_ge{m['threshold_C']}", item="events", events=m["events"],
                         cases=m["cases"], **{k: v for k, v in m.items() if k.startswith("frac_")}))
    for k, v in verdict[s].items():
        summ.append(dict(set=s, section="task8_evidence", item=k, value=v))
pd.DataFrame(summ).to_csv(os.path.join(OUT, "event_forensics_summary.csv"), index=False)
json.dump(dict(results=R, extreme_tables=T3, largest_single_minute_jump_C=LARGEST_1MIN, task8=verdict,
               consistent_train_val=consistent, ROBUSTNESS_LOCATION=LOCATION, edge_handling_also_required=EDGE_ALSO,
               not_cached_cases=not_cached, rule=dict(credible_share=CREDIBLE_SHARE, edge_majority=EDGE_MAJORITY),
               protection=protect), open(os.path.join(OUT, "event_forensics_results.json"), "w"), indent=2, default=str)

HASH_AFTER = {**hash_tree(CODE4_DIR), **hash_tree(FREEZE_DIR)}
protect["protected_files_unchanged"] = HASH_BEFORE == HASH_AFTER
PROTECTED = all(protect.values())
FORENSICS_OK = len(ev) > 0 and not mismatch


def line(s, k):
    return R[s]["task7"][k]


tr, va = verdict["dev_train"], verdict["dev_val"]
md = f"""# Event forensics report (development only)

Inputs: frozen Code 3B event table from the adequacy study; last observed settled minute from
code4_cohort_manifest.csv (settled_minutes - 1), cross-checked against cached tracks (0 mismatches;
{len(not_cached)} event cases not in local cache). No network access. Final holdout never loaded.

Denominators: "% of events" = events in that split; "% of cases" = all cases in that split
(dev-train {N_CASES['dev_train']}, dev-val {N_CASES['dev_val']}).

## Task 1 — distance from event end to last observed settled minute

| bin (min) | dev-train events (% events, % cases) | dev-val events (% events, % cases) |
|---|---|---|
""" + "\n".join(f"| {lab} | {R['dev_train']['task1_distance_bins'][lab]['events']} ({R['dev_train']['task1_distance_bins'][lab]['pct_of_events']}%, {R['dev_train']['task1_distance_bins'][lab]['pct_of_cases']}%) | {R['dev_val']['task1_distance_bins'][lab]['events']} ({R['dev_val']['task1_distance_bins'][lab]['pct_of_events']}%, {R['dev_val']['task1_distance_bins'][lab]['pct_of_cases']}%) |" for _, _, lab in DIST_BINS) + f"""

No post-window / within 5 min of end / both / no post-window but > 5 min from end:
dev-train {R['dev_train']['task1_counts']['no_post_window']} / {R['dev_train']['task1_counts']['within_5_min_of_end']} / {R['dev_train']['task1_counts']['both']} / {R['dev_train']['task1_counts']['no_post_window_but_more_than_5_min_from_end']};
dev-val {R['dev_val']['task1_counts']['no_post_window']} / {R['dev_val']['task1_counts']['within_5_min_of_end']} / {R['dev_val']['task1_counts']['both']} / {R['dev_val']['task1_counts']['no_post_window_but_more_than_5_min_from_end']}.

## Task 3 — extremes
Table A (top 20 by |net|): terminal-associated {T3['table_A_net']['terminal_associated']}, within 5 min of end {T3['table_A_net']['within_5_min_of_end']}, missing post-window {T3['table_A_net']['missing_post_window']}.
Table B (top 20 by |peak|): terminal-associated {T3['table_B_peak']['terminal_associated']}, within 5 min of end {T3['table_B_peak']['within_5_min_of_end']}, missing post-window {T3['table_B_peak']['missing_post_window']}.
Largest single-minute jump (consecutive observed minutes, cached tracks): {LARGEST_1MIN} C.

## Task 7 — train / validation geometry

| measure | dev-train | dev-val |
|---|---|---|
""" + "\n".join(f"| {k} | {line('dev_train', k)} | {line('dev_val', k)} |" for k in R["dev_train"]["task7"]) + f"""

## Task 8 — where robustness belongs

Evidence (interior post-data events = post-window present AND > {NEAR_END_MIN} min from recording end):

| evidence | dev-train | dev-val |
|---|---|---|
| interior post-data events | {tr['n_interior_post_data']} | {va['n_interior_post_data']} |
| share persistent_shift (interior) | {tr['share_persistent_interior']} | {va['share_persistent_interior']} |
| share isolated_returning (interior) | {tr['share_returning_interior']} | {va['share_returning_interior']} |
| share terminal-associated (all events) | {tr['share_terminal_all']} | {va['share_terminal_all']} |
| share terminal-associated (abs peak >= 5 C) | {tr['share_terminal_large']} | {va['share_terminal_large']} |
| level credible / observation credible / edge required | {tr['level_credible']} / {tr['observation_credible']} / {tr['edge_required']} | {va['level_credible']} / {va['observation_credible']} / {va['edge_required']} |

Rule (disclosed as NOT blind: written after aggregate pattern counts were seen): a pattern is credible if it
forms >= {CREDIBLE_SHARE:.0%} of interior post-data events in BOTH splits; edge handling is required if > {EDGE_MAJORITY:.0%} of all
events or of large (|peak| >= 5 C) events are terminal-associated in BOTH splits; any train/val disagreement -> INCONCLUSIVE.

For every conclusion:
- LEVEL — OBSERVED: interior persistent_shift share {tr['share_persistent_interior']} / {va['share_persistent_interior']}.
  Of those interior persistent shifts: in last 10% of recording {tr['DESCRIPTIVE_interior_persistent_in_last_10pct_of_recording']} / {va['DESCRIPTIVE_interior_persistent_in_last_10pct_of_recording']};
  ending 6-30 min before recording end {tr['DESCRIPTIVE_interior_persistent_ending_6_30_min_before_end']} / {va['DESCRIPTIVE_interior_persistent_ending_6_30_min_before_end']};
  |net| >= 5 C {tr['DESCRIPTIVE_interior_persistent_abs_net_ge5_share']} / {va['DESCRIPTIVE_interior_persistent_abs_net_ge5_share']}.
  INFERENCE: sustained post-event level differences exist away from the immediate recording edge. LIMITATION: the
  user-defined edge window is <= 5 min, so a recording-end change starting 6-30 min before the end is counted as
  interior and can appear as a "persistent shift" (shown on synthetic data); the three descriptive shares above
  indicate how much of the LEVEL evidence may be edge-adjacent. "Persistent at +10 min" also cannot distinguish a
  physiological change from probe repositioning; no reference signal is used here.
- OBSERVATION — OBSERVED: interior isolated_returning share {tr['share_returning_interior']} / {va['share_returning_interior']}.
  INFERENCE: transient excursions that return are observation-like. LIMITATION: a brief genuine change would look the same.
- EDGE — OBSERVED: terminal-associated share {tr['share_terminal_all']} / {va['share_terminal_all']} (large events {tr['share_terminal_large']} / {va['share_terminal_large']}).
  INFERENCE: changes at the end of the BT recording cannot be interpreted as state changes without post-event data.
  LIMITATION: recording end is not surgery end; the cause of terminal changes is not established here.
- COMBINATION — requires LEVEL and OBSERVATION both credible; edge handling separately if required.
- INCONCLUSIVE — chosen only if train and validation disagree or no component is credible.
- MODEL-BASED values (z_event) are reported in the JSON but were NOT used for this decision; the Gaussian q_hat is degenerate.

Edge handling additionally required alongside the selected location: {vt['edge_required']}.

FINAL_HOLDOUT_PROTECTED: {"PASS" if PROTECTED else "FAIL"}
EVENT_FORENSICS: {"PASS" if FORENSICS_OK else "FAIL"}
ROBUSTNESS_LOCATION: {LOCATION}
"""
open(os.path.join(OUT, "event_forensics_report.md"), "w").write(md)

print("=" * 78)
print("EVENT FORENSICS (development only)")
print("=" * 78)
for s in SPLITS:
    c1 = R[s]["task1_counts"]
    print(f"\n[{s}] events {c1['events']} | cases in split {c1['cases_in_split']}")
    print("  distance to last observed minute: " + ", ".join(
        f"{k} {v['events']} ({v['pct_of_events']}% ev, {v['pct_of_cases']}% cases)" for k, v in R[s]["task1_distance_bins"].items()))
    print(f"  no post-window {c1['no_post_window']} | within 5 min {c1['within_5_min_of_end']} | both {c1['both']} | "
          f"no post-window but > 5 min from end {c1['no_post_window_but_more_than_5_min_from_end']}")
    for g in R[s]["task2_groups_as_defined"]:
        print(f"  group {g['group']}: {g['events']} events / {g['cases']} cases; patterns {g['patterns']}; |net| {g['abs_net']}; "
              f"|peak| {g['abs_peak']}; peak direction {g['direction_peak']}")
    for m in R[s]["task4_large"]:
        print(f"  {m['measure']} >= {m['threshold_C']} C: {m['events']} ev | no-post {m['frac_no_post_window']} | <=5min {m['frac_within_5_min_of_end']} "
              f"| interior {m['frac_interior_supported']} | persistent {m['frac_persistent_shift']} | returning {m['frac_isolated_returning']} "
              f"| undetermined {m['frac_undetermined']} | peak dir {m['direction_peak']}")
    t5 = R[s]["task5_post_data_events"]
    print(f"  post-data events {t5['n']}: " + ", ".join(f"{p} {d['n']} ({d['pct_of_post_data_events']}%)" for p, d in t5["by_pattern"].items()))
    for g, d in R[s]["task6_timing"].items():
        print(f"  timing {g} (n={d['n']}): " + ", ".join(f"{k} {v['pct']}%" for k, v in d["bins"].items()))
    for m in R[s]["task4_large"]:
        print(f"  {m['measure']} >= {m['threshold_C']} C by distance-to-end {m['distance_to_end_bins']} | by position {m['timing_bins']}")
    print(f"  Task 8 evidence: {verdict[s]}")
print(f"\nTask 3: Table A {T3['table_A_net']} | Table B {T3['table_B_peak']} | largest single-minute jump {LARGEST_1MIN} C")
print(f"Train/val consistent on all Task 8 components: {consistent}; edge handling also required: {vt['edge_required']}")
print(f"Protection: {protect}")
print(f"\nFINAL_HOLDOUT_PROTECTED: {'PASS' if PROTECTED else 'FAIL'}")
print(f"EVENT_FORENSICS: {'PASS' if FORENSICS_OK else 'FAIL'}")
print(f"ROBUSTNESS_LOCATION: {LOCATION}")
