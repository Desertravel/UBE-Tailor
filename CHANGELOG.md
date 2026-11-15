# Changelog

## Unreleased
- **The vulva no longer vanishes under bikini tops, bras, dresses and other body pieces.** Converting cut it out of
  the UBE body inside every piece on slot 32: UBE's vulva lies deeper than the smooth 3BA crotch, and the Tailor
  hid every UBE body point farther than 1.2 from the old 3BA body. The crotch (partition 53 of the UBE body) is
  now kept unless the author cut most of it away (long skirts, pants: 180 pieces on the test list). Pieces you
  converted before are repaired by themselves at the next Scan (only the hidden-body data of their project changes,
  once per piece; 702 of 882 body pieces on the test list): run Batch Build in BodySlide afterwards.
- **Fix clipping (experimental):** a new button. Pick the body presets you play with (all are ticked - keep it that
  way: fixing for a few makes the others worse) and the Tailor changes how the ticked converted pieces (or all of
  them) follow the body sliders, so they stay outside the UBE body at every one of those presets. The shape at rest
  stays as converted; only the project's slider data changes (the original is kept as `.osd.orig`). Every point
  is checked on its own at every preset: a change is kept only where it does not sink in anywhere it did not
  before, so no piece gets worse at any of your presets; pieces that already fit them all are left alone. Run
  Batch Build in BodySlide again afterwards. Fixed pieces show "clipping fixed" in the list; the Tailor remembers
  which pieces it did for which presets and skips them next time; converting a piece again undoes its fix.
  Test (62 pieces of a real list, 27 presets, fit check before/after): points inside 70,350 -> 15,007, no piece
  worse at any preset; worst grade per piece of 50 random pieces A 20 / B 13 / C 17 -> A 37 / B 7 / C 6; about 8 s per piece
  (6 at a time), up to a minute for big bras and dresses. Also on the command line: `python fix_clip.py`.
- Preset, Workers and "Re-convert done ones" moved up next to Modpack / Requirements / Guide: in a narrow window
  they were pushed out of sight behind the buttons, so the preset could not be picked.
- **Smart slots 52 / 53 - the vulva no longer vanishes under garters, belts and crotchless panties.** UBE (and its
  TNG addon) hide the vulva for anything worn on slot 52 ("underwear") or 53 ("vagina cover"), but 3BA mods put
  many pieces there that do not cover it: garters, belts, thigh armor, skirts, stockings, piercings, open panties.
  For every converted piece on 52 / 53 that is not a body piece, the Tailor now checks whether its fabric hides the
  vulva when seen from outside (rays from the UBE body outward; kept in the database as db[set]["crotch"]); below
  60 % the piece loses the slot (53 -> 54, 52 -> 60 when nothing else is left, neither is used by UBE). Panties,
  pants, closed thongs and pantyhose keep it. On the test list: 515 records changed, e.g. all garters / belts and
  the crotchless "Lewd" panties; regular ones 93-99 % covered, crotchless 0-18 %. Same setting as smart slots
  (`smart_slots`, default on); takes effect at the next Scan / Update patch, no BodySlide build needed.
- **Outfits whose plugin writes the mesh path with a "meshes\" prefix are converted now.** The game drops that
  prefix, the Tailor did not: it looked for "meshes\meshes\...", found nothing and listed the piece as "Mesh
  missing in the mod", so it stayed 3BA and clipped on the UBE body at every preset. On the test list: 141
  pieces (122 of TEWOBA - The Expanded World of Bikini Armor, 18 ninistuff outfits); after the fix they convert
  and grade A at all tested presets. Scan, the patch and smart slots all read paths the same way now.
- Fix clipping: a piece with no visible outfit shape (only hidden or untextured ones) is listed as already fine
  instead of failing with KeyError.
- A piece whose conversion crashes inside the mesh library (PyNifly: "OSError ... access violation", seen once in
  3,800 pieces; the same piece converts fine on its own) is tried again at the end in a fresh process, instead of
  being listed as failed.
- Converting shows progress while it first copies the outfit meshes (minutes for thousands of pieces after a fresh
  start - before, the bar stood still), and Stop works during that step too.
- The fit check (and conversion) no longer depends on search order when an outfit point is equally close to two
  body triangles (at seams): the same triangle is always used, so in/out is always read the same way.
- **Skyrim LE meshes are ported to SE automatically** (le_port.py, with PyNifly: shapes, skin, weights, partitions,
  shaders, textures, alpha, string extra data such as BODYTRI and the HDT-SMP path) into the work folder, then
  converted as usual. The mod's own file is never changed. Before, such outfits were listed as "Old LE mesh".
- **Single-weight meshes** (no _0/_1 pair, about 1000 pieces on the test list) are converted now: their BodySlide
  project builds one file (GenWeights off). Before, they were listed as "Not supported".
- **Outfits are grouped better:** a mesh folder that holds many outfits (Caenarvon\Cosplay: 400+ pieces) is split
  by plugin and by the first word of the file name, so converting the Sailor outfit converts its 18 pieces, not
  the whole folder. Groups that are still huge are never pulled in with another piece.
- **BodySlide button:** opens BodySlide through MO2 (so it sees your mods); when you close it, the Tailor scans.
- Health check: clearer text for meshes the mod points at but never shipped.
- The "New outfits" window (Update patch) scrolls now, with Apply / Cancel always visible at the bottom, a
  search box and Tick shown / Clear. Before, with many mods, Apply was below the screen.
- First start: the Tailor makes its output mod with an empty `UBE Tailor.esp` at once, so MO2 lists both right away.
- While MO2 is open the Tailor no longer changes MO2's mod list or load order (MO2 wrote its own lists back as soon
  as BodySlide was started from it, so the output mod was switched off again). Instead a bar says what to tick
  ("press F5, then tick ...") and goes away by itself once it is done. With MO2 closed it still ticks them itself.
- Scans again by itself when BodySlide is closed, so the patch switches to the meshes BodySlide just built.
- `UBE Tailor.esp` now copies each armor from its **winning override** (the last plugin in the load order that
  changes it: keyword patches, balance patches, Synthesis, string fixes) instead of from the outfit mod itself.
  Before, those changes were undone for every converted armor (845 of 1610 armors on the test list).
- **Smart slots:** a body piece whose mesh claims the forearm (34) or calf (38) slot without having anything there
  loses that slot in the UBE version (and in its original addon, overridden - the mod is never edited). Wearing
  boots or gauntlets with it no longer makes them vanish. Checked per piece from the converted mesh; settings key
  `smart_slots` (default on).

## 0.9.2-beta (2026-11-13)
- Knows which Skyrim the modpack runs (reads SkyrimSE.exe: SE 1.5.97 or AE 1.6.x, shown bottom right and in the
  requirements screen) and asks when it cannot tell. On SE / older AE it warns when plugins of the modpack use the
  newer AE format (header 1.71) and BEES is not installed.
- Outfit mods made for Skyrim LE (never re-saved for SE) are marked "LE plugin" in the list, and the Tailor asks
  before converting them: they usually work, but can have other LE problems.
- Fixed a crash at game start (CTD while loading, e.g. with Hermit Armor or Heels Fix): records copied from old
  plugins that were never re-saved for SE (form version below 40) were written as version 44, but their texture
  hash data was still in the old layout, so the game misread it. Copies now keep their source's form version.
- `UBE Tailor.esp` is written with plugin header version 1.70 instead of 1.71, so it also loads on Skyrim SE 1.5.97
  (1.71 needs AE 1.6.1130 or newer). Nothing else changes: the plugin's ids were already in the 0x800-0xFFF range.
- `tailor.ico` ships with the .bat version too (right-click a shortcut to `UBE Tailor.bat` > Properties > Change
  Icon). Left out two macOS-only helper files of Python (`fetch_macholib`).
- After updating: press **Update patch**, then **Apply** (even with nothing new ticked), so `UBE Tailor.esp` is
  rebuilt with the fixes. No need to convert or build in BodySlide again.

## 0.9.1-beta (2026-11-12)
- Starts with `UBE Tailor.bat` instead of `UBE Tailor.exe`: virus scanners flagged the small unsigned .exe launcher
  as a "binder" (false positive). The .bat is plain text you can read.
- Left out an unused helper .exe of Tcl (`tcl\nmake`). README in English, with build-from-source steps.

## 0.9.0-beta (2026-11-12) - first public beta
- Works with any Mod Organizer 2 modpack (paths, profile and game read from ModOrganizer.ini).
- First start: welcome guide, modpack picker, requirements screen (opens official pages, never downloads).
- One merged plugin `UBE Tailor.esp` (ESL, splits at 250 masters / 2048 records); no xEdit patches needed.
- Outfits covered by other UBE patches are overridden in `UBE Tailor.esp`, never edited.
- Points at UBE meshes only once BodySlide has built them; slot-53 rule per outfit; head pieces judged by the mesh.
- Fit and motion grades, whole-outfit conversion, left-out / outdated detection, health check with "Fix all".
- HDT-SMP safety (no falling bones), BODYTRI fix for OBody / RaceMenu morphs, flat feet for heel-posed stockings.
