# UBE Tailor - Copyright (C) 2026 Desertravel. Licensed under the GNU GPL v3 or later (see LICENSE).
"""HDT-SMP safety check for converted outfits.

An SMP physics XML is read top to bottom. A bone that a <per-vertex-shape>/<per-triangle-shape> is skinned to
but that the XML never declared is created on the spot "with the current default setting". Outfit XMLs raise
the default mass before their cloth bones, so an undeclared bone becomes a free rigid body and falls to the
floor - dragging the real skeleton bone with it (head on the ground, legs melting into pillars).
The converter must therefore never add bones to shapes of a nif that carries an SMP XML.

  python smp_check.py [--filter TEXT]     scan the "UBE Auto" projects, list bones that would fall
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

MARK = b"HDT Skinned Mesh Physics Object"
SHAPES = ("per-vertex-shape", "per-triangle-shape")
CONSTRAINTS = ("generic-constraint", "stiffspring-constraint", "conetwist-constraint")


def xml_rel(nif_path):
    """meshes-relative path of the SMP XML a nif points at, or None."""
    with open(nif_path, "rb") as f:
        b = f.read()
    i = b.find(MARK)
    if i < 0:
        return None
    m = re.search(rb"[\x20-\x7e]{3,260}\.xml", b, re.I)
    if not m:
        return None
    rel = m.group(0).decode("cp1252").replace("/", "\\").lstrip("\\")
    return rel[7:] if rel.lower().startswith("meshes\\") else rel


def has_smp(nif_path):
    with open(nif_path, "rb") as f:
        return MARK in f.read()


def falling(xml_text, shape_bones):
    """[(shape, bone)] for bones that the XML would auto-create with mass and that no constraint holds."""
    try:
        root = ET.fromstring(re.sub(r"<\?xml[^>]*\?>", "", xml_text, count=1).strip())
    except ET.ParseError:
        return None
    default, templates = 0.0, {}
    mass, auto, held = {}, [], set()

    def own_mass(el, base):
        m = el.find("mass")
        try:
            return float(m.text) if m is not None and m.text else base
        except ValueError:
            return base

    def walk(parent):
        nonlocal default
        for el in parent:
            tag = el.tag
            if tag == "bone-default":
                base = templates.get(el.get("extends"), default)
                if el.get("name"):
                    templates[el.get("name")] = own_mass(el, base)
                else:
                    default = own_mass(el, base)
            elif tag == "bone":
                name = el.get("name")
                if name and name not in mass:
                    mass[name] = own_mass(el, templates.get(el.get("template"), default))
            elif tag in SHAPES:
                for b in shape_bones.get(el.get("name"), ()):
                    if b not in mass:
                        mass[b] = default
                        if default > 0:
                            auto.append((el.get("name"), b))
            elif tag in CONSTRAINTS:
                held.add(el.get("bodyA"))
                held.add(el.get("bodyB"))
            elif tag == "constraint-group":
                walk(el)

    walk(root)
    return [(s, b) for s, b in auto if b not in held]


def moving_bones(xml_text, shape_bones, body_bones=()):
    """Bones the physics moves away from the body: the XML gives them mass (declared, or created with the default
    mass when a shape is skinned to them undeclared) and the body is not skinned to them (skirt, frill, cape, tail
    bones; breast / butt bones the body jiggles on too do not count). None if the XML cannot be read."""
    body_bones = set(body_bones)
    try:
        root = ET.fromstring(re.sub(r"<\?xml[^>]*\?>", "", xml_text, count=1).strip())
    except ET.ParseError:
        return None
    default, templates, mass = 0.0, {}, {}

    def own_mass(el, base):
        m = el.find("mass")
        try:
            return float(m.text) if m is not None and m.text else base
        except ValueError:
            return base

    def walk(parent):
        nonlocal default
        for el in parent:
            if el.tag == "bone-default":
                base = templates.get(el.get("extends"), default)
                if el.get("name"):
                    templates[el.get("name")] = own_mass(el, base)
                else:
                    default = own_mass(el, base)
            elif el.tag == "bone" and el.get("name") and el.get("name") not in mass:
                mass[el.get("name")] = own_mass(el, templates.get(el.get("template"), default))
            elif el.tag in SHAPES:
                for b in shape_bones.get(el.get("name"), ()):
                    mass.setdefault(b, default)
            elif el.tag == "constraint-group":
                walk(el)

    walk(root)
    return {b for b, m in mass.items() if m > 0 and b not in body_bones}


def moving_bones_of(nif_path, resolver, body_shape=None):
    """The bones of a nif that its HDT-SMP XML moves away from the body shape (set() without SMP; None when it has
    SMP but the XML is not readable)."""
    rel = xml_rel(nif_path)
    if rel is None:
        return set()
    from nifly_env import NifFile
    kind, src = resolver.resolve(rel)
    if kind != "loose":
        return None
    with open(src, encoding="utf-8", errors="replace") as f:
        text = f.read()
    shapes = {s.name: list(s.bone_names) for s in NifFile(nif_path).shapes}
    return moving_bones(text, shapes, shapes.get(body_shape, ()))


def read_xml(nif_path, resolver):
    """Text of the nif's HDT-SMP XML, or None (no SMP, or the XML is packed / missing)."""
    rel = xml_rel(nif_path)
    if rel is None:
        return None
    kind, src = resolver.resolve(rel)
    if kind != "loose":
        import env                       # the XML may sit outside meshes (SKSE\Plugins\hdtSkinnedMeshConfigs\...)
        src = env.find(rel)
        if not src:
            return None
    with open(src, encoding="utf-8", errors="replace") as f:
        return f.read()


def shape_tags(xml_text):
    """{name: [tags]} of the <per-vertex-shape>/<per-triangle-shape> entries (empty when unreadable)."""
    try:
        root = ET.fromstring(re.sub(r"<\?xml[^>]*\?>", "", xml_text or "", count=1).strip())
    except ET.ParseError:
        return {}
    return {el.get("name"): [(t.text or "").strip() for t in el.findall("tag")]
            for el in root.iter() if el.tag in SHAPES and el.get("name")}


def check_nif(nif_path, resolver):
    """None = no SMP; else (xml rel path, [(shape, bone)] or None if the XML is missing/unreadable)."""
    rel = xml_rel(nif_path)
    if rel is None:
        return None
    from nifly_env import NifFile
    kind, src = resolver.resolve(rel)
    if kind != "loose":
        return rel, None
    with open(src, encoding="utf-8", errors="replace") as f:
        text = f.read()
    nif = NifFile(nif_path)
    return rel, falling(text, {s.name: list(s.bone_names) for s in nif.shapes})


def main():
    import glob
    import make_projects
    import resolve_mesh
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    flt = sys.argv[sys.argv.index("--filter") + 1].lower() if "--filter" in sys.argv else ""
    base = os.path.join(make_projects.BS, "ShapeData")
    res = resolve_mesh.Resolver()
    smp = bad = unknown = 0
    for d in sorted(glob.glob(os.path.join(base, "UBE Auto - *"))):
        if flt not in d.lower():
            continue
        for nif in glob.glob(os.path.join(d, "*.nif")):
            r = check_nif(nif, res)
            if r is None:
                continue
            smp += 1
            if r[1] is None:
                unknown += 1
                print(f"?? {os.path.basename(d)}: XML not readable ({r[0]})")
            elif r[1]:
                bad += 1
                bones = sorted({b for _s, b in r[1]})
                print(f"!! {os.path.basename(d)}: {len(bones)} bone(s) fall: {', '.join(bones)}")
    print(f"SMP projects {smp}, with falling bones {bad}, XML not readable {unknown}")


if __name__ == "__main__":
    main()
