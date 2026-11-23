# UBE Tailor - Copyright (C) 2026 Desertravel. Licensed under the GNU GPL v3 or later (see LICENSE).
"""HDT-SMP body collision for converted outfits.

Skirts, capes and coat tails that HDT-SMP moves only stay out of the body when the physics has a body to collide
with. 3BA modpacks often have none (CBBE 3BA installed as "CBPC only", or the 3BA SMP collision object never built),
so the cloth swung straight into the - fuller - UBE body. Each converted outfit with an SMP XML gets its own:

  * an invisible, light copy of the UBE body (about 2,400 points, a little inside the skin) in the outfit nif, with
    the UBE body's sliders (it follows the preset) and plain skeleton bones only (no physics bones);
  * a copy of the outfit's XML that names it as a still collision body (mass 0) at the very top, before any
    bone-default gives mass, plus that body's tag in the "can-collide-with" lists of the cloth that has one;
  * the nif points at that copy (meshes\\!UBE\\...\\<piece>.ube.xml in the Tailor's output mod).

The new XML is only used when smp_check finds no bone that would fall with it that did not fall before.
"""
import os
import re
import xml.etree.ElementTree as ET

import numpy as np

import smp_check

PROXY = "UBETailor_SMPBody"
TAG = "UBETailorBody"
CELL = 2.0            # clustering cell (game units): about 2,400 points for the UBE body
INSET = 0.4           # the collision body sits this far inside the skin...
MARGIN = 0.3          # ...and collides this far around it
KEEP = re.compile(r"^NPC (Pelvis|Spine[12]?|Neck|[LR] (Thigh|Calf|Foot|Clavicle|UpperArm|Forearm|Hand)) \[", re.I)
_CACHE = {}


def _normals(V, F):
    N = np.zeros_like(V)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    return N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)


def proxy_of(body):
    """(index of the UBE body point behind each proxy point, proxy triangles, proxy points at rest, {bone: [(i, w)]})
    for the UBE body reference (make_projects.Ref). Cached per body nif."""
    if body.nif in _CACHE:
        return _CACHE[body.nif]
    from nifly_env import NifFile
    V, F = body.verts, body.tris
    cell = np.floor(V / CELL).astype(np.int64)
    _u, cid = np.unique(cell, axis=0, return_inverse=True)
    cid = cid.reshape(-1)
    k = cid.max() + 1
    cen = np.zeros((k, 3))
    np.add.at(cen, cid, V)
    cen /= np.bincount(cid, minlength=k)[:, None]
    d = np.linalg.norm(V - cen[cid], axis=1)
    rep = np.full(k, -1)
    for i in np.argsort(d):                         # the body point nearest its cell's centre stands for the cell
        if rep[cid[i]] < 0:
            rep[cid[i]] = i
    # keep the winding of a source triangle: rebuild each from a body triangle that maps onto it
    seen, tris = set(), []
    for f in cid[F]:
        key = tuple(sorted(f))
        if len(set(f)) == 3 and key not in seen:
            seen.add(key)
            tris.append(f)
    tris = np.array(tris, dtype=np.int64)
    N = _normals(V, F)
    P = V[rep] - INSET * N[rep]
    # clustering cuts across hollows (under the breasts, the groin, the armpits): there the light body would stand
    # out of the skin and push cloth that rests there. Pull such points in until the collision surface (with its
    # margin) stays under the skin.
    import ube_field
    FN = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    FN /= np.linalg.norm(FN, axis=1, keepdims=True) + 1e-12
    for _ in range(4):
        S = np.vstack([P[tris].mean(1)] + [(P[tris[:, a]] + P[tris[:, b]]) / 2 for a, b in ((0, 1), (1, 2), (0, 2))])
        owner = np.concatenate([np.arange(len(tris))] * 4)
        tri, bary, dist = ube_field.project(S, V, F)
        q = ube_field.interp(V, F, tri, bary)
        out = np.sign(((S - q) * FN[tri]).sum(1)) * dist + MARGIN
        bad = out > 0
        if not bad.any():
            break
        push = np.zeros(len(P))
        for k in range(3):
            np.maximum.at(push, tris[owner[bad], k], out[bad])
        P -= (push + 0.05 * (push > 0))[:, None] * N[rep]
    # weights: the UBE body's, folded onto plain skeleton bones (physics bones would be created by the outfit XML)
    ube = NifFile(body.nif)
    shape = ube.shapes[0]
    parent = {}
    for name, node in ube.nodes.items():
        parent[name] = node.parent.name if node.parent is not None else None

    def keep_of(bone):
        b = bone
        while b is not None and not KEEP.match(b):
            b = parent.get(b)
        return b
    W = {}
    for bone, pairs in shape.bone_weights.items():
        kb = keep_of(bone)
        if kb is None:
            continue
        for i, w in pairs:
            W.setdefault(int(i), {}).setdefault(kb, 0.0)
            W[int(i)][kb] += w
    weights = {}
    for j, i in enumerate(rep):
        ws = sorted(W.get(int(i), {"NPC Pelvis [Pelv]": 1.0}).items(), key=lambda x: -x[1])[:4]
        tot = sum(w for _b, w in ws) or 1.0
        for b, w in ws:
            weights.setdefault(b, []).append((j, w / tot))
    _CACHE[body.nif] = (rep, tris, P, weights, ube)
    return _CACHE[body.nif]


def proxy_bones(body):
    return sorted(proxy_of(body)[3])


def new_xml(text, bones):
    """The outfit's XML with the collision body added, or None when it cannot be read or would let a bone fall."""
    if not text or PROXY in text:
        return None
    m = re.search(r"<system\b[^>]*>", text)
    if not m:
        return None
    block = (f"\n\t<!-- UBE Tailor: the UBE body, for the cloth to collide with -->\n"
             f"\t<per-triangle-shape name=\"{PROXY}\">\n\t\t<margin>{MARGIN}</margin>\n"
             f"\t\t<penetration>1</penetration>\n\t\t<tag>{TAG}</tag>\n"
             f"\t\t<no-collide-with-tag>{TAG}</no-collide-with-tag>\n\t</per-triangle-shape>\n")
    out = text[:m.end()] + block + text[m.end():]

    def add_tag(mm):
        body = mm.group(0)
        if "<can-collide-with-tag>" not in body:
            return body
        close = body.rfind("</")
        return body[:close] + f"\t<can-collide-with-tag>{TAG}</can-collide-with-tag>\n\t" + body[close:]
    out = re.sub(r"<per-(?:vertex|triangle)-shape\b(?:(?!</per-).)*</per-(?:vertex|triangle)-shape>", add_tag, out,
                 flags=re.S)
    try:
        ET.fromstring(re.sub(r"<\?xml[^>]*\?>", "", out, count=1).strip())
    except ET.ParseError:
        return None
    return out


def safe(old_text, new_text, shape_bones, bones):
    """True when the new XML lets no bone fall that the old one did not (smp_check.falling), and leaves every bone the
    old XML moved as it was (the collision body is declared first: a physics bone it shared would turn still)."""
    before = smp_check.falling(old_text, shape_bones)
    after = smp_check.falling(new_text, {**shape_bones, PROXY: bones})
    if before is None or after is None or set(after) - set(before):
        return False
    moving = smp_check.moving_bones(old_text, shape_bones) or set()
    return not (moving & set(bones))


def add_proxy(nif_path, body, xml_rel):
    """Add the collision body shape (skinned, invisible once unshaded) to the outfit nif and point its HDT-SMP extra
    data at xml_rel. Before the byte-level edits of make_projects. The nif is only written once the XML path is known to
    be replaceable."""
    from nif_patch import replace_xml_string
    from nifly_env import NifFile
    from ube_project import _copy_struct
    if not replace_xml_string(nif_path, xml_rel, dry=True):
        raise ValueError("the nif's HDT-SMP XML path was not found")
    rep, tris, P, weights, ube = proxy_of(body)
    b = ube.shapes[0]
    nif = NifFile(nif_path)
    uv = np.array(b.uvs, dtype=np.float64)[rep] if len(b.uvs) else np.zeros((len(rep), 2))
    nrm = _normals(P, tris)
    tup = lambda A: [tuple(x) for x in A.tolist()]
    new = nif.createShapeFromData(PROXY, tup(P), tup(tris), tup(uv), tup(nrm),
                                  props=_copy_struct(b.properties), parent=nif.rootNode)
    new.skin()
    new.set_global_to_skin(b.global_to_skin)
    for bone in sorted(weights):
        node = ube.nodes.get(bone)
        par = node.parent.name if node is not None and node.parent is not None else None
        new.add_bone(bone, node.transform if node is not None else None,
                     par if par and par != ube.rootNode.name else None)
    for bone in sorted(weights):
        new.set_skin_to_bone_xform(bone, b.get_shape_skin_to_bone(bone))
        new.setShapeWeights(bone, weights[bone])
    nif.save()
    if not replace_xml_string(nif_path, xml_rel):
        raise ValueError("the nif's HDT-SMP XML path was not found")


def slider_entries(body):
    """[(slider name, (osd entry name, point indices, moves))] for the collision body: the UBE body's own slider data
    at the points it keeps."""
    rep = proxy_of(body)[0]
    out = []
    for name, (attrs, dn) in body.sliders.items():
        if attrs.get("zap") == "true" or attrs.get("uv") == "true" or not dn or dn not in body.osd:
            continue
        D = body.osd[dn][rep]
        keep = np.nonzero(np.abs(D).max(1) > 1e-5)[0]
        if len(keep):
            out.append((name, (PROXY + name, keep, D[keep])))
    return out


def xml_out(base):
    """meshes-relative path of an outfit's own XML copy (inside the Tailor's output mod)."""
    return os.path.join("!UBE", os.path.dirname(base), os.path.basename(base) + ".ube.xml")
