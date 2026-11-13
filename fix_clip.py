# UBE Tailor - Copyright (C) 2026 Desertravel. Licensed under the GNU GPL v3 or later (see LICENSE).
"""Fix clipping: make a converted piece stay outside the UBE body at the presets the user picks.

A BodySlide preset sets every slider to some value (negative values and inverted sliders included); the outfit's
point i then sits at  rest_i + sum_s value_s * data_s,i  and the body at its own sum. No rule per slider can keep
the outfit outside at every preset (25 of 27 presets on the test list use negative values), so this solves it
for the presets that matter: for every outfit point that comes closer than GAP to the body (or goes inside) at
any of them, it finds the smallest change of that point's slider data, along the body normal, that keeps it at
least GAP outside at ALL of them at once (a small least-norm problem per point, with the presets as constraints).
The change is smoothed over neighbouring points (the motion is smoothed, not the shape, so details stay), the
piece is measured again, and this repeats a few times. Only the project's slider data (.osd) changes - the rest
shape stays as converted; BodySlide must build the piece again.

  python fix_clip.py <set name> <preset> [<preset> ...]
"""
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

import numpy as np

import env
import make_projects as mp
import tailor_core as tc
import ube_field
from nifly_env import NifFile, knn

GAP = 0.15           # wanted distance between outfit and body at every chosen preset
NEAR = 3.0           # only outfit points this close to the body at rest are looked at (skirts, capes move freely)
ROUNDS = 3           # measure - solve - smooth rounds
MAX_STEP = 4.0       # largest change of one slider's data at one point (units at 100 %), against wild results


def _depth(P, S):
    """(signed distance, body normal there) of points to a body surface; nan where the side is unclear."""
    SV, SF, FN = S
    tri, bary, dist = ube_field.project(P, SV, SF)
    q = ube_field.interp(SV, SF, tri, bary)
    n = FN[tri]
    dot = ((P - q) * n).sum(1)
    sd = np.sign(dot) * dist
    ok = (sd > -mp.CLIP_BAND) & ((np.abs(dot) >= 0.6 * dist) | (dist < 0.02))
    return np.where(ok, sd, np.nan), n


class Project:
    """A converted piece's BodySlide project: outfit shapes, their slider data (dense, per slider) and the cases."""

    def __init__(self, set_name, refs):
        self.osp = os.path.join(mp.BS, "SliderSets", mp.safe(set_name) + ".osp")
        self.root = ET.parse(self.osp).getroot()
        ss = self.root.find("SliderSet")
        folder, src = ss.findtext("DataFolder"), ss.findtext("SourceFile")
        self.osd_path = os.path.join(mp.BS, "ShapeData", folder, src[:-4] + ".osd")
        nif = NifFile(os.path.join(mp.BS, "ShapeData", folder, src))
        ref_names = {r.shape for r in refs}
        zapped = {d.get("target") for sl in ss.findall("Slider") if sl.get("zap") == "true" for d in sl.findall("Data")}
        self.rest = {}
        for s in nif.shapes:
            if s.name in ref_names or s.name in zapped or re.match(r"(virtual|3ba|collision)", s.name, re.I):
                continue
            if not (s.textures.get("Diffuse") or ""):
                continue
            self.rest[s.name] = np.array(s.verts, dtype=np.float64)
        self.osd = tc._osd_sparse(self.osd_path)
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
                self.dense[(shape, dn)] = D

    def values(self, pv, size):
        return np.array([tc._slider_value(a, pv, size) / 100.0 for a, _d in self.sliders])

    def at(self, shape, vals):
        P = self.rest[shape].copy()
        for v, (_a, data) in zip(vals, self.sliders):
            if v and shape in data:
                P += v * self.dense[(shape, data[shape])]
        return P

    def save(self):
        """Write the changed slider data back (a copy of the original .osd is kept once, as .osd.orig)."""
        if not os.path.exists(self.osd_path + ".orig"):
            shutil.copy2(self.osd_path, self.osd_path + ".orig")
        by_entry = {dn: key for key in self.dense for dn in (key[1],)}
        entries = []
        for name, (i, dd) in self.osd.items():
            if name not in by_entry:
                entries.append((name, i, dd))
                continue
            D = self.dense[by_entry[name]]
            keep = np.nonzero(np.abs(D).max(1) > 1e-5)[0]
            entries.append((name, keep, D[keep]))
        mp.write_osd(self.osd_path, entries)


def fix(set_name, presets, refs, heel=False, surfaces=None, log=None):
    """Fix one project for the presets. Returns {"before": points too close/inside, "after": ..., "changed": points}."""
    pr = Project(set_name, refs)
    surfaces = {} if surfaces is None else surfaces
    cases = []                                         # (body surface, slider values)
    for p in presets:
        pv = tc.preset_values(p)
        for w in (0, 1):
            key = (p, w, bool(heel))
            if key not in surfaces:
                surfaces[key] = tc.body_surface(refs, pv, w, heel)
            cases.append((surfaces[key], pr.values(pv, "big" if w else "small")))
    zkey = ("-Zeroed Sliders-", 1, bool(heel))
    if zkey not in surfaces:
        surfaces[zkey] = tc.body_surface(refs, tc.preset_values("-Zeroed Sliders-"), 1, heel)
    S0 = surfaces[zkey]
    report = {"before": 0, "after": 0, "changed": 0}
    for shape, rest in pr.rest.items():
        cols = [k for k, (_a, data) in enumerate(pr.sliders) if shape in data]
        if not cols:
            continue
        sd0, n0 = _depth(rest, S0)
        near = np.nonzero(np.nan_to_num(sd0, nan=99.0) < NEAR)[0]
        if not len(near):
            continue
        nbr = knn(rest[near], rest[near], min(8, len(near)))[1]
        V = np.array([vals[cols] for _S, vals in cases])          # (cases, sliders of this shape)
        u = n0[near]                                               # push along the rest body normal
        for rnd in range(ROUNDS + 1):
            sd = np.full((len(cases), len(near)), np.nan)
            nn = np.zeros((len(cases), len(near), 3))
            for c, (S, vals) in enumerate(cases):
                sd[c], nn[c] = _depth(pr.at(shape, vals)[near], S)
            bad = np.nan_to_num(sd, nan=99.0) < GAP - 1e-3
            if rnd == 0:
                report["before"] += int(bad.any(0).sum())
            if rnd == ROUNDS or not bad.any():
                report["after"] += int(bad.any(0).sum())
                break
            corr = np.zeros((len(near), len(cols)))
            for j in np.nonzero(bad.any(0))[0]:
                ok = ~np.isnan(sd[:, j])
                g = (nn[ok, j] * u[j]).sum(1)                      # how far a push along u moves it out, per case
                A = V[ok] * g[:, None]
                need = GAP - sd[ok, j]
                c = np.zeros(len(cols))
                for _ in range(4):                                 # active set: the cases still too close
                    r = need - A @ c
                    act = r > 1e-4
                    if not act.any():
                        break
                    Aa = A[act]
                    c += Aa.T @ np.linalg.solve(Aa @ Aa.T + 1e-3 * np.eye(len(Aa)), r[act])
                corr[j] = np.clip(c, -MAX_STEP, MAX_STEP)
            corr = 0.5 * corr + 0.5 * corr[nbr].mean(1)           # smooth the motion change, not the shape
            report["changed"] = max(report["changed"], int((np.abs(corr).max(1) > 1e-4).sum()))
            for k, col in enumerate(cols):
                D = pr.dense[(shape, pr.sliders[col][1][shape])]
                D[near] += corr[:, k:k + 1] * u
    pr.save()
    if log:
        log(f"   {set_name[11:]}: points too close / inside at the chosen presets: {report['before']} -> {report['after']}")
    return report


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
