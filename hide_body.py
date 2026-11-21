# UBE Tailor - Copyright (C) 2026 Desertravel. Licensed under the GNU GPL v3 or later (see LICENSE).
"""Hide the UBE body where the outfit covers it.

Every converted body piece carries the UBE body inside it (make_projects: the parts the author had cut away are
zapped). Where tight fabric or plate lies on the skin, the body moves with its own sliders and the outfit with its
slider data; at strong presets (muscle, belly, curves) the skin pushes through in small spots. Outfit makers
remove ("zap") the body under such pieces by hand: what is not there cannot poke through.

This does it per piece, for the presets the player uses: a body point is hidden when, at every one of them, an
opaque outfit surface lies along the skin right over it (a sheet roughly parallel to the skin, within a few units
outside it, or a little under it where it clips). A band of body points along the edge of every covered region
stays (openings, cut-outs, the neckline), so no hole can show. Shapes with transparency (lace, mesh, alpha cut-outs)
never count as covering: the skin must show through them. Only the project's hidden-body zap changes (.osd, and
.osd.orig of Fix clipping); BodySlide Batch Build makes the meshes.

  python hide_body.py <set name> <preset> [<preset> ...]      measure and print, writes nothing
"""
import os
import sys

import numpy as np

import env
import fix_clip
import make_projects as mp
import tailor_core as tc
import ube_field
from nifly_env import knn

OUT = 3.0        # outfit up to this far outside the skin covers it
IN = 1.5         # ... or this far under it (where it clips: the very spots to hide)
PARALLEL = 0.5   # |outfit normal . skin normal| at least this: a sheet lying along the skin, not an edge or a strap
ALONG = 0.6      # the outfit point must lie roughly along the skin normal (not beside the point)
EDGE = 1         # rings of body points kept visible along every covered region's edge
VERSION = 1      # pieces measured with an older rule are measured again (db[set]["hb"])


def _vertex_normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    return N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)


def _neighbours(nv, F):
    """Per body point the points it shares a triangle with (an index array padded with -1)."""
    e = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e = np.vstack([e, e[:, ::-1]])
    e = np.unique(e, axis=0)
    counts = np.bincount(e[:, 0], minlength=nv)
    out = -np.ones((nv, max(int(counts.max()), 1)), dtype=np.int64)
    starts = np.cumsum(counts) - counts
    out[e[:, 0], np.arange(len(e)) - starts[e[:, 0]]] = e[:, 1]
    return out


def _erode(mask, nbr, rings):
    """Keep a point only if every point within `rings` steps over the mesh is in the mask too."""
    m = mask.copy()
    for _ in range(rings):
        ok = np.where(nbr >= 0, m[np.maximum(nbr, 0)], True).all(1)
        m &= ok
    return m


def _cover_at(B, BN, O, OF, ON, cand):
    """Which candidate body points an outfit surface (O, OF, face normals ON) covers at one preset."""
    if not len(cand) or not len(OF):
        return np.zeros(len(cand), dtype=bool)
    P = B[cand]
    tri, bary, dist = ube_field.project(P, O, OF)
    q = ube_field.interp(O, OF, tri, bary)
    w = q - P
    n = BN[cand]
    s = (w * n).sum(1)                                   # how far outside the skin (negative: under it)
    par = np.abs((ON[tri] * n).sum(1))
    along = (np.abs(s) >= ALONG * dist) | (dist < 0.05)
    return (s < OUT) & (s > -IN) & (par > PARALLEL) & along


class Piece:
    """A converted piece: its project (fix_clip.Project), the opaque outfit shapes and the body's current zap."""

    def __init__(self, set_name, refs):
        self.pr = fix_clip.Project(set_name, refs, current=True)    # the slider data BodySlide builds from
        self.body = next(r for r in refs if r.key == "body")
        self.entry = self.body.shape + mp.ZAP
        conv = tc._osd_sparse(self.pr.orig) if os.path.isfile(self.pr.orig) else self.pr.osd
        self.has_body = self.entry in conv                          # the conversion's own zap, not an earlier one
        idx = conv[self.entry][0] if self.has_body else np.zeros(0, dtype=np.int64)
        self.zapped = np.zeros(len(self.body.verts), dtype=bool)
        self.zapped[idx[idx < len(self.body.verts)]] = True
        self.opaque = [n for n, s in self.pr.shape_of.items() if not s.has_alpha_property]
        self.tris = {n: np.array(self.pr.shape_of[n].tris, dtype=np.int64) for n in self.opaque}

    def outfit_at(self, pv, size):
        vals = self.pr.values(pv, size)
        Vs, Fs, off = [], [], 0
        for n in self.opaque:
            cols = self.pr.cols(n)
            P = self.pr.rest[n]
            if cols:
                P = P + np.tensordot(vals[cols], self.pr.stack(n, cols), axes=1)
            Vs.append(P)
            Fs.append(self.tris[n] + off)
            off += len(P)
        if not Vs:
            return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64), np.zeros((0, 3))
        O, OF = np.vstack(Vs), np.vstack(Fs)
        ON = np.cross(O[OF[:, 1]] - O[OF[:, 0]], O[OF[:, 2]] - O[OF[:, 0]])
        ON /= np.linalg.norm(ON, axis=1, keepdims=True) + 1e-12
        return O, OF, ON


def body_at(refs, pv, w, heel, body):
    """The UBE body part's points at a preset (weight w), from tailor_core.body_surface."""
    SV, _SF, _FN = tc.body_surface(refs, pv, w, heel)
    off = 0
    for r in refs:
        if r is body:
            return SV[off:off + len(r.verts)]
        off += len(r.verts)
    raise KeyError("body")


def measure(set_name, presets, refs, heel=False, pvs=None):
    """{"hide": body point indices to hide, "zapped": hidden before, "total": body points, "opaque": shapes that
    cover / all shapes, "poke": {preset: (body points through the outfit before, after)}}."""
    pvs = pvs or {}
    pc = Piece(set_name, refs)
    body = pc.body
    nbr = _neighbours(len(body.verts), body.tris)
    rep = {"total": len(body.verts), "zapped": int(pc.zapped.sum()), "opaque": (len(pc.opaque), len(pc.pr.rest)),
           "hide": np.zeros(0, dtype=np.int64), "poke": {}, "through": (0, 0)}
    if not pc.has_body or not pc.opaque:
        return rep
    cand = np.nonzero(~pc.zapped)[0]
    O0, _F, _N = pc.outfit_at({}, "small")
    near = knn(O0, body.verts[cand])[0][:, 0] < OUT + IN + 2.0 if len(O0) else np.zeros(len(cand), dtype=bool)
    cand = cand[near]
    covered = np.ones(len(cand), dtype=bool)
    pokes = []
    for p in presets:
        pv = pvs.get(p) or tc.preset_values(p)
        for w in (0, 1):
            B = body_at(refs, pv, w, heel, body)
            BN = _vertex_normals(B, body.tris)
            O, OF, ON = pc.outfit_at(pv, "big" if w else "small")
            covered &= _cover_at(B, BN, O, OF, ON, cand)
            pokes.append((p, w, B, BN, O, OF))
    mask = np.zeros(len(body.verts), dtype=bool)
    mask[cand[covered]] = True
    mask = _erode(mask | pc.zapped, nbr, EDGE) & ~pc.zapped
    rep["hide"] = np.nonzero(mask)[0]
    vis = np.nonzero(~pc.zapped)[0]
    any_poke = np.zeros(len(vis), dtype=bool)
    for p, w, B, BN, O, OF in pokes:              # body points standing out through the outfit, before / after
        if not len(OF):
            continue
        tri, bary, dist = ube_field.project(B[vis], O, OF)
        s = ((ube_field.interp(O, OF, tri, bary) - B[vis]) * BN[vis]).sum(1)
        poke = (s < fix_clip.INSIDE) & (s > -IN) & (np.abs(s) >= ALONG * dist)
        any_poke |= poke
        a, b = int(poke.sum()), int((poke & ~mask[vis]).sum())
        old = rep["poke"].get(p, (0, 0))
        rep["poke"][p] = (old[0] + a, old[1] + b)
    rep["through"] = (int(any_poke.sum()), int((any_poke & ~mask[vis]).sum()))   # at any preset, before / after
    return rep


def apply(set_name, refs, hide):
    """The body's hidden-body zap in the project's .osd becomes the conversion's zap plus these points (never an
    earlier run's: the conversion's data stays in .osd.orig, made here when Fix clipping did not make it already).
    Returns True when the file changed."""
    import shutil
    import xml.etree.ElementTree as ET
    body = next(r for r in refs if r.key == "body")
    entry = body.shape + mp.ZAP
    ss = ET.parse(os.path.join(mp.BS, "SliderSets", mp.safe(set_name) + ".osp")).getroot().find("SliderSet")
    osd = os.path.join(mp.BS, "ShapeData", ss.findtext("DataFolder"), ss.findtext("SourceFile")[:-4] + ".osd")
    orig = osd + ".orig"
    if not os.path.isfile(osd):
        return False
    conv = tc._osd_sparse(orig if os.path.isfile(orig) else osd)
    data = tc._osd_sparse(osd)
    if entry not in conv or entry not in data:
        return False
    idx = np.union1d(conv[entry][0], np.asarray(hide, dtype=np.int64)).astype(np.int64)
    if np.array_equal(idx, data[entry][0]):
        return False
    if len(hide) and not os.path.isfile(orig):
        shutil.copy2(osd, orig + ".tmp")
        os.replace(orig + ".tmp", orig)
    data[entry] = (idx, np.tile([0.0, 1.0, 0.0], (len(idx), 1)))
    mp.write_osd(osd + ".tmp", [(n, i, d) for n, (i, d) in data.items()])
    os.replace(osd + ".tmp", osd)
    return True


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    env.need_ready()
    refs = mp.load_refs()
    rep = measure(argv[0], argv[1:], refs, tc.load_db().get(argv[0], {}).get("heel", False))
    print(f"body points {rep['total']}, hidden before {rep['zapped']}, to hide now {len(rep['hide'])}, "
          f"covering shapes {rep['opaque'][0]} of {rep['opaque'][1]}")
    for p, (a, b) in rep["poke"].items():
        print(f"   {p}: body points through the outfit {a} -> {b}")
    print(f"   at any of them: {rep['through'][0]} -> {rep['through'][1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
