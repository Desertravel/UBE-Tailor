# UBE Tailor - Copyright (C) 2026 Desertravel. Licensed under the GNU GPL v3 or later (see LICENSE).
"""Minimal Skyrim SE (NIF 20.2.0.7, BS version 100) reader/patcher for BSTriShape vertex positions.

Only vertex xyz (and the shape bounding sphere) are rewritten, in place, same byte length, so every
other block -- skinning, partitions, shaders, HDT-SMP extra data, physics bones -- stays byte-identical.
For skinned SSE shapes the vertex data lives in NiSkinPartition, so that copy is patched too.
"""
import struct

import numpy as np

VF_FULLPREC = 0x400


def near_identity(t, R, s):
    """A skin transform that moves no point by more than about 0.01 units (rounding noise of the exporter, seen on
    many armors): treated as none, so those pieces convert exactly as before."""
    return (np.abs(np.asarray(t)).max() < 0.01 and np.abs(np.asarray(R) - np.eye(3)).max() < 1e-4
            and abs(s - 1) < 1e-4)


def replace_xml_string(path, new, dry=False):
    """Point a nif's HDT-SMP XML path (the one header string ending in .xml) at `new`. Blocks name strings by index,
    so only the header string table changes length; every block stays byte-identical. False when the nif has no such
    string, or more than one. dry: only tell whether it could."""
    with open(path, "rb") as f:
        b = bytearray(f.read())
    p = b.index(b"\n") + 1
    _ver, _e, _u, nblocks = struct.unpack_from("<IBII", b, p); p += 13
    p += 4                                           # BS version
    for _ in range(3):
        p += 1 + b[p]
    (ntypes,) = struct.unpack_from("<H", b, p); p += 2
    for _ in range(ntypes):
        (n,) = struct.unpack_from("<I", b, p); p += 4 + n
    p += 2 * nblocks + 4 * nblocks
    nstr_ofs = p
    nstr, maxlen = struct.unpack_from("<II", b, p); p += 8
    hits = []
    for _ in range(nstr):
        (n,) = struct.unpack_from("<I", b, p)
        if bytes(b[p + 4:p + 4 + n]).lower().endswith(b".xml"):
            hits.append((p, n))
        p += 4 + n
    if len(hits) != 1:
        return False
    if dry:
        return True
    q, n = hits[0]
    raw = new.encode("cp1252")
    b[q:q + 4 + n] = struct.pack("<I", len(raw)) + raw
    struct.pack_into("<I", b, nstr_ofs + 4, max(maxlen, len(raw)))
    with open(path, "wb") as f:
        f.write(b)
    return True


class SseNif:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.buf = bytearray(f.read())
        self._parse_header()
        self.shapes = [s for s in (self._parse_shape(i) for i, t in enumerate(self.block_types) if t == "BSTriShape") if s]

    # ---------------------------------------------------------------- header
    def _parse_header(self):
        b = self.buf
        p = b.index(b"\n") + 1
        ver, _endian, _uver, nblocks = struct.unpack_from("<IBII", b, p); p += 13
        if ver != 0x14020007:
            raise ValueError("not a NIF 20.2.0.7 file")
        (self.bsver,) = struct.unpack_from("<I", b, p); p += 4
        if self.bsver != 100:
            raise ValueError(f"not Skyrim SE (BS version {self.bsver})")
        for _ in range(3):  # author, process script, export script (ExportString: u8 len incl. NUL)
            p += 1 + b[p]
        (ntypes,) = struct.unpack_from("<H", b, p); p += 2
        types = []
        for _ in range(ntypes):
            (n,) = struct.unpack_from("<I", b, p); p += 4
            types.append(b[p:p + n].decode("ascii")); p += n
        idx = struct.unpack_from(f"<{nblocks}H", b, p); p += 2 * nblocks
        self.block_types = [types[i & 0x7FFF] for i in idx]
        sizes = struct.unpack_from(f"<{nblocks}I", b, p); p += 4 * nblocks
        nstr, _maxlen = struct.unpack_from("<II", b, p); p += 8
        self.strings = []
        for _ in range(nstr):
            (n,) = struct.unpack_from("<I", b, p); p += 4
            self.strings.append(b[p:p + n].decode("cp1252", "replace")); p += n
        (ngroups,) = struct.unpack_from("<I", b, p); p += 4 + 4 * ngroups
        self.block_ofs = []
        for s in sizes:
            self.block_ofs.append(p); p += s
        self.block_sizes = list(sizes)

    # ---------------------------------------------------------------- shapes
    @staticmethod
    def _layout(desc):
        # Skyrim SE (BSVertexDataSSE) always stores positions as full floats, whatever VF_FULLPREC says
        vsize = (desc & 0xF) * 4
        return vsize, True

    def _parse_shape(self, bi):
        b, p = self.buf, self.block_ofs[bi]
        (name_i,) = struct.unpack_from("<i", b, p); p += 4
        (nextra,) = struct.unpack_from("<I", b, p); p += 4 + 4 * nextra
        p += 4  # controller
        p += 4  # flags
        xf_ofs = p
        t = np.array(struct.unpack_from("<3f", b, p)); p += 12
        r = np.array(struct.unpack_from("<9f", b, p)).reshape(3, 3); p += 36
        (scale,) = struct.unpack_from("<f", b, p); p += 4
        p += 4  # collision object
        bound_ofs = p; p += 16
        skin, _shader, _alpha = struct.unpack_from("<3i", b, p); p += 12
        (desc,) = struct.unpack_from("<Q", b, p); p += 8
        ntris, nverts = struct.unpack_from("<HH", b, p); p += 4
        (dsize,) = struct.unpack_from("<I", b, p); p += 4
        vsize, full = self._layout(desc)
        copies = []
        if dsize > 0:
            copies.append((p, vsize, full))
        if skin >= 0:
            part = self._skin_partition(skin)
            if part is not None:
                q, pvsize, pfull, pcount = part
                copies.append((q, pvsize, pfull))
                if nverts == 0:          # skinned SSE shapes keep the counts in the partition
                    nverts = pcount
                elif nverts != pcount:
                    raise ValueError(f"vertex count mismatch in block {bi}")
        if not copies:
            return None
        name = self.strings[name_i] if 0 <= name_i < len(self.strings) else f"block{bi}"
        return {"block": bi, "name": name, "nverts": nverts, "copies": copies, "bound_ofs": bound_ofs,
                "skinned": skin >= 0, "skin_xf": self._skin_xf(skin) if skin >= 0 else None,
                "xf": (t, r, scale), "xf_ofs": xf_ofs, "props_ofs": bound_ofs + 16 + 4}

    def _skin_xf(self, skin_bi):
        """(t, R, scale) of NiSkinData's skin transform (global -> skin space), or None. A skinned shape's points are
        in that space: skin = scale * R @ global + t. Usually identity; rings and other pieces made in the space of
        their bone (vanilla style) have the bone's offset here."""
        if self.block_types[skin_bi] not in ("NiSkinInstance", "BSDismemberSkinInstance"):
            return None
        (data_bi,) = struct.unpack_from("<i", self.buf, self.block_ofs[skin_bi])
        if data_bi < 0 or self.block_types[data_bi] != "NiSkinData":
            return None
        f = struct.unpack_from("<13f", self.buf, self.block_ofs[data_bi])
        R, t, s = np.array(f[:9]).reshape(3, 3), np.array(f[9:12]), f[12] or 1.0
        if near_identity(t, R, s):
            return None
        return t, R, s

    def _skin_partition(self, skin_bi):
        if self.block_types[skin_bi] not in ("NiSkinInstance", "BSDismemberSkinInstance"):
            return None
        p = self.block_ofs[skin_bi]
        _data, part_bi = struct.unpack_from("<ii", self.buf, p)
        if part_bi < 0 or self.block_types[part_bi] != "NiSkinPartition":
            return None
        q = self.block_ofs[part_bi]
        _nparts, dsize, vsize = struct.unpack_from("<III", self.buf, q); q += 12
        (desc,) = struct.unpack_from("<Q", self.buf, q); q += 8
        if dsize == 0:
            return None
        _vs, full = self._layout(desc)
        return (q, vsize, full, dsize // vsize)

    # ---------------------------------------------------------------- access
    def positions(self, shape):
        """Vertex positions in shape-local space, from the first data copy."""
        ofs, vsize, full = shape["copies"][0]
        n = shape["nverts"]
        fmt = "<3f" if full else "<3e"
        return np.array([struct.unpack_from(fmt, self.buf, ofs + i * vsize) for i in range(n)], dtype=np.float64)

    def set_positions(self, shape, pos):
        pos = np.asarray(pos, dtype=np.float64)
        assert pos.shape == (shape["nverts"], 3)
        for ofs, vsize, full in shape["copies"]:
            fmt = "<3f" if full else "<3e"
            for i, v in enumerate(pos):
                struct.pack_into(fmt, self.buf, ofs + i * vsize, *v)
        lo, hi = pos.min(0), pos.max(0)
        c = (lo + hi) / 2
        rad = float(np.linalg.norm(pos - c, axis=1).max())
        struct.pack_into("<4f", self.buf, shape["bound_ofs"], *c, rad)

    def unshade(self, shape):
        """Drop the shape's shader and alpha property: the game then never draws it, while HDT-SMP still uses its
        points (that is how SMP collision proxies are made). The old property blocks stay, unreferenced."""
        struct.pack_into("<2i", self.buf, shape["props_ofs"], -1, -1)

    def to_global(self, shape, local):
        """Points of the shape where the game shows them at rest: skinned shapes through their skin transform,
        others through the shape's own transform."""
        if shape["skinned"]:
            if shape["skin_xf"] is None:
                return local
            t, r, s = shape["skin_xf"]
            return ((local - t) / s) @ r
        t, r, s = shape["xf"]
        return local @ (r.T * s) + t

    def to_local_delta(self, shape, delta):
        """A move in global space as the same move of the shape's stored points (and of BodySlide slider data)."""
        if shape["skinned"]:
            if shape["skin_xf"] is None:
                return delta
            _t, r, s = shape["skin_xf"]
            return s * delta @ r.T
        _t, r, s = shape["xf"]
        return delta @ np.linalg.inv(r.T * s)

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.buf)
