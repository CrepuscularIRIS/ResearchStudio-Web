#!/usr/bin/env python3
"""spec_check.py <spec_dir> <repo> <forbidden_json> <impl_path> [--block B1] [--plan evidence_plan.json]
The deterministic gate on block specs (moved out of the Brain on 2026-09-07; same rules as the former Phase 6 spec_check):
machine-readable fields, real files (a created file says function: NEW), no SMOKE in run_cmd, forbidden patterns, arms ↔ verdict_rule,
gates in the ASI form, open implementability holes addressed. With --plan it also enforces PLAN ⊆ SPEC: the Worker drafts engineering,
never science — keep_if_all numbers come from the plan's keep_rule, kill_condition is one of the plan's, forbids cover frozen_untouched,
the negative-control arm names the plan's negative control. Prints __SPEC_OK / __SPEC_BAD <findings>.
"""
import argparse, glob, json, os, re, sys


def norm(t) -> str: return re.sub(r"\s+", " ", str(t or "")).strip().lower()


def numbers(t) -> set:
    return {float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", str(t or ""))}


def check_binding(n: str, d: dict, plan: dict, bad: list, warn: list) -> None:
    pb = next((b for b in plan.get("blocks") or [] if isinstance(b, dict) and b.get("block_id") == d.get("block_id")), None)
    if not pb:
        warn.append(n + " plan has no block " + str(d.get("block_id")) + " — plan binding not checked"); return
    kr = pb.get("keep_rule")
    if kr:
        allowed = numbers(kr) | numbers(pb.get("kill_condition")) | {0.0, 1.0}
        for k in ("min_effect", "seed_sd", "gpu_h"):
            if isinstance(pb.get(k), (int, float)): allowed.add(float(pb[k]))
        if isinstance(pb.get("seeds"), (int, float)): allowed.add(float(pb["seeds"]))
        for r in (d.get("verdict_rule") or {}).get("keep_if_all") or []:
            v = r.get("value") if isinstance(r, dict) else None
            if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) not in allowed:
                bad.append(n + " keep_if_all value %s is not a number of the plan's keep_rule (%s) — a threshold the Worker invented" % (v, str(kr)[:80]))
    else:
        warn.append(n + " plan block has no keep_rule text — numeric binding not checked")
    kc = norm(d.get("kill_condition"))
    plan_kcs = [norm(x) for x in (plan.get("kill_conditions") or []) if x] + ([norm(pb.get("kill_condition"))] if pb.get("kill_condition") else [])
    if kc and plan_kcs and not any(kc in p or p in kc for p in plan_kcs):
        bad.append(n + " kill_condition is not one of the plan's kill_conditions (verbatim or contained)")
    fu = [norm(x) for x in plan.get("frozen_untouched") or [] if x]
    fb = norm(" ".join(str(x) for x in d.get("forbids") or []))
    miss = [x for x in fu if x not in fb]
    if miss: bad.append(n + " forbids does not cover plan.frozen_untouched: " + ", ".join(miss[:3]))
    nc = norm(pb.get("negative_control"))
    arm = next((a for a in d.get("arms") or [] if isinstance(a, dict) and str(a.get("name")) == str(d.get("negctl_arm"))), {})
    at = norm(json.dumps(arm, ensure_ascii=False))
    stop = {"with", "that", "this", "from", "into", "than", "then", "when", "which", "arm", "control", "negative", "the", "and", "for", "must", "should"}
    toks = [t for t in re.findall(r"[a-z][a-z0-9_]{3,}", nc) if t not in stop]
    if toks and at and not any(t in at for t in toks): warn.append(n + " negctl_arm shares no token with the plan's negative_control text")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec_dir"); ap.add_argument("repo"); ap.add_argument("forbidden"); ap.add_argument("impl_path")
    ap.add_argument("--block", default=""); ap.add_argument("--plan", default="")
    a = ap.parse_args()
    spec_dir, repo, forbidden, impl_path = a.spec_dir, a.repo, json.loads(a.forbidden), a.impl_path
    bad, warn = [], []
    files = sorted(glob.glob(os.path.join(spec_dir, a.block + ".json" if a.block else "B*.json")))
    if not files: bad.append("no spec/" + (a.block + ".json" if a.block else "B*.json"))
    plan = None
    if a.plan:
        try: plan = json.load(open(a.plan))
        except Exception as ex: warn.append("plan unreadable, binding not checked: " + str(ex)[:60])
    need = ["block_id", "goal", "method", "changes", "run_cmd", "smoke_cmd", "arms", "baselines", "negctl_arm", "verdict_rule", "kill_condition", "decision_points", "open_holes", "forbids", "outputs", "gates", "gpu_h"]
    gk = {"file_exists", "no_nan_inf", "forbidden_import", "forbidden_pattern", "key_present"}
    ops = {"gt", "gte", "lt", "lte", "eq"}
    open_holes = set()
    try:
        impl = json.load(open(impl_path))
        for u in impl.get("underspecified_points") or []:
            if str(u.get("severity")) == "open": open_holes.add(str(u.get("step_id")) + "|" + str(u.get("hole"))[:60])
    except Exception:
        pass
    covered = set()
    for f in files:
        try: d = json.load(open(f))
        except Exception as ex: bad.append(os.path.basename(f) + " unreadable: " + str(ex)[:80]); continue
        n = os.path.basename(f)
        if d.get("blocked"): warn.append(n + " blocked: " + str(d["blocked"])[:100]); continue
        for k in need:
            if k not in d or d[k] in ("", {}, None): bad.append(n + " missing " + k)
        for ch in d.get("changes") or []:
            fp = str(ch.get("file") or "")
            creates = bool(ch.get("new")) or bool(re.match(r"^\s*NEW\b", str(ch.get("function") or ""), re.I))
            if fp and creates:
                parent = os.path.dirname(os.path.join(repo, fp))
                if not os.path.isdir(parent) and not os.path.isdir(os.path.dirname(fp)): warn.append(n + " new file in a directory that does not exist yet: " + fp)
            elif fp and not os.path.exists(os.path.join(repo, fp)) and not os.path.exists(fp): bad.append(n + " change file not found: " + fp + " (a file the block creates must say function: NEW)")
        for key in ("run_cmd", "smoke_cmd"):
            cmd = str(d.get(key) or "")
            if re.search(r"(^|\s)SMOKE=", cmd): bad.append(n + " " + key + " sets SMOKE itself")
            tok = [t for t in re.split(r"\s+", cmd) if t and not t.startswith("-")]
            scripts = [t for t in tok if t.endswith(".py") or t.endswith(".sh")]
            for sc in scripts[:1]:
                if not os.path.exists(os.path.join(repo, sc)) and not os.path.exists(sc): bad.append(n + " " + key + " script not found: " + sc)
        blob = json.dumps({"run_cmd": d.get("run_cmd"), "smoke_cmd": d.get("smoke_cmd"), "arms": d.get("arms")}).lower()
        for pat in forbidden:
            if pat.lower() in blob: bad.append(n + " mentions forbidden pattern in run_cmd/smoke_cmd/arms: " + pat)
        names = {str(x.get("name")) for x in (d.get("arms") or []) if isinstance(x, dict)}
        vr = d.get("verdict_rule") or {}
        roles = vr.get("arms") or {}
        for role in ("candidate", "control", "negative_control"):
            if str(roles.get(role)) not in names: bad.append(n + " verdict_rule.arms." + role + " is not an arm name")
        if str(d.get("negctl_arm")) not in names: bad.append(n + " negctl_arm is not an arm name")
        kia = vr.get("keep_if_all") or []
        if not kia: bad.append(n + " verdict_rule.keep_if_all empty")
        for r in kia:
            if not isinstance(r, dict) or not r.get("key") or r.get("op") not in ops or not isinstance(r.get("value"), (int, float, bool)) or isinstance(r.get("value"), str):
                bad.append(n + " keep_if_all rule not machine-readable: " + json.dumps(r)[:80])
        if not isinstance(vr.get("seeds"), list) or not vr.get("seeds"): bad.append(n + " verdict_rule.seeds missing")
        if not isinstance(d.get("decision_points"), list): bad.append(n + " decision_points not a list")
        for dp in d.get("decision_points") or []:
            if not isinstance(dp, dict) or dp.get("default") in (None, ""): bad.append(n + " decision_point without default")
        gates = [g for g in (d.get("gates") or []) if isinstance(g, dict)]
        for g in gates:
            if g.get("check") not in gk or g.get("severity") not in ("hard", "soft"): bad.append(n + " gate not machine-readable: " + json.dumps(g)[:80])
        gated = {str((g.get("config") or {}).get("file")) for g in gates if g.get("check") == "file_exists"}
        for o in d.get("outputs") or []:
            if isinstance(o, dict) and str(o.get("file")) not in gated: warn.append(n + " output without a file_exists gate: " + str(o.get("file")))
        if d.get("forbids") and not any(g.get("check") in ("forbidden_pattern", "forbidden_import") for g in gates): bad.append(n + " forbids listed but no forbidden_pattern/forbidden_import gate")
        for h in d.get("open_holes") or []:
            if isinstance(h, dict):
                covered.add(str(h.get("step_id")) + "|" + str(h.get("hole"))[:60])
                if not h.get("resolution") and not h.get("blocked"): bad.append(n + " open hole neither resolved nor blocked: " + str(h.get("step_id")))
        if plan: check_binding(n, d, plan, bad, warn)
    if open_holes and files and not a.block:
        miss = [h for h in open_holes if not any(h.split("|")[0] == c.split("|")[0] for c in covered)]
        if miss: bad.append("implementability open holes not addressed in any spec: " + ", ".join(m.split("|")[0] for m in miss))
    print(("__SPEC_BAD " if bad else "__SPEC_OK ") + " | ".join(bad + ["warn: " + w for w in warn]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
