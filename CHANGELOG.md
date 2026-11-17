# Changelog

## Unreleased
- **Health check: a plugin sorted below the patch.** UBE characters only see armor addons that name the UBE races,
  and the patch adds them to each armor. A load order sort (LOOT, MO2's Sort) had put a Synthesis patch between
  the UBE Tailor files, and its armor records, without those addons, won: 561 armors (rings, amulets, outfits)
  went invisible on UBE characters. The health check now names any plugin below the patch that undoes it, and
  moves the UBE Tailor files back to the bottom when MO2 is closed. The patch already carries what such a plugin
  changes (it copies the winning record), so nothing of it is lost.
- **Earrings, circlets, hats and wigs of head-only mods show on UBE characters.** UBE races have no armor race, so
  they wear only armor addons that name them. The Tailor never converts head pieces (they need no new shape), and
  a mod with nothing else, or whose chokers the conversion found above the neck, never got into the patch: all of
  it was invisible on UBE characters (Vanilla Chokers and Earrings, JS Vanilla Circlets, KS Wigs, Dragon Priest
  masks... 18 mods on the test modpack). Such mods now join the patch as they are; a mod with a piece still to
  convert joins once it is converted, and one with an old LE mesh does not.
- **BodySlide started from the Tailor warns about projects it cannot see.** MO2 shows a program the mod folders as
  they were when it started that program, and a BodySlide started from the Tailor gets the Tailor's view. Projects
  converted since the Tailor was opened are new files there, so Batch Build skipped them without a word (pieces
  converted again were built: their files existed already). The BodySlide button now says how many projects that
  are and that BodySlide started from MO2 (after closing the Tailor) builds them.
- **Vanilla gold and silver rings show on UBE characters.** UBE Vanilla Armor and Clothes gives these rings (and
  Dawnguard's Hawk Claw ring) a UBE armor addon whose !UBE mesh it does not ship, so a UBE character wearing one
  showed no ring at all, and the Tailor listed them as "Native UBE" and left them alone. Jewelry now counts as
  native UBE only when that UBE mesh really exists (loose or in a loaded archive); otherwise it is listed as not
  converted, and converting it makes the very mesh the UBE patch points at (meshes\!UBE\Armor\AmuletsandRings\
  SilverRing_1.nif ...). Convert, Batch Build, done.
- **Rings, amulets and some armors fit where they belong.** Many rings (and some outfits) are made in the space of
  the bone they hang on: their points are stored around 0,0,0 and the skin data says where the game puts them. The
  Tailor read those points as if they were already in place, so it fitted a ring to the body near the feet and
  moved it about half a unit off the finger (CrbEX Dragon Ring, AoM Cat Ring), and it judged pieces like VigCgT
  ShaoKhan Knight armor as "head pieces" (lowest point z=152) and never converted them. Now every piece is read
  where the game shows it, and its moves and slider data are written back in its own space. On the test list the
  rings sit on the finger again (median gap to the skin 0.82 -> 0.21, 1.55 -> 0.79, 1.04 -> 0.29), and outfits
  without such a transform come out byte-identical.
- **One-bone jewelry stays one solid piece.** A shape its author tied 100% to one bone (a ring on a finger, a
  pendant on the neck) keeps that bone instead of getting the skin's weights, which spread a ring over the hand and
  three finger bones and bent it with every finger move. Its sliders follow that bone's part of the body.
- Conversion method 3, without re-converting everything: once, at the first start, the Tailor looks at the source
  mesh of every piece converted before and lists as "made with an older Tailor" only the pieces the new method
  changes (a shape in a bone's space or tied to one bone); all others come out byte-identical and stay done (on
  the test modpack 2913 of 3346 pieces stay done, 433 to convert again). A skin transform within 0.01 units of
  none (exporter rounding, seen on many armors) counts as none. Pieces an older version listed as head pieces are
  checked again at their next conversion.
- **The Tailor starts much faster.** Updating the patch at the start looked for every mesh in every mod folder of
  the modpack (2000+ on the test modpack, a few hundred with meshes, ten with UBE meshes), read the mod list again
  for each mesh and opened thousands of meshes to learn their part names. Now it only looks in the folders that
  can hold the file, reads the mod list once and keeps the part names on disk (work\tailor_shapes.json, by file
  time and size). Same patch, byte for byte: 98 s -> 12 s on the test modpack (the first start after the update
  takes about 60 s to fill the name cache).
- **Fix clipping no longer redoes every piece.** It skips pieces already fixed for the ticked presets, but the
  window opened with every preset ticked, so any run that did not tick exactly the same presets as the last one
  worked through all converted pieces again. The window now ticks the presets of the last run (and says so), and a
  piece fixed for more presets than ticked counts as done.
- **"Made with an older Tailor" and "Left out" follow Show.** These two states listed every type of piece whatever
  Show said, so "Select shown" with Show "Jewelry & tails" ticked all clothing too, and a re-convert overwrote
  pieces fixed with Fix clipping.
- **Ticking is easier and Convert says why it did nothing.** A click anywhere on a piece's row ticks it (before, only
  the small box in the tick column did). When nothing can be converted, the message says why: nothing ticked, the
  ticked pieces are converted already (tick "Re-convert done ones"), or they are head pieces / native or hand-made
  UBE / missing / old LE meshes.

## 0.9.3-beta (2026-11-15)
- **No more hole at the crotch under bras and bikini tops.** The vulva of the UBE body is its partition 53, and the
  game draws that part of a mesh only when the armor addon is on slot 53, so UBE puts every body armor on 32 + 53.
  The Tailor left 53 off the body pieces of any outfit that has its own slot-53 piece (stockings, cuisses), to keep
  the two from sharing the slot, but it looked at the outfit's original slots: smart slots had already moved those
  pieces to 54. So more than half of the converted body pieces (828 of 1488 on the test list, e.g. [COCO]
  Witchiness bras, TEWOBA bikini tops) were on 32 only and showed a hole where the vulva is. Now every body piece
  gets 53, like UBE's own conversions, and a piece of the same outfit still on 53 (closed panties, tights) moves to
  54. Fixed at the next Scan (patch rebuild); no conversion or BodySlide build needed.
  The same goes for body pieces of other UBE patches (made with UBE's xEdit script or shipped by a mod): the Tailor
  no longer takes slot 53 off them when it overrides their mesh path, and a slot-53 piece of that outfit which the
  Tailor converts moves to 54.
- **Colour variants of converted outfits show on the right parts again.** Many outfits make their colour versions
  with alternate textures on the armor addon (white / black / gold sets of [COCO] Mysterious Mage, Caenarvon,
  ralfeta panties...). The game finds the part by its index in the mesh, and a converted mesh lists its parts in
  another order (the 3BA body shapes are gone, the UBE body is added), so the textures landed on the wrong parts:
  metal on the lace, the dress texture on the body, parts looking hidden. The UBE copies in UBE Tailor.esp now get
  each entry's index from the mesh BodySlide built (the part that had it in the outfit's own mesh, else the one
  with the entry's name), and never put one on the UBE body, feet or hands. Fixed at the next Scan for everything
  converted before (171 armor addons on the test list), no conversion or BodySlide build needed.
- **A hand-made UBE version always wins.** When another mod ships a UBE BodySlide project for an outfit (a conversion
  someone made by hand in Outfit Studio and shared online, or UBE's own armor conversions), the piece shows as
  "Hand-made UBE · <mod>" and is never converted. Both projects build the same mesh (meshes\!UBE\<the outfit's own
  path>), so if the Tailor had converted it before, its own project is moved to the backup folder at the next Scan
  and only the hand-made one is built; UBE Tailor.esp keeps pointing the outfit's armors at that mesh. Run Batch
  Build in BodySlide afterwards. Before, a standalone UBE version (with only UBE_AllRace.esp as master, e.g. [COCO]
  Mysterious Mage - UBE) was not noticed, and BodySlide built both over each other.
- The first patch build after updating measures every converted body piece once for the TNG file (a few minutes on
  a big list) and now says so, instead of sitting on "Updating the patches..." without a word.
- **TNG no longer hides the vulva under bikini tops and bras.** TNG (The New Gentleman) covers the genitals for every
  armor on slot 32 unless it is told the armor is revealing, so even with the vulva kept in the body (below) it
  vanished as soon as a bikini top was worn. The Tailor now writes `SKSE\Plugins\TNG\UBE Tailor_TNG.ini` (TNG 4
  reads its ini files only from that folder) in its output
  mod with every patch build: each converted body armor with nothing of its own in front of the vulva (rays from
  the UBE vulva, 30 units: skirts and plate count as covering) is listed as `RevealingRecord`, the way bikini armor
  mods ship their own TNG files. On the test list 838 of 1758 body armors (bikinis, lingerie, the revealing outfit
  mods). Settings key `tng_revealing` (default on); start the game again after the Scan.
- **Loose parts follow their own body part** (new conversions): an outfit point weighted to other bones than the
  body under it - a wide sleeve hanging next to the thigh, a cape over the back - takes its slider data from the
  nearest body points of its own bones, so the sleeve follows the arm instead of growing with the thigh (like
  hand-made conversions do). Only where it can never sink into the body: per point, everything the nearest body
  points would push it out by must fit in its gap from the body, otherwise it keeps the old behaviour. Test (40
  loose pieces: dresses, robes, cloaks, capes, hair; 4 presets): points inside 176 -> 176, 30 pieces use it.
- **Outfit adjust sliders** (new conversions): every converted piece gets the `*_ForOutfits` sliders of UBE outfits
  (BiggerBody, BiggerBreasts, BiggerBelly, BiggerButt, BiggerHips, BiggerThighs, BiggerCalves, BiggerFeet,
  BiggerUpperTorso, BiggerUpperSpine, BiggerLowerSpine, BiggerUpperarms, BiggerWrists, BiggerHands). They are 0 by
  default, so nothing changes; raise one in BodySlide to give a clipping area more room. Areas and amounts measured
  from the outfit projects of UBE mods (297). Pieces converted before get them when converted again.
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
