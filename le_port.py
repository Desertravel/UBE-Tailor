# UBE Tailor - Copyright (C) 2026 Desertravel. Licensed under the GNU GPL v3 or later (see LICENSE).
"""Port a Skyrim LE (Oldrim) mesh to Skyrim SE, so the Tailor can convert outfits that were never ported.

The LE mesh is read with PyNifly and every shape is written again into a new SE nif: vertices, triangles, UVs,
normals, the shape transform, the skin (bones, global-to-skin and skin-to-bone transforms, weights), the
dismember partitions, the shader (with all its textures) and the alpha property, plus the string extra data of
the root (BODYTRI, the HDT-SMP physics XML path). This is what Outfit Studio's "Optimize for SSE" does for an
outfit; collision and animation blocks are not copied (outfit meshes do not use them).

  python le_port.py <LE nif> <SE nif out>
"""
import os
import sys

from nifly_env import NifFile


def is_le(path):
    """True if the nif is not in Skyrim SE format (the Tailor's own SE reader refuses it)."""
    from nif_patch import SseNif
    try:
        SseNif(path)
        return False
    except ValueError as e:
        return "not Skyrim SE" in str(e)


def port(src, dst, game="SKYRIMSE"):
    """Write src again as a `game` nif to dst (also usable the other way, for tests). Returns the shape count."""
    old = NifFile(src)
    new = NifFile()
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    new.initialize(game, dst)
    n = 0
    for s in old.shapes:
        ns = new.createShapeFromData(s.name, s.verts, s.tris, s.uvs, s.normals)
        ns.transform = s.transform
        if s.bone_names:
            ns.skin()
            ns.set_global_to_skin(s.global_to_skin)
            for b in s.bone_names:                           # all bones first: adding one resets the others
                node = old.nodes.get(b)
                ns.add_bone(b, node.global_transform if node is not None else None)
            for b in s.bone_names:
                ns.set_skin_to_bone_xform(b, s.get_shape_skin_to_bone(b))
                ns.setShapeWeights(b, s.bone_weights.get(b, []))
            parts = s.partitions
            if parts:
                ns.set_partitions(parts, s.partition_tris)
        if s.shader is not None and s.shader.properties is not None:
            ns.shader.name = s.shader.name
            ns.shader._properties = s.shader.properties.copy()
            ns.save_shader_attributes()
            for slot, tex in (s.textures or {}).items():
                if tex:
                    ns.set_texture(slot, tex)
        if s.has_alpha_property:
            ns.has_alpha_property = True
            ns.alpha_property.properties.flags = s.alpha_property.properties.flags
            ns.alpha_property.properties.threshold = s.alpha_property.properties.threshold
            ns.save_alpha_property()
        n += 1
    from io_scene_nifly.pyn.pynifly import NiStringExtraData
    for ed in old.root.extra_data("NiStringExtraData") or []:
        NiStringExtraData.New(new, name=ed.name, string_value=ed.string_data, parent=new.root)
    new.save()
    return n


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    print("shapes:", port(sys.argv[1], sys.argv[2]))
