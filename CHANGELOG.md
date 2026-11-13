# Changelog

## Unreleased
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
