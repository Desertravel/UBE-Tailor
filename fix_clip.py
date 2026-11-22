# UBE Tailor - Copyright (C) 2026 Desertravel. Licensed under the GNU GPL v3 or later (see LICENSE).
"""Fix clipping: make a converted piece stay outside the UBE body at the presets the user picks.

A BodySlide preset sets every slider to some value (negative values and inverted sliders included); the outfit's
point i then sits at  rest_i + sum_s value_s * data_s,i  and the body at its own sum. No rule per slider can keep
the outfit outside at every preset (25 of 27 presets on the test list use negative values), so this solves it
for the presets that matter: for every outfit point that comes closer than GAP to the body (or goes inside) at
any of them, it finds the smallest change of that point's slider data, along the body normal, that keeps it at
least GAP outside at ALL of them at once (a small least-norm problem per point, with the presets as constraints).
The change is smoothed over neighbouring points (the motion is smoothed, not the shape, so details stay), the
piece is measured again, and this repeats; a last pass solves without smoothing, so smoothing leaves nothing new.

Do no harm: every shape is graded at every chosen preset before and after. A shape that got worse at any of them
(more points inside, or deeper) keeps its original data. Only the project's slider data (.osd) changes - the rest
shape stays as converted, the original is kept as .osd.orig (a new fix always starts from it, a new conversion
deletes it). BodySlide must build the piece again.

Use all the presets the player uses: fixing for a few makes the others worse (the data is changed for those only).

  python fix_clip.py <set name> <preset> [<preset> ...]
"""
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np

import env
import make_projects as mp
import tailor_core as tc
import ube_field
from nifly_env import NifFile, body_delta, body_points, knn, skin_delta

try:
    from scipy.spatial import cKDTree as _KDTree
except ImportError:                 # plain numpy fallback (slow)
    _KDTree = None

GAP = 0.15           # wanted distance between outfit and body at every chosen preset
NEAR = 3.0           # only outfit points this close to the body at rest are changed (skirts, capes move freely)
ROUNDS = 2           # measure - solve - smooth rounds,
FINAL = 3            # then unsmoothed ones (smoothing moves points the solve did not ask to move)
MAX_STEP = 4.0       # largest change of one slider's data at one point (units at 100 %), against wild results
INSIDE = -0.05       # a point deeper than this is "inside" (same as the fit check, tailor_core.qa)
WORSE_DEPTH = 0.02   # a shape whose deepest point sinks more than this at some preset is "worse"


# ---------------------------------------------------------------- body surfaces and distances
_ADJ = {}


def surface(refs, pv, w, heel):
    """UBE body at a preset (tailor_core.body_surface) plus a search tree of its points."""
    SV, SF, FN = tc.body_surface(refs, pv, w, heel)
    return SV, SF, FN, (_KDTree(SV) if _KDTree is not None else None)


def _project(P, S):
    SV, SF, _FN, tree = S
    key = (len(SV), len(SF))
    if key not in _ADJ:                  # every surface of one process has the same triangles
        _ADJ[key] = ube_field.tri_adjacency(len(SV), SF)
    if tree is None:
        idx = knn(SV, P, 4)[1]
    else:
        idx = tree.query(P, k=4)[1]                     # one thread: starting threads costs more here
    return ube_field.project(P, SV, SF, adj=_ADJ[key], idx=idx)


def _depth(P, S):
    """(signed distance, body normal there) of points to a body surface; nan where the side is unclear."""
    SV, SF, FN, _t = S
    tri, bary, dist = _project(P, S)
    q = ube_field.interp(SV, SF, tri, bary)
    n = FN[tri]
    dot = ((P - q) * n).sum(1)
    sd = np.sign(dot) * dist
    ok = (sd > -mp.CLIP_BAND) & ((np.abs(dot) >= 0.6 * dist) | (dist < 0.02))
    return np.where(ok, sd, np.nan), n


def grade_of(st):
    """Fit grade of one preset's numbers, exactly like the fit check."""
    return tc.grade(st["verts"], max(st["in0"], st["in1"]), st["worst"])


# ---------------------------------------------------------------- the project
class Project:
    """A converted piece's BodySlide project: outfit shapes, their slider data (dense, per slider) and the cases.
    Reads the original slider data (.osd.orig) when the piece was fixed before, so fixes never stack."""

    def __init__(self, set_name, refs, current=False):
        """current=True reads the slider data as it is now (after a fix) instead of the conversion's."""
        self.osp = os.path.join(mp.BS, "SliderSets", mp.safe(set_name) + ".osp")
        self.root = ET.parse(self.osp).getroot()
        ss = self.root.find("SliderSet")
        folder, src = ss.findtext("DataFolder"), ss.findtext("SourceFile")
        self.osd_path = os.path.join(mp.BS, "ShapeData", folder, src[:-4] + ".osd")
        self.orig = self.osd_path + ".orig"
        self.nif_path = os.path.join(mp.BS, "ShapeData", folder, src)
        nif = NifFile(self.nif_path)
        ref_names = {r.shape for r in refs}
        zapped = {d.get("target") for sl in ss.findall("Slider") if sl.get("zap") == "true" for d in sl.findall("Data")}
        self._nif = nif                          # keeps the shapes below readable (save() asks for their transform)
        self.rest, self.shape_of = {}, {}       # rest points in the UBE body's space; the slider data too
        for s in nif.shapes:
            if s.name in ref_names or s.name in zapped or re.match(r"(virtual|3ba|collision)", s.name, re.I):
                continue
            if not (s.textures.get("Diffuse") or ""):
                continue
            self.rest[s.name] = body_points(s)
            self.shape_of[s.name] = s
        self.osd = tc._osd_sparse(self.orig if os.path.isfile(self.orig) and not current else self.osd_path)
        self.sliders = []            # (slider attributes, {shape: osd entry name})
        for sl in ss.findall("Slider"):
            if sl.get("zap") == "true" or sl.get("uv") == "true":
                continue
            data = {d.get("target"): d.text.split("\\", 1)[1] for d in sl.findall("Data")
                    if d.get("local") == "true" and d.get("target") in self.rest and d.text and "\\" in d.text}
            if data:
                self.sliders.append((dict(sl.attrib), data))
        self.dense = {}              # (shape, entry) -> (N, 3) slider data
        for _a, data in self.sliders:
            for shape, dn in data.items():
                D = np.zeros_like(self.rest[shape])
                if dn in self.osd:
                    i, dd = self.osd[dn]
                    D[i] = dd
                self.dense[(shape, dn)] = body_delta(self.shape_of[shape], D)

    def values(self, pv, size):
        return np.array([tc._slider_value(a, pv, size) / 100.0 for a, _d in self.sliders])

    def cols(self, shape):
        return [k for k, (_a, data) in enumerate(self.sliders) if shape in data]

    def stack(self, shape, cols):
        """(sliders of the shape, N, 3): the shape's slider data, a view-free copy."""
        return np.stack([self.dense[(shape, self.sliders[k][1][shape])] for k in cols]) if cols else None

    def put(self, shape, cols, St):
        for j, k in enumerate(cols):
            self.dense[(shape, self.sliders[k][1][shape])] = St[j]

    def save(self):
        """Write the changed slider data (the original is kept once as .osd.orig). Each file is written next to
        its place and then swapped in, so stopping half way never leaves a broken file."""
        if not os.path.isfile(self.orig):
            shutil.copy2(self.osd_path, self.orig + ".tmp")
            os.replace(self.orig + ".tmp", self.orig)
        by_entry = {key[1]: key for key in self.dense}
        entries = []
        for name, (i, dd) in self.osd.items():
            if name not in by_entry:
                entries.append((name, i, dd))
                continue
            D = skin_delta(self.shape_of[by_entry[name][0]], self.dense[by_entry[name]])
            keep = np.nonzero(np.abs(D).max(1) > 1e-5)[0]
            entries.append((name, keep, D[keep]))
        mp.write_osd(self.osd_path + ".tmp", entries)
        os.replace(self.osd_path + ".tmp", self.osd_path)

    def restore(self):
        """Back to the slider data of the conversion."""
        if os.path.isfile(self.orig):
            os.replace(self.orig, self.osd_path)


# ---------------------------------------------------------------- measuring
def _measure(rest, St, V, cases, idx):
    """The shape's points idx at every case: (signed depth (cases, len(idx)) with nan where unclear, body normal
    there (cases, len(idx), 3)). A point's place depends on its own slider data only."""
    return _measure_at(rest[idx], None if St is None else St[:, idx], V, cases)


def _measure_at(R, Si, V, cases):
    """_measure for points with rest places R and slider data Si (sliders, len(R), 3)."""
    sd = np.full((len(cases), len(R)), np.nan)
    nn = np.zeros((len(cases), len(R), 3))
    for c, (S, _vals) in enumerate(cases):
        P = R if Si is None else R + np.tensordot(V[c], Si, axes=1)
        sd[c], nn[c] = _depth(P, S)
    return sd, nn


def _stats(sd, case_preset, presets):
    """{preset: {"verts", "in0", "in1", "worst"}} of one shape from its depths (like tailor_core.qa)."""
    d = np.nan_to_num(sd, nan=9.0)
    out = {}
    for p in presets:
        st = {"verts": sd.shape[1], "worst": 0.0}
        for c, (pp, w) in enumerate(case_preset):
            if pp == p:
                st[f"in{w}"] = int((d[c] < INSIDE).sum())
                st["worst"] = min(st["worst"], float(d[c].min()))
        out[p] = st
    return out


def _worse(a, b):
    """Shape numbers b (after) worse than a (before) at this preset? (A point just under the skin but above
    INSIDE does not count, like in the fit check.)"""
    return b["in0"] + b["in1"] > a["in0"] + a["in1"] or b["worst"] < min(a["worst"], INSIDE) - WORSE_DEPTH


def _add(total, st):
    for p, s in st.items():
        t = total.setdefault(p, {"verts": 0, "in0": 0, "in1": 0, "worst": 0.0})
        t["verts"] += s["verts"]
        t["in0"] += s["in0"]
        t["in1"] += s["in1"]
        t["worst"] = round(min(t["worst"], s["worst"]), 3)


def _violation(sd):
    """How far each point is from GAP outside, summed over the cases (unclear cases count as fine)."""
    return np.maximum(0.0, GAP - np.nan_to_num(sd, nan=9.0)).sum(0)


def _harm(sd0, sd1):
    """Per point: does sd1 (after) sink in anywhere sd0 (before, the conversion) did not, or deeper? A point that
    goes from measured to unclear counts as harm too (it may have gone right through the body)."""
    a, b = np.nan_to_num(sd0, nan=9.0), np.nan_to_num(sd1, nan=9.0)
    bad = (b < INSIDE) & ~((a < INSIDE) & (b >= a - WORSE_DEPTH))
    return (bad | (np.isnan(sd1) & ~np.isnan(sd0))).any(0)


def _solve(sdn, nn, u, V):
    """Per near point: the least change of its slider data (along u) that keeps it >= GAP outside at all cases."""
    bad = np.nan_to_num(sdn, nan=99.0) < GAP - 1e-3
    corr = np.zeros((sdn.shape[1], V.shape[1]))
    for j in np.nonzero(bad.any(0))[0]:
        ok = ~np.isnan(sdn[:, j])
        g = (nn[ok, j] * u[j]).sum(1)                      # how far a push along u moves it out, per case
        A = V[ok] * g[:, None]
        need = GAP - sdn[ok, j]
        c = np.zeros(V.shape[1])
        act = np.zeros(len(need), dtype=bool)
        for _ in range(8):                                 # active set: every case that was ever too close stays
            viol = need - A @ c > 1e-4                     # in, so fixing one preset never undoes another
            if not (viol & ~act).any():
                break
            act |= viol
            Aa = A[act]
            c = Aa.T @ np.linalg.solve(Aa @ Aa.T + 1e-3 * np.eye(len(Aa)), np.maximum(need[act], 0))
        corr[j] = np.clip(c, -MAX_STEP, MAX_STEP)
    return corr, int(bad.any(0).sum())


# ---------------------------------------------------------------- one piece
def fix(set_name, presets, refs, heel=False, surfaces=None, log=None, write=True, pvs=None):
    """Fix one project for the presets. Returns
    {"presets": {preset: {"before": numbers, "after": numbers}}, "before": points inside (all presets, both
     weights), "after": ..., "changed": points changed, "shapes": changed shapes, "kept": shapes left as they were
     because the fix made them worse somewhere, "state": "fixed" / "fine" (all presets grade A already) /
     "unchanged" (nothing helped without harm)}.
    write=False measures and solves but writes nothing."""
    pr = Project(set_name, refs)
    surfaces = {} if surfaces is None else surfaces
    pvs = pvs or {}
    cases, case_preset = [], []                          # (body surface, slider values), (preset, weight)
    for p in presets:
        pv = pvs.get(p) or tc.preset_values(p)
        for w in (0, 1):
            key = (p, w, bool(heel))
            if key not in surfaces:
                surfaces[key] = surface(refs, pv, w, heel)
            cases.append((surfaces[key], pr.values(pv, "big" if w else "small")))
            case_preset.append((p, w))
    zkey = ("-Zeroed Sliders-", 1, bool(heel))
    if zkey not in surfaces:
        surfaces[zkey] = surface(refs, pvs.get("-Zeroed Sliders-") or tc.preset_values("-Zeroed Sliders-"), 1, heel)
    S0 = surfaces[zkey]
    allV = np.array([vals for _S, vals in cases])
    zero = {"verts": 0, "in0": 0, "in1": 0, "worst": 0.0}
    before = {p: dict(zero) for p in presets}            # a piece with no visible outfit shape stays at zero
    after = {p: dict(zero) for p in presets}
    report = {"changed": 0, "shapes": 0, "kept": 0}
    plan = []                                            # (shape, rest, cols, St, V, near, u, sd, nn)
    for shape, rest in pr.rest.items():
        cols = pr.cols(shape)
        St = pr.stack(shape, cols)
        V = allV[:, cols] if cols else np.zeros((len(cases), 0))
        sd0r, n0r = _depth(rest, S0)
        near = np.nonzero(np.nan_to_num(sd0r, nan=99.0) < NEAR)[0]
        sd, nn = _measure(rest, St, V, cases, np.arange(len(rest)))
        _add(before, _stats(sd, case_preset, presets))
        plan.append((shape, rest, cols, St, V, near, n0r[near], sd, nn[:, near]))
    report["presets"] = {p: {"before": dict(before[p], grade=grade_of(before[p]))} for p in presets}
    if all(grade_of(before[p]) == "A" for p in presets):
        if write and os.path.isfile(pr.orig):
            pr.restore()                                 # fixed before for other presets: back to the conversion
        report.update(state="fine", before=sum(before[p]["in0"] + before[p]["in1"] for p in presets))
        report["after"] = report["before"]
        for p in presets:
            report["presets"][p]["after"] = report["presets"][p]["before"]
        _hide(set_name, presets, refs, heel, pvs, write, report)
        return _done(report, set_name, log)
    for shape, rest, cols, St, V, near, u, sd, nn in plan:   # u: push along the rest body normal
        st0 = _stats(sd, case_preset, presets)
        if not cols or not len(near):
            _add(after, st0)
            continue
        nbr = knn(rest[near], rest[near], min(8, len(near)))[1]
        New = St.copy()
        sd_orig = sd[:, near]
        sd_now = sd_orig.copy()
        scale = np.ones(len(near))                       # halved for a point each time its change is refused
        for rnd in range(ROUNDS + FINAL):
            corr, n_bad = _solve(sd_now, nn, u, V)
            if not n_bad:
                break
            if rnd < ROUNDS:
                corr = 0.5 * corr + 0.5 * corr[nbr].mean(1)   # smooth the motion change, not the shape
            corr *= scale[:, None]
            move = np.nonzero(np.abs(corr).max(1) > 1e-4)[0]
            if not len(move):
                break
            Try = New[:, near[move]] + corr[move].T[:, :, None] * u[move][None]
            sd_try, nn_try = _measure_at(rest[near[move]], Try, V, cases)
            # a point moves with its own data only, so each one is kept or refused on its own: kept when it is
            # closer to GAP outside overall and sinks in nowhere the conversion did not
            ok = ~_harm(sd_orig[:, move], sd_try) & (_violation(sd_try) < _violation(sd_now[:, move]) - 1e-6)
            keep = move[ok]
            New[:, near[keep]] = Try[:, ok]
            sd_now[:, keep], nn[:, keep] = sd_try[:, ok], nn_try[:, ok]
            scale[move[~ok]] *= 0.5
        changed = int((np.abs(New[:, near] - St[:, near]).max((0, 2)) > 1e-5).sum())
        sd_after = sd.copy()
        sd_after[:, near] = sd_now
        st1 = _stats(sd_after, case_preset, presets)
        if changed and not any(_worse(st0[p], st1[p]) for p in presets):     # never happens; a last guard
            pr.put(shape, cols, New)
            report["shapes"] += 1
            report["changed"] += changed
            _add(after, st1)
        else:
            report["kept"] += bool(changed)
            _add(after, st0)
    for p in presets:
        report["presets"][p]["after"] = dict(after[p], grade=grade_of(after[p]))
    report["before"] = sum(before[p]["in0"] + before[p]["in1"] for p in presets)
    report["after"] = sum(after[p]["in0"] + after[p]["in1"] for p in presets)
    report["state"] = "fixed" if report["shapes"] else "unchanged"
    if write:
        if report["shapes"]:
            pr.save()
        else:
            pr.restore()
    _hide(set_name, presets, refs, heel, pvs, write, report)
    return _done(report, set_name, log)


def _hide(set_name, presets, refs, heel, pvs, write, report):
    """After the slider data: hide the UBE body where the outfit covers it at every chosen preset (hide_body).
    report["hidden"] = body points hidden, report["through"] = body points through the outfit at any preset
    (before, after)."""
    import hide_body
    report["hidden"], report["through"] = 0, (0, 0)
    try:
        hb = hide_body.measure(set_name, presets, refs, heel, pvs=pvs)
    except Exception as e:                       # never fail a fix over this: the piece just keeps its body
        report["hide_error"] = repr(e)
        return
    report["hidden"], report["through"] = len(hb["hide"]), hb["through"]
    if write:
        hide_body.apply(set_name, refs, hb["hide"])


def _done(report, set_name, log):
    if log:
        log(f"   {set_name[11:]}: points inside at the chosen presets {report['before']} -> {report['after']}"
            f"  ({report['state']}); body hidden under the outfit: {report.get('hidden', 0)} points, through the "
            f"outfit {report.get('through', (0, 0))[0]} -> {report.get('through', (0, 0))[1]}")
    return report


# ---------------------------------------------------------------- many pieces, in parallel
_W = {}


def _init_fix():
    _W["refs"] = mp.load_refs()
    _W["surf"] = {}


def _fix_one(job):
    set_name, heel, presets, pvs, write = job
    t0 = time.time()
    try:
        rep = fix(set_name, presets, _W["refs"], heel, _W["surf"], write=write, pvs=pvs)
        rep["seconds"] = round(time.time() - t0, 1)
        return set_name, rep, None
    except Exception as e:
        return set_name, None, repr(e)


def done_for(db, sets, presets):
    """The pieces already fixed (or found fine) for these presets, or for these and more - the Tailor remembers
    them in the database (db[set]["clip"]), so a second run only works on new or re-converted pieces (a new
    conversion makes a new database entry without it). A piece fixed for more presets fits these as well. A piece
    whose hidden body (hide_body) was measured with an older rule, or never, is done again."""
    import hide_body
    want = set(presets)
    return [s for s in sets if want <= set(db.get(s, {}).get("clip") or ())
            and db.get(s, {}).get("hb") == hide_body.VERSION]


def fix_many(sets, presets, workers=6, on=None, stop=None, write=True, again=False):
    """Fix many projects for the presets, in worker processes. on(i, total, set name, report or None, error or
    None). Fixed pieces are marked in the database: db[set]["fixed"] = presets (a new conversion clears it); the
    fit grade of the preset picked in the Tailor is updated too. Pieces already done for these presets are
    skipped unless again=True."""
    db = tc.load_db()
    presets = list(presets)
    if not again:
        skip = set(done_for(db, sets, presets))
        sets = [s for s in sets if s not in skip]
    pvs = {p: tc.preset_values(p) for p in set(presets) | {"-Zeroed Sliders-"}}
    jobs = [(s, db.get(s, {}).get("heel", False), presets, pvs, write) for s in sets]
    results = {}
    if not jobs:
        return results
    picked = env.preset()
    with tc._pool(max(1, min(workers, len(jobs))), _init_fix) as pool:
        for i, (name, rep, err) in enumerate(tc._results(pool, _fix_one, jobs, stop), 1):
            if rep:
                results[name] = rep
                if write and name in db:
                    if rep["state"] == "fixed":
                        db[name]["fixed"] = presets
                    else:
                        db[name].pop("fixed", None)
                    db[name]["clip"] = sorted(presets)
                    if "hide_error" not in rep:
                        import hide_body
                        db[name]["hb"] = hide_body.VERSION
                    qa = db[name].get("qa")
                    if qa and picked in rep["presets"] and qa.get("preset") == picked:
                        a = rep["presets"][picked]["after"]
                        qa.update(in0=a["in0"], in1=a["in1"], worst=a["worst"], grade=a["grade"])
            if on:
                on(i, len(jobs), name, rep, err)
            if write and i % 25 == 0:
                tc.save_db(db)
    if write:
        tc.save_db(db)
    return results


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    env.need_ready()
    refs = mp.load_refs()
    db = tc.load_db()
    print(fix(argv[0], argv[1:], refs, db.get(argv[0], {}).get("heel", False), log=print))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
