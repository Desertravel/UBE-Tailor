# UBE Tailor - Copyright (C) 2026 Desertravel. Licensed under the GNU GPL v3 or later (see LICENSE).
"""Create real UBE BodySlide projects for 3BA/CBBE outfits (what Outfit Studio "conversion" does, automated).

usage:
  python make_projects.py <mesh path without _0/_1.nif> ...        game mesh (loose or BSA) as source
  python make_projects.py --proj "<3BA SliderSet name>" ...          a 3BA BodySlide project's clean source nif

Per outfit:
  * old body shapes (3BA/CBBE body, feet, hands) are found by texture; for each body part they covered
    the matching UBE base shape is added: body -> BaseShape, feet -> Feet, hands -> Hands
  * every outfit shape (incl. SMP collision bodies) is conformed to the UBE base shape (ube_field "b")
  * all UBE body/feet/hands sliders are transferred to the outfit shapes (k-nearest, IDW)
  * a hidden zap removes the old body shapes and the parts of the UBE shapes the author had cut away
  * files go to <output mod>\\CalienteTools\\BodySlide (env.OUT_MOD), group "UBE Auto Conversions"
"""
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from xml.sax.saxutils import escape, quoteattr

import numpy as np

import bodytri
import smp_check
import ube_field
from nif_patch import SseNif
import env
from nifly_env import NifFile, knn, read_osd
from resolve_mesh import Resolver
from ube_project import add_ube_refs
import ube_weights

MOD = env.OUT_MOD                          # the output mod: projects, the merged patch
BS = os.path.join(MOD, "CalienteTools", "BodySlide") if MOD else None
GROUP = "UBE Auto Conversions"
BODY_RX = re.compile(r"actors[\\/]character[\\/]female[\\/]female(body|hands|feet)", re.I)
ZAP = "UBEAuto_HideBody"
WORK = os.path.join(env.WORK, "src") if env.WORK else None   # copies of the source meshes
K = 8
OSD_MAGIC = b"\x00DSO"   # BodySlide writes the uint32 'OSD\0' little-endian
HEEL = "HiHeelz_CBBE"
MIN_GAP, CLIP_BAND = 0.1, 1.5   # anti-clip: keep outfits >= MIN_GAP outside UBE; ignore deeper than CLIP_BAND
ZAP_SURFACE = 0.5   # feet/hands: hide UBE verts farther than this from the old part's surface
CROTCH_CUT = 0.5    # the UBE crotch (partition 53) is hidden only when the author cut away more than this share of it
HEAD_SLOTS = {30, 31, 41, 42, 43, 130, 131, 141, 142, 143}   # always head pieces: never converted
# 44 face, 45 neck, 47 back, 55 face (alt): many mods put body pieces here too (chest plates, pauldrons, leg
# armor, loincloths), so these are judged by the mesh: only a piece that stays above the neck is skipped.
NECK_Z = 105.0
# Version of the conversion method. RAISE IT whenever a change here (or in ube_field / ube_weights / nif_patch)
# changes what a converted project looks like: the Tailor then lists every project made with an older version
# as outdated and offers to re-convert it, so improvements reach the outfits converted before them.
#   1 = 2026-11-11: anti-clip push-out, UBE bone weights, SMP-safe bones, head pieces judged by the mesh
#   2 = 2026-11-12: no old 3BA BODYTRI in projects, SMP safety net after the weight copy, flat feet for
#       heel-posed stockings / pantyhose (pieces without the feet slot)
#   3 = 2026-11-16: pieces made in a bone's space (rings, some armors) read where the game shows them; one-bone
#       pieces keep their author's weights. Head-piece verdicts of older versions are checked again.
METHOD = 3


class HeadPiece(Exception):
    """The mesh sits on the head only (helmet, mask, hair): it needs no UBE version."""


def smp_falling(nif_path, resolver):
    """{(shape, bone)} that the outfit's HDT-SMP XML would let fall (empty: no SMP / XML not found / none)."""
    try:
        r = smp_check.check_nif(nif_path, resolver)
    except Exception:
        return set()
    return set(r[1]) if r and r[1] else set()


class OldrimMesh(Exception):
    """The mod ships the mesh in the old Skyrim LE format, which this converter (and often SE itself) cannot use."""


def _one_bone(shape):
    """True when every point of a skinned shape hangs fully on one and the same bone."""
    try:
        bw = shape.bone_weights
    except Exception:
        return False
    if not bw or len(bw) != 1:
        return False
    lst = next(iter(bw.values()))
    return len({i for i, w in lst if w > 0.999}) == len(shape.verts)


def lowest_point(nif_path):
    """Lowest z of all shapes of a nif, in the nif's global space."""
    n = SseNif(nif_path)
    zs = []
    for s in n.shapes:
        p = n.positions(s)
        if len(p):
            zs.append(float(n.to_global(s, p)[:, 2].min()))
    return min(zs) if zs else None


class Ref:
    """One UBE base part (body / feet / hands) with its BodySlide sliders."""

    def __init__(self, key, partition, nif, osd, osp):
        self.key, self.partition, self.nif = key, partition, nif
        self.folder = os.path.basename(os.path.dirname(nif))
        s = NifFile(nif).shapes[0]
        self.shape = s.name
        self.verts = np.array(s.verts, dtype=np.float64)
        self.tris = np.array(s.tris, dtype=np.int64)
        # the crotch with the vulva (partition 53 of the UBE body): 3BA has no vulva, so its points lie away from
        # an old 3BA body and the zap below would cut them out of every body piece (keep_crotch)
        self.crotch = np.zeros(len(self.verts), bool)
        ids = [p.id for p in (s.partitions or [])]
        if 53 in ids and len(s.partition_tris) == len(self.tris):
            self.crotch[self.tris[np.array(s.partition_tris) == ids.index(53)].ravel()] = True
        root = ET.parse(osp).getroot()
        ss = next((s for s in root.iter("SliderSet") if (s.findtext("DataFolder") or "").strip() == self.folder),
                  root.find("SliderSet"))
        self.sliders = OrderedDict()
        for sl in ss.findall("Slider"):
            d = sl.find("Data")
            self.sliders[sl.get("name")] = (dict(sl.attrib), d.get("name") if d is not None else None)
        self.osd = read_osd(osd, len(self.verts))
        # Optional extra sliders: other projects on the same UBE data (UBE's "... Male" projects) can carry sliders the
        # user imported into them, e.g. LDD Male Shape Shifters for UBE 2.0 (Outfit Studio, Import OSD). Outfits get
        # them too, so they follow a male UBE body. Always off by default: female bodies and presets never change.
        self.extra = []
        for other in root.iter("SliderSet"):
            if other is ss or (other.findtext("DataFolder") or "").strip() != self.folder:
                continue
            for sl in other.findall("Slider"):
                d, name = sl.find("Data"), sl.get("name")
                dn = d.get("name") if d is not None else None
                if name and name not in self.sliders and dn in self.osd:
                    self.sliders[name] = (dict(sl.attrib, small="0", big="0"), dn)
                    self.extra.append(name)


def keep_crotch(hide, r):
    """Hidden UBE body points without the crotch (partition 53), unless the author cut most of it away.
    The UBE vulva lies deeper than the smooth 3BA crotch, so "farther than 1.2 from the old body" took it out of
    every body piece (bikini tops, dresses: the vulva vanished as soon as one was worn, TNG or not). The game
    hides partition 53 by itself when something is worn on slot 53, like on the naked UBE body."""
    c = getattr(r, "crotch", None)
    if c is None or not c.any() or not len(hide):
        return hide
    h = np.zeros(len(c), bool)
    h[hide] = True
    if (h & c).sum() > CROTCH_CUT * c.sum():
        return hide
    return np.nonzero(h & ~c)[0]


# Outfit adjust sliders of UBE outfits ("BiggerBody_ForOutfits" ...): all at 0 by default, so nothing changes until
# the player raises one in BodySlide to give a clipping area more room. Each pushes the outfit out along the body
# normal under it, in its own area (from the UBE body's bone weights), by the amount at 100. Areas and amounts as in
# the outfit projects of UBE mods (297 projects measured).
FRONT, BACK, SIDE = "front", "back", "side"
FOR_OUTFITS = [  # (slider, bone name parts, facing, push at 100)
    ("BiggerBody_ForOutfits", None, None, 0.55),
    ("BiggerUpperTorso_ForOutfits", ("Spine2", "Clavicle", "Breast"), None, 0.35),
    ("BiggerBreasts_ForOutfits", ("Breast",), None, 1.35),
    ("BiggerUpperarms_ForOutfits", ("UpperArm", "UpperarmTwist"), None, 0.65),
    ("BiggerWrists_ForOutfits", ("Forearm",), None, 0.65),
    ("BiggerHands_ForOutfits", ("Hand", "Finger"), None, 0.7),
    ("BiggerBelly_ForOutfits", ("Spine [", "Spine1", "Belly", "Pelvis"), FRONT, 0.8),
    ("BiggerUpperSpine_ForOutfits", ("Spine2", "Clavicle"), BACK, 0.7),
    ("BiggerLowerSpine_ForOutfits", ("Spine [", "Spine1", "Pelvis"), BACK, 0.55),
    ("BiggerHips_ForOutfits", ("Pelvis", "Thigh"), SIDE, 0.45),
    ("BiggerButt_ForOutfits", ("Butt",), None, 0.4),
    ("BiggerThighs_ForOutfits", ("Thigh",), None, 0.75),
    ("BiggerCalves_ForOutfits", ("Calf",), None, 0.75),
    ("BiggerFeet_ForOutfits", ("Foot", "Toe"), None, 0.8),
]
FOLLOW_MATCH = 0.6   # outfit points whose bones match the body under them less than this follow their own bones' body


def _vertex_normals(V, F):
    FN = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], FN)
    return N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)


def outfit_areas(refs, U, BW, bones):
    """{slider: (area 0..1 per UBE point, push at 100)} and the UBE normals (body, feet, hands stacked like U)."""
    N, off = [], 0
    for r in refs:
        n = len(r.verts)
        N.append(_vertex_normals(U[off:off + n], r.tris))
        off += n
    N = np.vstack(N)
    front = np.clip((N[:, 1] + 0.25) / 0.5, 0, 1)             # the body faces +Y
    face = {FRONT: front, BACK: 1 - front, SIDE: np.clip((np.abs(N[:, 0]) - 0.35) / 0.35, 0, 1)}
    out = {}
    for name, parts, facing, push in FOR_OUTFITS:
        if parts is None:
            a = np.ones(len(U))
        else:
            cols = [i for i, b in enumerate(bones) if any(p in b for p in parts)]
            a = BW[:, cols].sum(1) if cols else np.zeros(len(U))
            a = np.clip(a / max(np.percentile(a[a > 0], 95) if (a > 0).any() else 1, 1e-6), 0, 1)
        if facing:
            a = a * face[facing]
        out[name] = (a, push)
    return out, N


def outfit_bones(nif_path, names, bones):
    """{shape: (verts, len(bones)) weights of the outfit points over the UBE body's bones}. A bone the body does not
    have (HDT-SMP, cloth) counts as its nearest ancestor the body has; points with none get an empty row."""
    nif = NifFile(nif_path)
    col = {b: i for i, b in enumerate(bones)}
    out = {}
    for s in nif.shapes:
        if s.name not in names:
            continue
        W = np.zeros((len(s.verts), len(bones)))
        for b, lst in s.bone_weights.items():
            a, seen = b, 0
            while a is not None and a not in col and seen < 64:
                node = nif.nodes.get(a)
                a = node.parent.name if node is not None and node.parent is not None else None
                seen += 1
            if a in col:
                for vi, w in lst:
                    W[vi, col[a]] += w
        sw = W.sum(1, keepdims=True)
        out[s.name] = np.divide(W, sw, out=np.zeros_like(W), where=sw > 0)
    return out


class Follow:
    """Which UBE points an outfit point takes its slider data from. Normally its K nearest (Outfit Studio
    "Conform"). A point weighted to other bones than the body under it - a hanging sleeve or skirt panel next to
    the thigh, hair over the back - takes it from the nearest body points of its own bones instead, so a sleeve
    follows the arm, not the thigh it hangs next to (like the hand-made conversions). It never sinks in more than
    with the nearest points: where they would push it out along the body normal by more than the room it has
    from the body (its gap at rest), it is pushed out by the rest."""

    def __init__(self, U, P, BW, Wo, UN, room=None):
        d, I = knn(U, P, K)
        w = 1.0 / (d ** 2 + 1e-4)
        self.I, self.w = I, w / w.sum(1, keepdims=True)
        n = (UN[I] * self.w[..., None]).sum(1)
        self.n = n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
        self.room = np.zeros(len(P)) if room is None else room
        self.alpha, self.parts = np.zeros(len(P)), []
        if Wo is None or not len(P):
            return
        has = Wo.sum(1) > 0
        match = (self.w * np.minimum(Wo[:, None, :], BW[I]).sum(2)).sum(1)
        self.alpha = np.where(has, np.clip((FOLLOW_MATCH - match) / 0.3, 0, 1), 0.0)
        bad = np.nonzero(self.alpha > 0)[0]
        if not len(bad):
            return
        for b in np.nonzero((Wo[bad] > 0.05).any(0))[0]:
            sub = np.nonzero(BW[:, b] >= 0.2)[0]
            rows = bad[Wo[bad, b] > 0.05]
            if len(sub) < K or not len(rows):
                continue
            db, Ib = knn(U[sub], P[rows], K)
            wb = 1.0 / (db ** 2 + 1e-4)
            self.parts.append((rows, Wo[rows, b], sub[Ib], wb / wb.sum(1, keepdims=True)))
        tot = np.zeros(len(P))
        for rows, share, _I, _w in self.parts:
            tot[rows] += share
        self.tot = tot

    def probe(self, D):
        """First pass over the body sliders: add up how far the nearest points would push each point out beyond
        what its own bones' points do. settle() then keeps the own-bone follow only where all of that together
        still fits in the room the point has from the body, so no combination of sliders makes it sink in."""
        if not self.parts:
            return
        if not hasattr(self, "acc"):
            self.acc = np.zeros(len(self.alpha))
        out, res = self._mix(D)
        self.acc += np.maximum(((out - res) * self.n).sum(1), 0)

    def settle(self):
        if self.parts and hasattr(self, "acc"):
            self.alpha[self.acc > 2 * self.room] = 0.0

    def _mix(self, D):
        out = (D[self.I] * self.w[..., None]).sum(1)
        own = np.zeros_like(out)
        for rows, share, I, w in self.parts:
            own[rows] += share[:, None] * (D[I] * w[..., None]).sum(1)
        t = self.tot[:, None]
        own = np.divide(own, t, out=np.array(out), where=t > 0)
        a = self.alpha[:, None]
        return out, (1 - a) * out + a * own

    def __call__(self, D):
        """D (one value or vector per UBE point) at the outfit points."""
        out = (D[self.I] * self.w[..., None]).sum(1) if D.ndim == 2 else (D[self.I] * self.w).sum(1)
        if not self.parts:
            return out
        own = np.zeros_like(out)
        for rows, share, I, w in self.parts:
            v = (D[I] * w[..., None]).sum(1) if D.ndim == 2 else (D[I] * w).sum(1)
            own[rows] += (share[:, None] * v) if D.ndim == 2 else share * v
        t = self.tot if D.ndim == 1 else self.tot[:, None]
        own = np.divide(own, t, out=np.array(out), where=t > 0)
        a = self.alpha if D.ndim == 1 else self.alpha[:, None]
        res = (1 - a) * out + a * own
        if D.ndim == 2:
            lack = ((out - res) * self.n).sum(1)
            res += np.maximum(lack - self.room, 0)[:, None] * self.n
        return res


def load_refs():
    return [Ref(*p) for p in ube_field.parts()]


def write_osd(path, entries):
    with open(path, "wb") as f:
        f.write(OSD_MAGIC + struct.pack("<II", 1, len(entries)))
        for name, idx, diff in entries:
            nb = name.encode("utf-8")
            f.write(struct.pack("<B", len(nb)) + nb + struct.pack("<H", len(idx)))
            rec = np.zeros(len(idx), dtype=np.dtype([("i", "<u2"), ("d", "<f4", 3)]))
            rec["i"], rec["d"] = idx, diff
            f.write(rec.tobytes())


def safe(s):
    return re.sub(r"[^A-Za-z0-9 _\-\[\]\(\)\.]", "_", s)


# ------------------------------------------------------------------ inputs
def find_project(set_name):
    """(source nif, output rel path without _0/_1) of a BodySlide SliderSet in an enabled mod."""
    for d in env.bodyslide_dirs("SliderSets"):
        for f in os.listdir(d):
            if not f.lower().endswith(".osp"):
                continue
            try:
                root = ET.parse(os.path.join(d, f)).getroot()
            except ET.ParseError:
                continue
            for ss in root.iter("SliderSet"):
                if ss.get("name") != set_name:
                    continue
                folder = ss.findtext("DataFolder")
                src = os.path.join(os.path.dirname(d), "ShapeData", folder, ss.findtext("SourceFile"))
                out = ss.findtext("OutputPath").strip().replace("/", "\\")
                if out.lower().startswith("meshes\\"):
                    out = out[7:]
                return src, os.path.join(out, ss.findtext("OutputFile").strip())
    raise KeyError(f"BodySlide project not found: {set_name}")


# ------------------------------------------------------------------ anti-clip
def push_out(P, V, F, FN, gap=MIN_GAP, band=CLIP_BAND, k=8):
    """Displacement that moves outfit points lying inside (or closer than `gap` to) the UBE surface out to `gap`,
    spread to neighbours so no creases form. Points deeper than `band` are left alone (meant to be inside)."""
    tri, bary, dist = ube_field.project(P, V, F)
    q = ube_field.interp(V, F, tri, bary)
    n = FN[tri]
    dot = ((P - q) * n).sum(1)
    sd = np.sign(dot) * dist
    clear = (np.abs(dot) >= 0.6 * dist) | (dist < 0.02)   # near openings (neck, wrists, ankles) the side is unclear
    need = np.where((sd < gap) & (sd > -band) & clear, gap - sd, 0.0)
    if not need.any():
        return np.zeros_like(P)
    _d, I = knn(P, P, min(k, len(P)))
    push = np.maximum(need, need[I].mean(1))
    push[sd <= -band] = 0.0
    return n * push[:, None]


# ------------------------------------------------------------------ project
def make_project(base, src, ref, refs, resolver, log=print, slots=None):
    base = base.replace("/", "\\")
    if src is None:
        first = "" if base.lower().endswith(".nif") else "_1.nif"        # single-weight mesh: the base is the file
        src = os.path.join(WORK, "meshes", base + first)
        if not os.path.isfile(src):
            src = resolver.extract(base + first, WORK)
        if not src:
            raise FileNotFoundError(base)
    ported = False
    try:
        low = lowest_point(src)
    except ValueError as e:
        if "not Skyrim SE" not in str(e):
            raise
        # a Skyrim LE (Oldrim) mesh: port a copy to SE in the work folder (the mod's own file is never touched)
        import le_port
        se = os.path.join(WORK, "le_port", os.path.relpath(src, WORK) if src.startswith(WORK) else
                          os.path.basename(src))
        try:
            le_port.port(src, se)
            low = lowest_point(se)
        except Exception as e2:
            raise OldrimMesh(f"Skyrim LE (Oldrim) mesh that could not be ported to SE ({e2}) - port it with "
                             "Cathedral Assets Optimizer") from None
        src, ported = se, True
    if low is not None and low >= NECK_Z:
        raise HeadPiece(f"head piece (lowest point z={low:.0f}, above the neck): no UBE version needed")
    stem = re.sub(r"(?i)\.nif$", "", base)          # a single-weight base is the whole file name
    set_name = "UBE Auto - " + stem.replace("\\", " - ")  # = tailor_core.set_name_of(base)
    folder = safe(set_name)
    fname = safe(os.path.basename(stem))
    shape_dir = os.path.join(BS, "ShapeData", folder)
    os.makedirs(shape_dir, exist_ok=True)
    nif_path = os.path.join(shape_dir, fname + ".nif")
    osd_name = fname + ".osd"

    src_nif = NifFile(src)
    info = {s.name: ((s.textures.get("Diffuse", "") or ""), {p.id for p in s.partitions}) for s in src_nif.shapes}
    bodies = {n for n, (t, _p) in info.items() if BODY_RX.search(t)}
    covered = set().union(*[info[n][1] for n in bodies]) if bodies else set()
    use = [r for r in refs if r.partition in covered]
    if bodies and not use:       # body shape without known partitions: decide by texture
        use = [r for r in refs if any(r.key[:4] in info[n][0].lower() or (r.key == "body" and "femalebody" in info[n][0].lower()) for n in bodies)][:1]
    rename = {r.shape: r.shape + "_old3BA" for r in use if r.shape in info}
    add_ube_refs(src, nif_path, [r.nif for r in use], rename)
    bodies = {rename.get(n, n) for n in bodies}
    ref_names = {r.shape for r in use}

    nif = SseNif(nif_path)
    shapes = [s for s in nif.shapes if s["name"] not in ref_names]
    pos = {s["block"]: nif.positions(s) for s in shapes}
    # where the game shows each point at rest (a ring made in its finger bone's space is stored around 0,0,0)
    gpos = {s["block"]: nif.to_global(s, pos[s["block"]]) for s in shapes}
    tex_of = {rename.get(n, n): t for n, (t, _p) in info.items()}
    parts_of = {rename.get(n, n): p for n, (_t, p) in info.items()}
    main = [s for s in shapes if s["name"] in bodies and "etc" not in tex_of.get(s["name"], "").lower()]
    stack = lambda lst: np.vstack(lst) if lst else np.zeros((0, 3))
    E = stack([gpos[s["block"]] for s in main])
    E_feet = stack([gpos[s["block"]] for s in main if 37 in parts_of.get(s["name"], set())])
    E_rest = stack([gpos[s["block"]] for s in main if 37 not in parts_of.get(s["name"], set())])

    # high heels: the outfit's feet stand on tiptoe -> use UBE feet with HiHeelz_CBBE baked in
    # (also for outfits without 3BA feet inside, e.g. leggings made for heels: judged by the outfit itself)
    feet = next(r for r in refs if r.key == "feet")
    feet_in = feet in use
    heel_dn = feet.sliders.get(HEEL, (None, None))[1]
    Vh, heel_fit = None, None
    if heel_dn and heel_dn in feet.osd:
        cand = feet.verts + feet.osd[heel_dn]
        probe = E_feet if len(E_feet) else stack(
            [gpos[s["block"]][gpos[s["block"]][:, 2] < 8] for s in shapes if s["name"] not in bodies])
        if len(probe) >= 30:
            dh = knn(cand, probe)[0][:, 0].mean()
            if dh < 0.5 * knn(feet.verts, probe)[0][:, 0].mean() and dh < 1.5:
                Vh = cand
    # Stockings, pantyhose, bodystockings (a piece that does not take the feet slot 37) are often made in a high-heel
    # pose. Barefoot - or in flat shoes - the game shows the flat skin feet, and the heel-posed foot part hangs
    # under them. Find the heel height that fits the piece and pull its foot part onto the flat UBE foot; the
    # HiHeelz slider is still transferred, so a heel morph can bring it back. Shoes and boots (slot 37) keep heels.
    flat = None
    if slots is not None and 37 not in slots and not len(E_feet) and heel_dn and heel_dn in feet.osd:
        P_low = stack([gpos[s["block"]][gpos[s["block"]][:, 2] < 8] for s in shapes if s["name"] not in bodies
                       and tex_of.get(s["name"]) and not re.match(r"(?i)(virtual|collision)", s["name"])])
        sole = feet.verts[:, 2].min()
        D = feet.osd[heel_dn]
        if len(P_low):                                  # only what wraps the foot itself (not a cape's hem, a
            near = np.minimum(knn(feet.verts, P_low)[0][:, 0], knn(feet.verts + D, P_low)[0][:, 0]) < 4.0
            P_low = P_low[near]                         # a skirt or a floor plane behind / around it)
        if len(P_low) >= 30 and (P_low[:, 2] < sole - 0.3).mean() > 0.15:
            d_flat = knn(feet.verts, P_low)[0][:, 0].mean()
            d_fit, h = min((knn(feet.verts + h * D, P_low)[0][:, 0].mean(), h) for h in np.linspace(0.25, 2.0, 15))
            if d_fit < 1.2 and d_fit < 0.6 * d_flat:     # it really is a foot in a heel pose
                Vfit = feet.verts + h * D
                tri, bary, _dist = ube_field.project(P_low, Vfit, feet.tris)
                flat = (P_low, ube_field.interp(feet.verts - Vfit, feet.tris, tri, bary), round(float(h), 2))
                Vh = None                               # anti-clip and sliders against the flat feet
    if flat is not None:
        field = ube_field.Field(ref, E_rest, "b", fixed=flat[:2], t3_exclude=ref["T3"][:, 2] < 16)
    elif Vh is not None and not len(E_feet):
        # no 3BA feet to map from: the 3BA heel foot is within ~0.3 of UBE's, so pin the foot area to UBE's heel foot
        field = ube_field.Field(ref, E_rest, "b", fixed=(Vh, np.zeros_like(Vh)), t3_exclude=ref["T3"][:, 2] < 16)
    elif Vh is not None:
        tri, bary, dist = ube_field.project(E_feet, Vh, feet.tris)
        q = ube_field.interp(Vh, feet.tris, tri, bary)
        heel_fit = round(float(dist.mean()), 3)
        field = ube_field.Field(ref, E_rest, "b", fixed=(E_feet, q - E_feet), t3_exclude=ref["T3"][:, 2] < 16)
    else:
        field = ube_field.Field(ref, E, "b")
    ref_verts = {r.shape: (Vh if Vh is not None and r is feet else r.verts) for r in use}

    # anti-clip surface: UBE body + feet (heel pose if any) + hands, outward face normals
    SV, SF, off = [], [], 0
    for r in refs:
        v = Vh if Vh is not None and r is feet else r.verts
        SV.append(v); SF.append(r.tris + off); off += len(v)
    SV, SF = np.vstack(SV), np.vstack(SF)
    SN = np.cross(SV[SF[:, 1]] - SV[SF[:, 0]], SV[SF[:, 2]] - SV[SF[:, 0]])
    SN /= np.linalg.norm(SN, axis=1, keepdims=True) + 1e-12
    pushed = 0
    conformed = {}
    for s in shapes:
        d = field(gpos[s["block"]])
        if flat is not None and re.search(r"(?i)ground", s["name"]) and not tex_of.get(s["name"]):
            d = np.zeros_like(d)                         # the SMP floor plane stays on the floor
        if s["name"] not in bodies:
            p = push_out(gpos[s["block"]] + d, SV, SF, SN)
            pushed += int((np.abs(p).sum(1) > 0).sum())
            d = d + p
        conformed[s["name"]] = gpos[s["block"]] + d
        nif.set_positions(s, pos[s["block"]] + nif.to_local_delta(s, d))
    if Vh is not None and feet_in:
        fs = next(s for s in nif.shapes if s["name"] == feet.shape)
        if not fs["skinned"]:
            raise ValueError("UBE feet shape is not skinned")
        nif.set_positions(fs, Vh)
    nif.save(nif_path)
    # bone weights: copy the UBE body/feet/hands weights onto the conformed outfit shapes
    with open(nif_path, "rb") as f:
        before_weights = f.read()
    # a shape its author tied 100% to one bone (a ring on a finger bone, an amulet on the neck...) is one solid piece:
    # it keeps that bone, or the skin weights would bend and stretch it with every finger move
    rigid = {rename.get(x.name, x.name) for x in src_nif.shapes if _one_bone(x)} - bodies
    if rigid:
        log(f"   weights: kept the author's one-bone weights on {', '.join(sorted(rigid))}")
    ube_weights.copy_weights(nif_path, [s["name"] for s in shapes if s["name"] not in bodies | rigid], refs,
                             [Vh if Vh is not None and r is feet else r.verts for r in refs], log=log)
    # HDT-SMP safety net: a bone the physics XML does not declare falls to the floor and drags the skeleton with it.
    # Whatever the weight copy did, the result may not have a falling bone the outfit's own source did not have.
    if smp_check.has_smp(nif_path):
        new = {(s, b) for s, b in smp_falling(nif_path, resolver) - smp_falling(src, resolver)
               if s not in ref_names}                # the added UBE body / feet / hands are zapped at build time
        if new:
            with open(nif_path, "wb") as f:
                f.write(before_weights)
            log(f"   weights: kept the author's weights (HDT-SMP: {len(new)} bone(s) would have fallen, e.g. "
                f"{sorted(b for _s, b in new)[0]})")
    # the 3BA outfit's own BODYTRI (its 3BA morph file) must not survive: BodySlide adds the UBE one after it and
    # RaceMenu / OBody would read the old one, so the outfit would never follow the body's preset (bodytri.py)
    bodytri.neutralize_source(nif_path)

    entries, zap_rows, hidden = [], [], {}
    for s in shapes:
        if s["name"] in bodies:
            idx = np.arange(s["nverts"])
            entries.append((s["name"] + ZAP, idx, np.tile([0.0, 1.0, 0.0], (len(idx), 1))))
            zap_rows.append((s["name"] + ZAP, s["name"]))
    Ec = E + field(E) if len(E) else E
    tris_of = {rename.get(x.name, x.name): np.array(x.tris, dtype=np.int64) for x in src_nif.shapes}
    for r in use:
        olds = [n for n in bodies if r.partition in parts_of.get(n, set()) and n in conformed]
        if r.key in ("feet", "hands") and olds:
            # keep only the UBE feet/hands that lie on the (conformed) surface the author kept
            Vs, Fs, off = [], [], 0
            for n in olds:
                Vs.append(conformed[n]); Fs.append(tris_of[n] + off); off += len(conformed[n])
            _t, _b, ds = ube_field.project(ref_verts[r.shape], np.vstack(Vs), np.vstack(Fs))
            hide = np.nonzero(ds > ZAP_SURFACE)[0]
        elif len(Ec):
            dist, _ = knn(Ec, ref_verts[r.shape])
            hide = keep_crotch(np.nonzero(dist[:, 0] > 1.2)[0], r)
        else:
            hide = np.arange(len(r.verts))
        hidden[r.shape] = (len(hide), len(r.verts))
        if len(hide):
            entries.append((r.shape + ZAP, hide, np.tile([0.0, 1.0, 0.0], (len(hide), 1))))
            zap_rows.append((r.shape + ZAP, r.shape))

    # sliders: union of body, feet, hands; transfer from all three parts
    sliders = OrderedDict()
    for r in refs:
        for name, (attrs, _dn) in r.sliders.items():
            sliders.setdefault(name, attrs)
    U = np.vstack([Vh if Vh is not None and r is feet else r.verts for r in refs])
    outfit = [s["name"] for s in shapes if s["name"] not in bodies]
    bones, BW, _stb, _node = ube_weights.ref_weights(refs)
    try:
        Wo = outfit_bones(nif_path, set(outfit), bones)
    except Exception as e:                       # never fail a conversion over this: plain nearest points
        log(f"   follow: bone weights not read ({e})")
        Wo = {}
    areas, UN = outfit_areas(refs, U, BW, bones)
    SVr, SFr, off = [], [], 0
    for r, Vr in zip(refs, np.split(U, np.cumsum([len(r.verts) for r in refs])[:-1])):
        SVr.append(Vr); SFr.append(r.tris + off); off += len(Vr)
    SVr, SFr = np.vstack(SVr), np.vstack(SFr)
    SNr = np.cross(SVr[SFr[:, 1]] - SVr[SFr[:, 0]], SVr[SFr[:, 2]] - SVr[SFr[:, 0]])
    SNr /= np.linalg.norm(SNr, axis=1, keepdims=True) + 1e-12

    def room(P):
        """Room each outfit point has from the UBE body at rest (half its gap; 0 inside or where unclear)."""
        tri, bary, dist = ube_field.project(P, SVr, SFr)
        q = ube_field.interp(SVr, SFr, tri, bary)
        dot = ((P - q) * SNr[tri]).sum(1)
        ok = (dot > 0) & (np.abs(dot) >= 0.6 * dist)
        return np.where(ok, np.maximum(dist - MIN_GAP, 0) * 0.5, 0.0)
    near = {n: Follow(U, conformed[n], BW, Wo.get(n), UN, room(conformed[n])) for n in outfit}
    for name, attrs in sliders.items():                 # first pass: where own-bone follow is safe (Follow.probe)
        if attrs.get("uv") == "true" or attrs.get("zap") == "true" or (Vh is not None and name == HEEL):
            continue
        parts = []
        for r in refs:
            dn = r.sliders.get(name, (None, None))[1]
            parts.append(r.osd[dn] if dn and dn in r.osd else np.zeros_like(r.verts))
        D = np.vstack(parts)
        if np.abs(D).max() > 0:
            for f in near.values():
                f.probe(D)
    for f in near.values():
        f.settle()
    own = sum(int((f.alpha > 0).sum()) for f in near.values())
    for name, _a in areas.items():
        sliders.setdefault(name, {"name": name, "invert": "false", "small": "0", "big": "0"})
    by_name = {s["name"]: s for s in shapes}

    def stored(n, diff):
        """Slider data is applied to the stored points: a skinned shape's moves in its skin space."""
        s = by_name[n]
        return nif.to_local_delta(s, diff) if s["skinned"] else diff
    data_for = {}
    for name, attrs in sliders.items():
        rows = []
        if Vh is not None and name == HEEL:   # already baked into the feet; the outfit is in heel pose
            data_for[name] = rows
            continue
        for r in use:
            if name in r.sliders and r.sliders[name][1]:
                rows.append((r.sliders[name][1], r.shape, r.folder + ".osd"))
        if name in areas and not any(name in r.sliders for r in refs):
            area, push = areas[name]
            for n in outfit:
                nn = near[n](UN)
                nn /= np.linalg.norm(nn, axis=1, keepdims=True) + 1e-12
                diff = push * near[n](area)[:, None] * nn
                keep = np.nonzero(np.abs(diff).max(1) > 1e-3)[0]
                if len(keep):
                    entries.append((n + name, keep, stored(n, diff[keep])))
                    rows.append((n + name, n, None))
        elif attrs.get("uv") != "true" and attrs.get("zap") != "true":
            parts = []
            for r in refs:
                dn = r.sliders.get(name, (None, None))[1]
                parts.append(r.osd[dn] if dn and dn in r.osd else np.zeros_like(r.verts))
            D = np.vstack(parts)
            if np.abs(D).max() > 0:
                for n in outfit:
                    diff = near[n](D)
                    mag = np.abs(diff).max(1)
                    keep = np.nonzero(mag > 1e-5)[0]
                    if len(keep) and mag.max() > 1e-3:
                        entries.append((n + name, keep, stored(n, diff[keep])))
                        rows.append((n + name, n, None))
        data_for[name] = rows
    write_osd(os.path.join(shape_dir, osd_name), entries)
    if os.path.isfile(os.path.join(shape_dir, osd_name + ".orig")):
        os.remove(os.path.join(shape_dir, osd_name + ".orig"))     # a "Fix clipping" copy of the old conversion

    out_dir, out_file = os.path.split(base)
    single = out_file.lower().endswith(".nif")          # single-weight mesh: BodySlide builds one file, no _0/_1
    if single:
        out_file = out_file[:-4]
    L = ['<?xml version="1.0" encoding="UTF-8"?>', '<SliderSetInfo version="1">',
         f'    <SliderSet name={quoteattr(set_name)}>',
         f'        <DataFolder>{escape(folder)}</DataFolder>',
         f'        <SourceFile>{escape(fname)}.nif</SourceFile>',
         f'        <OutputPath>{escape(chr(92).join(["meshes", "!UBE", out_dir]))}</OutputPath>',
         f'        <OutputFile GenWeights="{"false" if single else "true"}" PreventMorphFile="false" '
         f'KeepZappedShapes="false">{escape(out_file)}</OutputFile>']
    for r in use:
        L.append(f'        <Shape target={quoteattr(r.shape)} DataFolder={quoteattr(r.folder)} SmoothSeamNormalsAngle="120">{escape(r.shape)}</Shape>')
    for s in shapes:
        L.append(f'        <Shape target={quoteattr(s["name"])}>{escape(s["name"])}</Shape>')
    for name, attrs in sliders.items():
        rows = data_for.get(name, [])
        if not rows:
            continue
        a = " ".join(f"{k}={quoteattr(v)}" for k, v in attrs.items())
        L.append(f"        <Slider {a}>")
        for dn, tgt, ext in rows:
            if ext is None:
                L.append(f'            <Data name={quoteattr(dn)} target={quoteattr(tgt)} local="true">{escape(osd_name + chr(92) + dn)}</Data>')
            else:
                L.append(f'            <Data name={quoteattr(dn)} target={quoteattr(tgt)}>{escape(ext + chr(92) + dn)}</Data>')
        L.append("        </Slider>")
    if zap_rows:
        L.append(f'        <Slider name="{ZAP}" invert="false" small="100" big="100" zap="true" hidden="true">')
        for dn, tgt in zap_rows:
            L.append(f'            <Data name={quoteattr(dn)} target={quoteattr(tgt)} local="true">{escape(osd_name + chr(92) + dn)}</Data>')
        L.append("        </Slider>")
    L += ["    </SliderSet>", "</SliderSetInfo>", ""]
    os.makedirs(os.path.join(BS, "SliderSets"), exist_ok=True)
    with open(os.path.join(BS, "SliderSets", folder + ".osp"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    n_tr = sum(1 for rows in data_for.values() for r in rows if r[2] is None)
    fit = None if field.body_fit is None else round(float(field.body_fit.mean()), 3)
    log(f"== {set_name}: shapes {len(shapes)} (old body {sorted(bodies)}), UBE parts {[r.key for r in use]}, "
        f"hidden {hidden}, slider data {n_tr}, body fit {fit}, pushed out {pushed}, own-bone follow {own}"
        + (", PORTED from Skyrim LE to SE" if ported else "")
        + (f", FLAT FEET (heel-posed foot part pulled onto the flat foot, heel {flat[2]})" if flat is not None else "") + (f", HEELS (feet fit {heel_fit})" if Vh is not None and heel_fit is not None else ", HEELS (outfit pose)" if Vh is not None else ""))
    return set_name


def write_group(members, drop=()):
    path = os.path.join(BS, "SliderGroups", GROUP + ".xml")
    old = set()
    if os.path.exists(path):
        old = {m.get("name") for m in ET.parse(path).getroot().iter("Member")}
    allm = sorted((old | set(members)) - set(drop))
    L = ['<?xml version="1.0" encoding="UTF-8"?>', "<SliderGroups>"]
    for g in (GROUP, "UBE"):  # also join "UBE" so the user's UBE presets apply to these sets
        L.append(f"    <Group name={quoteattr(g)}>")
        L += [f"        <Member name={quoteattr(m)}/>" for m in allm]
        L.append("    </Group>")
    L += ["</SliderGroups>", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv):
    jobs = []   # (base, src or None)
    mode = None
    for a in argv:
        if a == "--proj":
            mode = a
        elif mode == "--proj":
            src, base = find_project(a)
            jobs.append((base, src))
        else:
            jobs.append((a, None))
    ref = ube_field.load_cache()
    refs = load_refs()
    resolver = Resolver()
    made, failed = [], []
    for base, src in jobs:
        try:
            made.append(make_project(base, src, ref, refs, resolver))
        except Exception as e:  # keep going; report at the end
            failed.append((base, repr(e)))
            print(f"!! {base}: {e!r}")
        write_group(made)
    print(f"done: {len(made)} projects, {len(failed)} failed")
    for b, e in failed:
        print("   failed:", b, e)


if __name__ == "__main__":
    main(sys.argv[1:])
