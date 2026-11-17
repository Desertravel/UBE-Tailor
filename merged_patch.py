# UBE Tailor - Copyright (C) 2026 Desertravel. Licensed under the GNU GPL v3 or later (see LICENSE).
"""One merged UBE patch for every outfit mod the Tailor patches: "UBE Tailor.esp" (then "UBE Tailor 2.esp", ...
when a file would pass MAX_MASTERS masters or 2048 new records, the ESL limit).

The file is rebuilt from the source plugins every time, so it always matches what is installed. Per outfit mod:
  * a UBE copy of each armor addon: race = UBE, body slot 32 also gets slot 53, model = the converted
    meshes\\!UBE mesh once one exists (same rule as repoint_armas.py);
  * an override of the armor that lists those copies first, so UBE races pick them.
Every form id copied from a source plugin is renumbered to the merged file's master list.
Which mods are in it, and the object ids of the copies (kept the same between rebuilds), live in
the work folder (tailor_patch.json).
"""
import json
import os
import re
import shutil
import struct

import make_projects as mp
import repoint_armas
import tailor_core as tc
import env
from plugin_lib import enabled_plugins, plugin_locations, read_plugin, subrecords, zstr

BASE = "UBE Tailor"
STATE = os.path.join(env.WORK, "tailor_patch.json") if env.WORK else None
MAX_MASTERS = 250                      # the game allows 254 (ESL masters count too); keep a margin
FIRST_ID, LAST_ID = 0x800, 0xFFF       # ESL object id range
HEDR_VERSION = 1.70                    # 1.70, not 1.71: SE 1.5.97 needs 1.70 (1.71 is only for AE 1.6.1130+);
                                       # 1.71 is only needed for ESL ids below 0x800, and we never use those
LOCALIZED = 0x80
FILE_RX = re.compile(r"^UBE Tailor( \d+)?\.esp$", re.I)

ARMA_FIDS = {b"NAM0", b"NAM1", b"NAM2", b"NAM3", b"SNDD", b"ONAM"}
ARMO_FIDS = {b"EITM", b"YNAM", b"ZNAM", b"ETYP", b"BIDS", b"BAMT", b"RNAM", b"TNAM", b"MODL"}
ALT_TEX = {b"MO2S", b"MO3S", b"MO4S", b"MO5S", b"DMDS"}


def file_name(i):
    return f"{BASE}.esp" if i == 0 else f"{BASE} {i + 1}.esp"


def merged_files():
    if not os.path.isdir(mp.MOD):
        return []
    return sorted(f for f in os.listdir(mp.MOD) if FILE_RX.match(f))


def ensure_plugin():
    """Make the output mod and an empty UBE Tailor.esp when there is none yet, so MO2 lists both from the first
    start: the user ticks them once (F5 in MO2), the Tailor fills the plugin when outfits are converted.
    True if it made them now."""
    if merged_files():
        return False
    os.makedirs(mp.MOD, exist_ok=True)
    tes4 = tc._sub(b"HEDR", struct.pack("<fiI", HEDR_VERSION, 0, FIRST_ID))
    tes4 += tc._sub(b"CNAM", b"UBE Tailor\0")
    tes4 += tc._sub(b"SNAM", b"UBE versions of outfits, made by UBE Tailor (by Desertravel). Empty until outfits "
                             b"are converted; the tool rebuilds this file.\0")
    with open(os.path.join(mp.MOD, "UBE Tailor.esp"), "wb") as f:
        f.write(struct.pack("<4sIIIIHH", b"TES4", len(tes4), 0x200, 0, 0, 44, 0) + tes4)
    return True


def mo2_status():
    """What MO2 must have for the game and BodySlide to see the Tailor's work: {mod: output mod enabled,
    unticked: merged files not ticked, files: merged files, mo2: MO2 is running}."""
    files = merged_files()
    on = {p.lower() for p in enabled_plugins()}
    return {"mod": env.output_mod_enabled(), "unticked": [f for f in files if f.lower() not in on], "files": files,
            "mo2": env.mo2_running()}


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    st.setdefault("plugins", [])
    st.setdefault("foreign", [])         # other UBE patches whose armor addons we override (built mesh)
    st.setdefault("ids", {})
    return st


def save_state(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, STATE)


def tes4_info(path):
    """(record flags, CNAM author, masters) of a plugin's header."""
    with open(path, "rb") as f:
        hdr = f.read(24)
        data = f.read(struct.unpack_from("<I", hdr, 4)[0])
    flags = struct.unpack_from("<I", hdr, 8)[0]
    cnam = next((zstr(x) for t, x in subrecords(data) if t == b"CNAM"), "")
    return flags, cnam, [zstr(x) for t, x in subrecords(data) if t == b"MAST"]


def load_order():
    """{plugin name lower: position} from the profile's load order."""
    pos = {}
    for name in env.load_order():
        pos.setdefault(name, len(pos))
    return pos


def undone_by_later():
    """{plugin: armors} - enabled plugins loading after a UBE Tailor file that override armors of the patch without
    its UBE armor addons, so UBE characters see nothing of them. A load order sorter (LOOT, MO2's Sort) put a
    Synthesis patch between the Tailor's files and 561 armors went invisible. Only plugins below the first of our
    files are read, so this is quick."""
    files = {f.lower() for f in merged_files()}
    lo = load_order()
    mine_pos = [lo[f] for f in files if f in lo]
    if not mine_pos:
        return {}
    loc = plugin_locations()
    on = {p.lower() for p in enabled_plugins()}

    def armors(low):
        try:
            ms, recs = read_plugin(loc[low], {b"ARMO"})
        except (OSError, ValueError, struct.error, KeyError):
            return {}
        ml = [m.lower() for m in ms]
        out = {}
        for sig, fid, d, _fl in recs:
            i = fid >> 24
            mods = set()
            for t, x in subrecords(d):
                if t == b"MODL" and len(x) == 4:
                    f = struct.unpack("<I", x)[0]
                    mods.add(((ml[f >> 24] if f >> 24 < len(ml) else low), f & 0xFFFFFF))
            out[((ml[i] if i < len(ml) else low), fid & 0xFFFFFF)] = mods
        return out
    mine = {}                                   # armor -> (position of our last file with it, our UBE addons)
    for f in sorted(files, key=lambda x: lo.get(x, -1)):
        if f in lo and f in loc:
            for k, mods in armors(f).items():
                mine[k] = (lo[f], {m for m in mods if m[0] in files})
    last = {}                                   # armor -> (position, plugin, addons) of the last plugin after ours
    for p in sorted((p for p in on if p not in files and lo.get(p, -1) > min(mine_pos) and p in loc), key=lo.get):
        for k, mods in armors(p).items():
            if k in mine and lo[p] > mine[k][0]:
                last[k] = (lo[p], p, mods)
    out = {}
    for k, (_pos, p, mods) in last.items():
        if mine[k][1] and not mine[k][1] & mods:
            out[p] = out.get(p, 0) + 1
    return out


# ---------------------------------------------------------------- form id renumbering
def remapper(ms, name, index):
    def R(fid):
        if fid == 0:
            return 0
        i = fid >> 24
        src = ms[i] if i < len(ms) else name
        return index[src.lower()] << 24 | fid & 0xFFFFFF
    return R


def _u32(x, R):
    return struct.pack("<I", R(struct.unpack("<I", x)[0]))


def remap_array(x, R):
    return b"".join(_u32(x[i:i + 4], R) for i in range(0, len(x) - len(x) % 4, 4)) + x[len(x) - len(x) % 4:]


def remap_alt(x, R):
    """Alternate textures: count, then per entry name (u32 len + chars), TXST form id, index."""
    b = bytearray(x)
    n, i = struct.unpack_from("<I", b, 0)[0], 4
    for _ in range(n):
        i += 4 + struct.unpack_from("<I", b, i)[0]
        struct.pack_into("<I", b, i, R(struct.unpack_from("<I", b, i)[0]))
        i += 8
    if i != len(b):
        raise ValueError("unexpected alternate texture data")
    return bytes(b)


def remap_dstd(x, R):
    b = bytearray(x)
    if len(b) >= 16:
        for off in (8, 12):                    # explosion, debris
            struct.pack_into("<I", b, off, R(struct.unpack_from("<I", b, off)[0]))
    return bytes(b)


def remap_vmad(x, R):
    """Script data: renumber object properties (single and arrays)."""
    b = bytearray(x)
    ver, fmt, count = struct.unpack_from("<hhH", b, 0)
    i = 6

    def wstr(i):
        return i + 2 + struct.unpack_from("<H", b, i)[0]

    def obj(i):
        off = i + 4 if fmt == 2 else i
        struct.pack_into("<I", b, off, R(struct.unpack_from("<I", b, off)[0]))
        return i + 8

    for _ in range(count):
        i = wstr(i)
        if ver >= 4:
            i += 1
        props = struct.unpack_from("<H", b, i)[0]
        i += 2
        for _ in range(props):
            i = wstr(i)
            typ = b[i]
            i += 2 if ver >= 4 else 1
            if typ == 1:
                i = obj(i)
            elif typ == 2:
                i = wstr(i)
            elif typ in (3, 4):
                i += 4
            elif typ == 5:
                i += 1
            elif typ in (11, 12, 13, 14, 15):
                n = struct.unpack_from("<I", b, i)[0]
                i += 4
                for _ in range(n):
                    i = obj(i) if typ == 11 else wstr(i) if typ == 12 else i + 4 if typ in (13, 14) else i + 1
            else:
                raise ValueError(f"unknown script property type {typ}")
    return bytes(b)


_SHAPES = {}
NAMES_CACHE = os.path.join(env.WORK, "tailor_shapes.json") if env.WORK else None


def _shape_names(f):
    """Shape names, in order, of a nif. Kept on disk by file time and size (tailor_shapes.json), so a start of the
    Tailor does not open thousands of meshes again; save_shape_names() writes what is new."""
    names = _SHAPES.get("names")
    if names is None:
        names = _SHAPES["names"] = {}
        try:
            with open(NAMES_CACHE, encoding="utf-8") as fh:
                names.update(json.load(fh))
        except (OSError, ValueError, TypeError):
            pass
    st = os.stat(f)
    key = os.path.normcase(f)
    hit = names.get(key)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return hit[2]
    from nifly_env import NifFile
    names[key] = [st.st_mtime_ns, st.st_size, [sh.name for sh in NifFile(f).shapes]]
    _SHAPES["dirty"] = True
    return names[key][2]


def save_shape_names():
    if not (_SHAPES.get("dirty") and NAMES_CACHE):
        return
    try:
        with open(NAMES_CACHE + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(_SHAPES["names"], fh)
        os.replace(NAMES_CACHE + ".tmp", NAMES_CACHE)
        _SHAPES["dirty"] = False
    except OSError:
        pass                                        # only a cache: the next start reads the meshes again


def built_shapes(path):
    """Shape names, in order, of the UBE mesh meshes/!UBE/<path> as the game loads it (the highest priority loose
    file), or None."""
    for d in env.dirs_with(os.path.join("meshes", "!UBE")):
        f = os.path.join(d, "meshes", "!UBE", path)
        if os.path.isfile(f):
            try:
                return _shape_names(f)
            except Exception:
                return None
    return None


def source_shapes(path):
    """Shape names, in order, of the outfit's own (3BA) mesh: the Tailor's copy of it, else the game's file."""
    cands = [os.path.join(mp.WORK, "meshes", path)] if mp.WORK else []
    if not any(os.path.isfile(f) for f in cands):
        try:
            if "res" not in _SHAPES:
                _SHAPES["res"] = tc.Resolver()
            kind, f = _SHAPES["res"].resolve(path)
            if kind == "loose":
                cands.append(f)
        except Exception:
            pass
    for f in cands:
        if os.path.isfile(f):
            try:
                return _shape_names(f)
            except Exception:
                continue
    return None


UBE_PARTS = {"BaseShape", "Feet", "Hands"}           # the UBE reference shapes, exactly as named


def reindex_alt(x, names, old=None):
    """Alternate textures (MO3S...) with each entry's 3D index set to where its shape is in the UBE mesh. The game
    finds the shape by that index, and a converted mesh lists its shapes in another order (the old 3BA body shapes
    are gone, the UBE body is added), so the colour variants of an outfit landed on the wrong shapes: dress texture
    on the body, metal on the lace ([COCO] Mysterious Mage). The game goes by the index alone (authors often leave
    a wrong name), so with the outfit's own mesh (old) the shape is the one at that index there; without it, the one
    with the entry's name. Entries whose shape is not in the UBE mesh stay as they are."""
    if not names or len(x) < 4:
        return x
    n = struct.unpack_from("<I", x, 0)[0]
    o, out = 4, [x[:4]]
    low = [m.lower() for m in names]
    try:
        for _ in range(n):
            ln = struct.unpack_from("<I", x, o)[0]
            name = x[o + 4:o + 4 + ln]
            tx, idx = struct.unpack_from("<Ii", x, o + 4 + ln)
            own = name.decode("cp1252", "replace").rstrip("\0").lower()
            was = old[idx].lower() if old and 0 <= idx < len(old) else None   # where the game showed it before
            nm = was if was in low else own
            if 0 <= idx < len(names) and names[idx].lower() == nm:
                pass                                    # already right (the game ignores case)
            elif nm in low:
                idx = low.index(nm)
            if 0 <= idx < len(names) and names[idx] in UBE_PARTS:
                # never on the UBE body / feet / hands the Tailor added (they keep the skin): the outfit shape with
                # the entry's own name if there is one, else the entry goes
                alt = [k for k, m in enumerate(low) if m == own and names[k] not in UBE_PARTS]
                idx = alt[0] if alt else -1
            if idx >= 0:
                out.append(x[o:o + 4 + ln] + struct.pack("<Ii", tx, idx))
            o += 12 + ln
    except struct.error:
        return x
    out[0] = struct.pack("<I", len(out) - 1)
    return b"".join(out) + x[o:]


def remap_sub(t, x, R, fids):
    if t in fids and len(x) == 4:
        return _u32(x, R)
    if t == b"KWDA":
        return remap_array(x, R)
    if t in ALT_TEX:
        return remap_alt(x, R)
    if t == b"DSTD":
        return remap_dstd(x, R)
    if t == b"VMAD":
        return remap_vmad(x, R)
    return x


# ---------------------------------------------------------------- winning overrides, smart slots
def winners(skip=()):
    """{(sig, owner plugin lower, object id): (plugin, its masters, data, flags)} for every armor and armor addon:
    the last enabled plugin in the load order that has the record (the winning override - e.g. a balance patch),
    leaving out the Tailor's own files and `skip` (lower-case names)."""
    loc = plugin_locations()
    names = {p.lower(): p for p in enabled_plugins()}
    ours = {f.lower() for f in merged_files()} | set(skip)
    out = {}
    for low in env.load_order():
        if low not in names or low in ours or low not in loc:
            continue
        try:
            ms, recs = read_plugin(loc[low], {b"ARMO", b"ARMA"})
        except (OSError, ValueError, struct.error):
            continue
        n = len(ms)
        for sig, fid, d, fl in recs:
            owner = (ms[fid >> 24] if fid >> 24 < n else names[low]).lower()
            out[(sig, owner, fid & 0xFFFFFF)] = (names[low], ms, d, fl)
    return out


def used_masters(name, ms, data):
    """Plugins a record of `name` (masters ms) refers to - they must be masters of the file it is copied into."""
    used = set()

    def note(fid):
        if fid:
            i = fid >> 24
            used.add(ms[i] if i < len(ms) else name)
        return fid
    for t, x in subrecords(data):
        remap_sub(t, x, note, ARMO_FIDS | ARMA_FIDS)
    return used


def _bod(d):
    return next((struct.unpack_from("<I", x)[0] for t, x in subrecords(d) if t in (b"BOD2", b"BODT")), 0)


def _strip_bod(t, x, mask, add=0):
    if (mask or add) and t in (b"BOD2", b"BODT") and len(x) >= 4:
        return struct.pack("<I", struct.unpack_from("<I", x)[0] & ~mask | add) + x[4:]
    return x


SMART = {34: 1 << 4, 38: 1 << 8}     # forearms, calves: often claimed by body armor that does not cover them
COVER_MIN = 15                       # outfit points on those bones that count as "covers it"
CROTCH = {52: 1 << 22, 53: 1 << 23}  # UBE / TNG hide the vulva for anything on these (underwear, "vagina cover")
CROTCH_MIN = 0.6                     # share of the vulva the piece's fabric must hide to keep the slot
FREE_SLOT = 1 << 30                  # slot 60: given to a piece that would be left without any slot
FREE_LEG = 1 << 24                   # slot 54 (leg, secondary) for a leg piece that lost 53; UBE uses neither
SLOT_NAMES = {**SMART, **CROTCH}


def smart_slots(e, armo_data, converted):
    """{"arma": {addon object id: slot bits to remove}, "armo": {armor object id: bits}} for one outfit mod.
    A body piece (slot 32) whose mesh claims slot 34 / 38 but has none of its own shapes on the forearms / calves
    (tc.slot_cover, only once it is built as UBE) loses that slot: two worn meshes on one slot make the game hide
    one of them (boots or gauntlets vanish). The armor itself loses the slot when all its addons that had it did."""
    out = {"arma": {}, "armo": {}, "arma_add": {}, "armo_add": {}}
    if not env.S.get("smart_slots", True):
        return out
    n = len(e["ms"])
    armas = {fid & 0xFFFFFF: d for sig, fid, d, _fl in e["recs"] if sig == b"ARMA" and fid >> 24 >= n}
    cand, crotch = {}, {}
    for _o, arma_objs in e["todo"]:
        for a in arma_objs:
            bod = _bod(armas[a])
            m3 = tc.mesh_path(next((zstr(x) for t, x in subrecords(armas[a]) if t == b"MOD3"), ""))
            if m3.lower() not in converted:          # same key as mod_records uses to switch the mesh
                continue
            name = tc.set_name_of(re.sub(r"(?i)_[01]\.nif$", "", m3))
            bits = [s for s, bit in SMART.items() if bod & 4 and bod & bit]
            if bits:
                cand[a] = (bits, name)
            cbits = [s for s, bit in CROTCH.items() if not bod & 4 and bod & bit]
            if cbits:                                # not a body piece (those carry the UBE body itself)
                crotch[a] = (cbits, name)
    cover = tc.slot_cover(sorted({s for _b, s in cand.values()})) if cand else {}
    for a, (bits, name) in cand.items():
        mask = sum(SMART[s] for s in bits if name in cover and cover[name].get(str(s), COVER_MIN) < COVER_MIN)
        if mask:
            out["arma"][a] = mask
    ccov = tc.crotch_cover(sorted({s for _b, s in crotch.values()})) if crotch else {}
    for a, (bits, name) in crotch.items():
        if name in ccov and ccov[name] < CROTCH_MIN:
            out["arma"][a] = out["arma"].get(a, 0) | sum(CROTCH[s] for s in bits)
    # Every UBE body armor sits on 32 + 53, like UBE's naked body (mod_records): the vulva is partition 53 of the
    # UBE body each converted body piece carries, and the game does not draw it when the piece is not on 53.
    # A piece of the same outfit still on 53 (it covers the vulva: closed panties, pantyhose) would share that slot
    # with the body pieces and only one of the two meshes would show, so it moves off 53 as well. A body piece
    # another UBE patch converts (not in todo) is on 53 too, so any worn body addon of the mod counts.
    worn = {struct.unpack_from("<I", x)[0] & 0xFFFFFF for sig, fid, d, _fl in e["recs"] if sig == b"ARMO"
            and fid >> 24 >= n for t, x in subrecords(d) if t == b"MODL" and len(x) == 4
            and struct.unpack_from("<I", x)[0] >> 24 >= n}
    if any(_bod(armas[a]) & 4 for a in worn if a in armas):
        for _o, al in e["todo"]:
            for a in al:
                bod = _bod(armas[a])
                if not bod & 4 and bod & CROTCH[53]:
                    out["arma"][a] = out["arma"].get(a, 0) | CROTCH[53]
    for a, mask in out["arma"].items():
        if not _bod(armas[a]) & ~mask & 0xFFFFFFFF:  # it must keep some slot to be shown at all: leg pieces
            out["arma_add"][a] = FREE_LEG if mask & CROTCH[53] else FREE_SLOT    # 53 -> 54, the rest -> 60
    for armo_obj, arma_objs in e["todo"]:
        bod = _bod(armo_data[armo_obj])
        mask = 0
        for s, bit in SMART.items():
            had = [a for a in arma_objs if _bod(armas[a]) & bit]
            if bod & 4 and bod & bit and had and all(out["arma"].get(a, 0) & bit for a in had):
                mask |= bit
        for s, bit in CROTCH.items():
            had = [a for a in arma_objs if _bod(armas[a]) & bit]
            if bod & bit and had and all(out["arma"].get(a, 0) & bit for a in had):
                mask |= bit
        if mask:
            out["armo"][armo_obj] = mask
        add = 0                                      # the armor must hold the slots its addons are shown on
        for a in arma_objs:
            add |= out["arma_add"].get(a, 0)
        if mask and not bod & ~mask & 0xFFFFFFFF and not add:
            add = FREE_LEG if mask & CROTCH[53] else FREE_SLOT
        if add:
            out["armo_add"][armo_obj] = add
    return out


def tng_revealing(e, armo_data, converted, log=None):
    """Armor object ids of this mod to list as revealing for TNG (The New Gentleman). TNG covers the genitals for
    every armor on slot 32 unless it is told the armor is revealing, so with TNG the UBE vulva vanished under a
    bikini top or a bra just like under a dress. A converted body piece with nothing of its own in front of the
    vulva (tc.crotch_cover up to CROTCH_SEEN away: a skirt or plate counts) is revealing; an armor is when all its
    converted body pieces are."""
    if not env.S.get("tng_revealing", True):
        return []
    n = len(e["ms"])
    armas = {fid & 0xFFFFFF: d for sig, fid, d, _fl in e["recs"] if sig == b"ARMA" and fid >> 24 >= n}
    body = {}
    for armo_obj, arma_objs in e["todo"]:
        if not _bod(armo_data[armo_obj]) & 4:
            continue
        names = []
        for a in arma_objs:
            if not _bod(armas[a]) & 4:
                continue
            m3 = tc.mesh_path(next((zstr(x) for t, x in subrecords(armas[a]) if t == b"MOD3"), ""))
            if m3.lower() in converted:
                names.append(tc.set_name_of(re.sub(r"(?i)_[01]\.nif$", "", m3)))
        if names:
            body[armo_obj] = names
    if not body:
        return []
    cov = tc.crotch_cover(sorted({x for v in body.values() for x in v}), tc.CROTCH_SEEN, "crotch_seen", log)
    return sorted(o for o, names in body.items() if all(x in cov and cov[x] < CROTCH_MIN for x in names))


TNG_INI = os.path.join("SKSE", "Plugins", "TNG", "UBE Tailor_TNG.ini")    # TNG 4 reads only that folder
TNG_INI_OLD = os.path.join("SKSE", "Plugins", "UBE Tailor_TNG.ini")       # where an earlier build put it


def write_tng_ini(records, log=print):
    """SKSE/Plugins/TNG/UBE Tailor_TNG.ini in the output mod: the revealing armors for TNG (tng_revealing), as
    "0x<id>~<plugin>" like the TNG files of bikini armor mods. Removed when there are none."""
    path = os.path.join(mp.MOD, TNG_INI)
    if os.path.isfile(os.path.join(mp.MOD, TNG_INI_OLD)):
        os.remove(os.path.join(mp.MOD, TNG_INI_OLD))
    if not records:
        if os.path.isfile(path):
            os.remove(path)
        return
    lines = [";Made by UBE Tailor - rewritten with every patch build, do not edit.",
             ";Converted body pieces (bikini tops, bras, open dresses...) whose fabric does not cover the vulva:",
             ";without this TNG covers the genitals for them like for a full dress.", "", "[Armor]"]
    lines += [f"RevealingRecord = 0x{o:X}~{plugin}" for plugin, o in records]
    text = "\r\n".join(lines) + "\r\n"
    try:
        with open(path, encoding="utf-8", newline="") as f:
            if f.read() == text:
                return
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(path + ".tmp", path)
    log(f"   TNG: {len(records)} body piece(s) that do not cover the vulva marked revealing ({TNG_INI})")


# ---------------------------------------------------------------- records of one outfit mod
def mod_records(e, index, new_i, ids, ui, target, extra, converted):
    """(armo bytes, arma bytes, armo count, arma count) for one source plugin. Armors are copied from their winning
    override (e["win"]: balance patches stay), smart slots (e["strip"]) are removed from the armor, its UBE copies
    and its original armor addons (overridden here, the mod itself is never edited)."""
    R = remapper(e["ms"], e["name"], index)
    n = len(e["ms"])
    armas = {fid & 0xFFFFFF: (d, fl) for sig, fid, d, fl in e["recs"] if sig == b"ARMA" and fid >> 24 >= n}
    armos = {fid & 0xFFFFFF: (d, fl) for sig, fid, d, fl in e["recs"] if sig == b"ARMO" and fid >> 24 >= n}
    win = e.get("win", {})
    strip = e.get("strip", {}).get("armo", {})          # armor -> slot bits to remove
    amask = e.get("strip", {}).get("arma", {})          # armor addon -> slot bits to remove
    sadd = e.get("strip", {}).get("armo_add", {})       # ... and the free slot to add when none is left
    aadd = e.get("strip", {}).get("arma_add", {})
    # UBE's naked body and UBE's own body armors sit on 32 + 53, so body pieces get 53 too: partition 53 of the UBE
    # body in the mesh (the vulva) is not drawn when the piece is not on 53 - a hole under every bra / bikini top.
    # Only when a piece of the outfit itself stays on 53 (smart slots off) do the body pieces go without it: two
    # meshes on one slot and the game shows only one of them. Counted with the slots the copies really get (smart
    # slots move garters, stockings, cuisses... from 53 to 54), never from the original records alone; an addon no
    # armor of the mod uses (a leftover in the plugin), or one without a female mesh, has nothing to hide.
    worn = {struct.unpack_from("<I", x)[0] & 0xFFFFFF for sig, fid, d, _fl in e["recs"] if sig == b"ARMO"
            and fid >> 24 >= n for t, x in subrecords(d) if t == b"MODL" and len(x) == 4
            and struct.unpack_from("<I", x)[0] >> 24 >= n}
    own53 = any(not _bod(armas[a][0]) & 4 and (_bod(armas[a][0]) & ~amask.get(a, 0) | aadd.get(a, 0)) & 1 << 23
                and any(t == b"MOD3" and zstr(x) for t, x in subrecords(armas[a][0])) for a in worn if a in armas)
    done, arma_body, armo_body = {}, b"", b""
    for armo_obj, arma_objs in e["todo"]:
        mine = []
        for a in arma_objs:
            if a not in done:
                data, fl = armas[a]
                subs = []
                m3 = tc.mesh_path(next((zstr(x) for t, x in subrecords(data) if t == b"MOD3"), ""))
                ube_shapes = built_shapes(m3) if m3 and m3.lower() in converted else None
                old_shapes = source_shapes(m3) if ube_shapes else None
                for t, x in subrecords(data):
                    if t == b"EDID":
                        x = zstr(x).encode("cp1252", "replace") + b"_UBE\0"
                    elif t in (b"BOD2", b"BODT"):
                        f0 = struct.unpack_from("<I", x)[0]
                        if f0 & 4 and not own53:        # body slot 32 -> also UBE slot 53
                            x = struct.pack("<I", f0 | 1 << 23) + x[4:]
                        x = _strip_bod(t, x, amask.get(a, 0), aadd.get(a, 0))
                    elif t == b"RNAM":
                        x = struct.pack("<I", ui << 24 | target)
                    elif t == b"MODL" and len(x) == 4:
                        continue                        # the old additional races
                    elif t == b"MO3S" and ube_shapes:
                        x = reindex_alt(remap_sub(t, x, R, ARMA_FIDS), ube_shapes, old_shapes)
                    elif t == b"MOD3":
                        path = tc.mesh_path(zstr(x))
                        key = path.lower()
                        if not key.startswith("!ube\\") and key in converted:
                            x = ("!UBE\\" + path).encode("cp1252", "replace") + b"\0"
                    else:
                        x = remap_sub(t, x, R, ARMA_FIDS)
                    subs.append(tc._sub(t, x))
                subs += [tc._sub(b"MODL", struct.pack("<I", ui << 24 | r)) for r in extra]
                done[a] = new_i << 24 | ids[f"{e['name'].lower()}|{a:06x}"]
                arma_body += tc._rec(b"ARMA", done[a], fl, b"".join(subs))
            mine.append(done[a])
        data, fl = armos[armo_obj]
        Ra = R
        if armo_obj in win:                             # a later plugin (balance patch...) changed this armor
            wname, wms, data, fl = win[armo_obj]
            Ra = remapper(wms, wname, index)
        subs, placed = [], False
        ins = b"".join(tc._sub(b"MODL", struct.pack("<I", f)) for f in mine)
        for t, x in subrecords(data):
            if t == b"MODL" and len(x) == 4 and not placed:
                subs.append(ins)                        # first in the list so it wins for UBE races
                placed = True
            subs.append(tc._sub(t, _strip_bod(t, remap_sub(t, x, Ra, ARMO_FIDS), strip.get(armo_obj, 0),
                                              sadd.get(armo_obj, 0))))
        if not placed:
            subs.append(ins)
        armo_body += tc._rec(b"ARMO", R(n << 24 | armo_obj), fl, b"".join(subs))
    n_over = 0
    for a, mask in amask.items():                   # the original armor addons lose the same slots (other races)
        if not mask:
            continue
        data, fl = armas[a]
        Ra = R
        if a in e.get("awin", {}):
            wname, wms, data, fl = e["awin"][a]
            Ra = remapper(wms, wname, index)
        body = b"".join(tc._sub(t, _strip_bod(t, remap_sub(t, x, Ra, ARMA_FIDS), mask, aadd.get(a, 0)))
                        for t, x in subrecords(data))
        arma_body += tc._rec(b"ARMA", R(n << 24 | a), fl, body)
        n_over += 1
    return armo_body, arma_body, len(e["todo"]), len(done) + n_over


def assign_ids(entries, old):
    """Object ids for the new armor addons of one file: keep earlier ones, fill the rest from the lowest free."""
    keys = [f"{e['name'].lower()}|{a:06x}" for e in entries for a in dict.fromkeys(x for _o, al in e["todo"] for x in al)]
    ids, used = {}, set()
    for k in keys:
        v = old.get(k)
        if v is not None and FIRST_ID <= v <= LAST_ID and v not in used:
            ids[k] = v
            used.add(v)
    nxt = FIRST_ID
    for k in keys:
        if k not in ids:
            while nxt in used:
                nxt += 1
            ids[k] = nxt
            used.add(nxt)
    return ids


# ---------------------------------------------------------------- other UBE patches: override, never edit
FOREIGN_FIDS = ARMA_FIDS | {b"RNAM", b"MODL"}


def owner_key(ms, name, fid):
    """(plugin that owns the record, lower case, object id): the same key in every plugin that lists it."""
    i = fid >> 24
    return (ms[i] if i < len(ms) else name).lower(), fid & 0xFFFFFF


def override_records():
    """{owner_key: armor addon data} of the overrides of other plugins' armor addons in the merged files."""
    out = {}
    for f in merged_files():
        ms, recs = read_plugin(os.path.join(mp.MOD, f), {b"ARMA"})
        for _sig, fid, data, _fl in recs:
            if fid >> 24 < len(ms):
                out[owner_key(ms, f, fid)] = data
    return out


def foreign_overrides(patch, converted, log=print):
    """Entries for one other UBE patch: its UBE armor addons whose mesh is built as UBE (MOD3 -> !UBE). Their body
    pieces keep slot 53 (the UBE vulva is partition 53 of the mesh and shows only on that slot); a slot-53 piece of
    the outfit that the Tailor converts moves to 54 instead (smart_slots). Returns [dict(key, ms, name, data, flags,
    new, masters)] - masters = the plugins the record refers to (only those become masters of UBE Tailor.esp)."""
    found = [f for f in tc.foreign_armas() if f["patch"].lower() == patch.lower()]
    out = []
    for f in found:
        subs, changed = [], False
        m3 = tc.mesh_path(next((zstr(x) for t, x in subrecords(f["data"]) if t == b"MOD3"), ""))
        key = m3.lower()
        for t, x in subrecords(f["data"]):
            if t == b"MOD3" and not key.startswith("!ube\\") and key in converted:
                x = ("!UBE\\" + m3).encode("cp1252", "replace") + b"\0"
                changed = True
            elif t == b"MO3S" and not key.startswith("!ube\\") and key in converted:
                y = reindex_alt(x, built_shapes(m3), source_shapes(m3))
                changed |= y != x
                x = y
            subs.append((t, x))
        if not changed:
            continue                              # the other patch's own record is right as it is
        used = set()

        def note(fid, ms=f["ms"], name=f["patch"]):
            if fid:
                i = fid >> 24
                used.add(ms[i] if i < len(ms) else name)
            return fid
        note(f["fid"])
        for t, x in subs:
            remap_sub(t, x, note, FOREIGN_FIDS)
        out.append(dict(key=owner_key(f["ms"], f["patch"], f["fid"]), ms=f["ms"], name=f["patch"], fid=f["fid"],
                        subs=subs, flags=f["flags"], masters={u.lower(): u for u in used}))
    return out


def foreign_bytes(e, index):
    R = remapper(e["ms"], e["name"], index)
    body = b"".join(tc._sub(t, remap_sub(t, x, R, FOREIGN_FIDS)) for t, x in e["subs"])
    return tc._rec(b"ARMA", R(e["fid"]), e["flags"], body)


# ---------------------------------------------------------------- build
def build(add=(), exclude=(), log=print, add_foreign=()):
    """Rebuild every UBE Tailor*.esp. add = outfit plugins to include from now on; add_foreign = other UBE patches
    whose armor addons get overridden from now on; exclude = patch files to leave out of the 'already covered'
    check. Returns [(file, mods, armors, addons, masters)]."""
    st = load_state()
    order = st["plugins"]
    for n in add:
        if n.lower() not in (p.lower() for p in order):
            order.append(n)
    forder = st["foreign"]
    for n in add_foreign:
        if n.lower() not in (p.lower() for p in forder):
            forder.append(n)
    skip = {f.lower() for f in merged_files()} | {x.lower() for x in exclude}
    cov, _aware = tc.covered_armos(exclude=skip)
    loc = plugin_locations()
    enabled = {p.lower() for p in enabled_plugins()}
    target, extra = tc.ube_races()
    converted = repoint_armas.converted_set()

    entries, W, n_win, n_strip, reveal = [], None, 0, 0, []
    for name in order:
        low = name.lower()
        if low not in enabled or low not in loc:
            log(f"   left out {name}: not enabled")
            continue
        path = loc[low]
        if tes4_info(path)[0] & LOCALIZED:
            log(f"   left out {name}: localized plugin (not supported yet)")
            continue
        todo = tc.patchable(path, name, cov)
        if not todo:
            log(f"   left out {name}: no armor left to patch (another UBE patch covers it)")
            continue
        ms, recs = read_plugin(path, {b"ARMO", b"ARMA"})
        names = {m.lower(): m for m in ms}
        names[low] = name
        names[tc.UBE_PLUGIN.lower()] = tc.UBE_PLUGIN
        if W is None:
            W = winners(skip)
        win, awin = {}, {}
        for armo_obj, arma_objs in todo:
            w = W.get((b"ARMO", low, armo_obj))
            if w and w[0].lower() != low:
                win[armo_obj] = w
            for a in arma_objs:
                w = W.get((b"ARMA", low, a))
                if w and w[0].lower() != low:
                    awin[a] = w
        src_armo = {fid & 0xFFFFFF: d for sig, fid, d, _fl in recs if sig == b"ARMO" and fid >> 24 >= len(ms)}
        e = dict(name=name, path=path, ms=ms, recs=recs, todo=todo, masters=names, win=win, awin=awin,
                 n_arma=len({a for _o, al in todo for a in al}))
        e["strip"] = smart_slots(e, {o: win[o][2] if o in win else src_armo[o] for o, _al in todo}, converted)
        reveal += [(name, o) for o in tng_revealing(e, {o: win[o][2] if o in win else src_armo[o] for o, _al in todo},
                                                     converted, log)]
        stripped = e["strip"]["arma"]
        for wname, wms, d, _fl in [win[o] for o in win] + [awin[a] for a in awin if a in stripped]:
            names.update({m.lower(): m for m in used_masters(wname, wms, d)})
        if win:
            n_win += len(win)
        if stripped:
            n_strip += len(stripped)
            src_arma = {fid & 0xFFFFFF: d for sig, fid, d, _fl in recs if sig == b"ARMA" and fid >> 24 >= len(ms)}
            for a, mask in list(stripped.items())[:3]:
                ed = next((zstr(x) for t, x in subrecords(src_arma[a]) if t == b"EDID"), f"{a:06x}")
                log(f"   smart slots: {ed} ({name}) - slot(s) "
                    + ", ".join(str(s) for s, bit in SLOT_NAMES.items() if mask & bit) + " removed: nothing of it there")
        try:                                   # renumber once on a throw-away index to catch odd data early
            mod_records(e, {k: 0 for k in names}, 0, {f"{low}|{a:06x}": FIRST_ID for _o, al in todo for a in al},
                        0, target, extra, converted)
        except (ValueError, struct.error, KeyError) as ex:
            log(f"   left out {name}: could not copy its records ({ex})")
            continue
        entries.append(e)
    if n_win:
        log(f"   {n_win} armor(s) copied from a later plugin that changes them (balance patch etc.) - its changes stay")
    if n_strip:
        log(f"   smart slots: {n_strip} armor addon(s) lost forearm / calf / crotch (52, 53) slots their mesh does "
            "not cover")
    n_over = 0
    for pname in forder:
        if pname.lower() not in enabled:
            log(f"   left out overrides of {pname}: not enabled")
            continue
        try:
            fo = foreign_overrides(pname, converted, log)
        except (ValueError, struct.error, KeyError) as ex:
            log(f"   left out overrides of {pname}: could not copy its records ({ex})")
            continue
        if fo:
            allm = {}
            for x in fo:
                allm.update(x["masters"])
            entries.append(dict(name=pname, foreign=fo, masters=allm, n_arma=0, todo=[]))
            n_over += len(fo)
    if n_over:
        log(f"   {n_over} armor addon(s) of other UBE patches overridden (built UBE mesh)")

    groups, cur, cur_m, cur_n = [], [], set(), 0
    for e in entries:
        m = set(e["masters"])
        if len(m) > MAX_MASTERS or e["n_arma"] > LAST_ID - FIRST_ID + 1:
            log(f"   left out {e['name']}: too big for one patch file")
            continue
        if cur and (len(cur_m | m) > MAX_MASTERS or cur_n + e["n_arma"] > LAST_ID - FIRST_ID + 1):
            groups.append(cur)
            cur, cur_m, cur_n = [], set(), 0
        cur.append(e)
        cur_m |= m
        cur_n += e["n_arma"]
    if cur:
        groups.append(cur)

    lo = load_order()
    result, new_ids = [], {}
    for gi, group in enumerate(groups):
        fname = file_name(gi)
        allm = {}
        for e in group:
            allm.update(e["masters"])
        masters = sorted(allm.values(), key=lambda m: (lo.get(m.lower(), 1 << 30), m.lower()))
        index = {m.lower(): i for i, m in enumerate(masters)}
        new_i = len(masters)
        ids = assign_ids([e for e in group if "foreign" not in e], st["ids"].get(fname.lower(), {}))
        new_ids[fname.lower()] = ids
        if tc.UBE_PLUGIN.lower() not in index:            # only overrides in this file
            masters.append(tc.UBE_PLUGIN)
            index[tc.UBE_PLUGIN.lower()] = len(masters) - 1
            new_i = len(masters)
        ui = index[tc.UBE_PLUGIN.lower()]
        armo_body, arma_body, n_armo, n_arma = b"", b"", 0, 0
        for e in group:
            if "foreign" in e:
                for x in e["foreign"]:
                    arma_body += foreign_bytes(x, index)
                n_arma += len(e["foreign"])
                continue
            a, b, c, d = mod_records(e, index, new_i, ids, ui, target, extra, converted)
            armo_body += a
            arma_body += b
            n_armo += c
            n_arma += d
        tes4 = tc._sub(b"HEDR", struct.pack("<fiI", HEDR_VERSION, n_armo + n_arma + 2, max(ids.values(), default=FIRST_ID - 1) + 1))
        tes4 += tc._sub(b"CNAM", b"UBE Tailor\0")
        tes4 += tc._sub(b"SNAM", b"UBE versions of outfits, made by UBE Tailor (by Desertravel). The tool rebuilds this file; "
                                 b"do not edit it by hand.\0")
        for m in masters:
            tes4 += tc._sub(b"MAST", m.encode("cp1252", "replace") + b"\0") + tc._sub(b"DATA", b"\0" * 8)
        blob = struct.pack("<4sIIIIHH", b"TES4", len(tes4), 0x200, 0, 0, 44, 0) + tes4
        blob += tc._grup(b"ARMO", armo_body) + tc._grup(b"ARMA", arma_body)
        out = os.path.join(mp.MOD, fname)
        os.makedirs(mp.MOD, exist_ok=True)
        with open(out + ".tmp", "wb") as f:
            f.write(blob)
        os.replace(out + ".tmp", out)
        result.append((fname, len(group), n_armo, n_arma, len(masters)))

    write_tng_ini(reveal, log)
    keep = {r[0].lower() for r in result}
    for f in merged_files():
        if f.lower() not in keep:                       # no longer needed (fewer files than before)
            shutil.move(os.path.join(mp.MOD, f), os.path.join(env.backup_dir(), f))
            log(f"   removed {f} (moved to the backup folder)")
    st["plugins"] = order
    st["foreign"] = forder
    st["ids"] = new_ids
    save_state(st)
    save_shape_names()
    return result


def place_in_load_order(files, drop=()):
    """Enable the output mod, tick the merged files and put them at the end of the load order (after all their
    masters); remove the drop plugins. Only when MO2 is closed (env.can_edit_profile). True if
    written (or nothing had to change). Every profile file is backed up first (env.backup)."""
    if not env.can_edit_profile():
        return False
    env.enable_output_mod()
    ours = {f.lower() for f in files} | {d.lower() for d in drop}
    for txt, prefix in (("plugins.txt", "*"), ("loadorder.txt", "")):
        p = os.path.join(env.PROFILE, txt)
        if not os.path.isfile(p):
            continue
        with open(p, "rb") as f:
            raw = f.read()
        nl = "\r\n" if b"\r\n" in raw else "\n"
        lines = raw.decode("utf-8", "replace").splitlines()
        keep = [ln for ln in lines if ln.strip().lstrip("*").lower() not in ours]
        keep += [prefix + f for f in files]
        if keep == lines:
            continue
        env.backup(p)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(nl.join(keep) + nl)
    return True


def scan_records():
    """(source plugin label, armor addon data) for every UBE copy in the merged files; label = plugin w/o extension."""
    for f in merged_files():
        ms, recs = read_plugin(os.path.join(mp.MOD, f), {b"ARMO", b"ARMA"})
        own = len(ms)
        src = {}
        for sig, fid, data, _fl in recs:
            if sig != b"ARMO":
                continue
            label = os.path.splitext(ms[fid >> 24])[0] if fid >> 24 < own else BASE
            for t, x in subrecords(data):
                if t == b"MODL" and len(x) == 4:
                    a = struct.unpack("<I", x)[0]
                    if a >> 24 == own:
                        src.setdefault(a, label)
        for sig, fid, data, _fl in recs:
            if sig == b"ARMA" and fid >> 24 == own:       # our own UBE copies (overrides: override_records)
                yield src.get(fid, BASE), data


