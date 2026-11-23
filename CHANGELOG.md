# Changelog

## Unreleased
- **SMP skirts and capes collide with the UBE body.** Cloth that HDT-SMP moves only stays out of the body when the
  physics has a body to collide with, and 3BA modpacks often have none (CBBE 3BA installed as "CBPC only"): skirts
  and capes swung into the fuller UBE body. Every converted outfit whose physics moves cloth now carries its own: an
  invisible, light copy of the UBE body (2,367 points, kept just under the skin, with the body sliders so it follows
  your preset, on plain skeleton bones) and its own copy of the outfit's XML (meshes\!UBE\...\<piece>.ube.xml in the
  output mod) that adds it as a still collision body. Only when the physics stays safe with it (no bone would fall,
  no physics bone turns still); otherwise the outfit converts as before. Convert SMP outfits again to get it.
- **SMP cloth keeps the body it collides with.** An HDT-SMP outfit whose physics XML collides its skirt or cape
  with the outfit's own body shape (`<per-triangle-shape name="3BA">`) lost that body: the conversion hides the old
  body, so the cloth had nothing to hit and swung into the UBE body. That body now stays as an invisible collision
  body in UBE shape, with the author's bones (the XML stays safe) and the body sliders. And where a 3BA conversion
  renamed the body but kept the old CBBE XML (it names a "CBBE" body the outfit does not have), the body takes that
  name - only when none of its bones would then fall (checked against the XML; Ninirim's Summer Casual would, so it
  stays as it is).
- **Health check: SMP without body collision.** It tells you when CBBE 3BA was installed without its SMP option
  (3BBB-Amazing.xml missing): UBE's SMP body collision object then cannot work, and moving skirts and capes pass into
  the body (3BA characters too) - with what to install and build to get collision.
- **Right-click a converted piece: Open in Outfit Studio.** Opens its project straight in Outfit Studio, to touch it
  up by hand (save there, then Batch Build). Needs the Tailor started from MO2; a project made since the Tailor was
  opened needs the Tailor closed first (MO2 shows programs the files as they were when it started them).
- **Health check: invisible bodies.** It now warns when a body mesh the game uses (female, male, UBE female / male)
  has no texture - built from a BodySlide reference project like "HIMBO Ref - Merged Body", which Batch Build can
  pick for the body's path. Men then showed only head, hands and feet.
- **Lost conversions show as "Not converted", not "Native UBE".** When the Tailor's projects were gone (deleted, or a
  modpack reinstall wiped the output mod) but UBE Tailor.esp still pointed the pieces at UBE meshes, Scan listed them
  as UBE meshes from another mod and never offered to convert them again (4,003 pieces after a reinstall). Now only
  a UBE mesh another mod points at counts as native.
- **Squeeze outfits keep their squeeze.** Latex and corset outfits often have their own sliders that press the body
  inside them (Christmas Latex: "[Predator] Tight Corset", "Tight Belt", on by default). The Tailor put the clean UBE
  body in instead, so the squeeze was lost. Now such sliders move the UBE body the same way (carried over from the
  old body; Tight Belt up to 1.69 on both), and an outfit converted from its unbuilt BodySlide project keeps them on
  its own shapes too. Fix clipping leaves these pieces as converted (it would push the pressed outfit back out).
- **BodySlide add-ons.** Sliders that a BodySlide add-on (SliderSetAddOn) adds to the UBE body, feet or hands
  project - e.g. "BodyRef Addon - UBE 2.0 Donut" - are now carried into every converted outfit, so a preset that uses
  them shapes the outfits like the body. Only with a BodySlide that builds add-ons (BodySlide 6): an older one
  ignores them, the body would lack the sliders, so outfits do not get them either. Outfits converted before the
  add-on was installed: tick "Re-convert done ones" and convert them again.
- **Fix clipping no longer hides the body under cloth that physics moves.** HDT-SMP skirts, coat tails, frills and
  dress hems count as covering the body only where they rest; wind and motion lift them, and the body hidden under
  them showed as holes or let the skin through. Now outfit parts weighted to physics bones the body does not have
  never cover it (cups, bodices and anything on the body's own breast / butt bones still do). On 35 SMP pieces with
  a body: 123,092 -> 88,294 hidden body points. Pieces are measured again at the next Fix clipping.
- **Thigh pieces that could not be worn on UBE characters.** A leg piece that leaves slot 53 (so the UBE vulva and the
  body pieces keep it) was moved to 54, thought free - but UBE's own 00UBE_HideUnderwear armor sits on 54 and UBE
  keeps it on its characters, so putting the piece on took it off again (TEWOBA Ebony Bikini Thigh A / B). Such
  pieces, and pieces that were on 54 in the outfit itself (stockings, garters, thigh bands: Witch, Cheongsam), now
  take a spare slot no armor of the same mod uses (60, else 48, 55, 59, 47, 44), one per slot they leave, so pieces
  that were on 52, 53 and 54 can still be worn together. An armor that holds 54 with none of its addons shown there
  (TAWOBA Imperial bikini pants) just drops it. Press Update patch; no conversion or BodySlide build needed.
- **BodySlide button: no Yes/No that is always No.** After converting, a BodySlide started from the Tailor cannot see
  the new projects (MO2 shows it the files as they were when it started the Tailor), and the button asked whether to
  start it anyway. Now it just says what to do (close the Tailor, F5 in MO2, BodySlide from MO2, Batch Build), and the
  "Next:" line after converting or Fix clipping says the same when there are new projects.
- **Steel no longer bends like cloth.** Metal shapes (the ones with a shine map: steel, iron, dwarven, ebony plate,
  buckles, chain links) followed every body slider point by point, so a muscle preset gave the plates abs, veins
  and creases. Now each metal part follows a smoothed version of the body's motion: it still grows and moves with
  the body (fully solid plates sank into it everywhere), but without the fine relief; tiny parts (rivets, studs)
  move as one solid piece. Their bone weights are smoothed the same way, so they bend softly instead of creasing.
  On 123 TEWOBA pieces at 4 presets: 52% less relief on the steel after Fix clipping, for a little more clipping
  that Fix clipping's hidden body covers (outfit points inside the body 550 -> 746). Conversion method 4: only
  pieces with a metal shape show as made with an older Tailor.
- **Fix clipping hides the body under the outfit.** Every converted body piece carries the UBE body inside it.
  Under tight fabric and plate, strong presets (muscle, curves, belly) pushed the skin through in small spots, the
  thing outfit makers fix by hand by removing ("zapping") the body under the piece. Fix clipping now does that for
  the presets you tick: a body point is hidden only where an opaque outfit surface lies along the skin right over
  it at every one of them. A band of skin along every edge stays (necklines, openings, cut-outs), and lace, mesh
  and other see-through shapes never hide anything. Only the project's hidden-body list changes (the conversion's
  data stays in .osd.orig); run Batch Build afterwards. Pieces fixed before are done again once. On 80 bikini
  armors (TAWOBA, TEWOBA, Caenarvon...) at 4 presets including ABS EX: 94,007 body points hidden, skin points
  through the outfit 22,628 -> 14,420, outfit points inside the body 14,975 -> 362.
- **Crash at start on non-English Windows fixed** (`'NoneType' object has no attribute 'lower'`). The Tailor checks
  whether BodySlide or the game is running with Windows' `tasklist`, which answers in the console's language and code
  page. On a German (or French, ...) Windows its message has letters Python could not read, the answer came back
  empty and the Tailor stopped before its first scan. It now reads that answer in the console's code page and never
  fails on it. Thanks to Papierherz for finding it and the fix.

## 0.9.4-beta (2026-11-17)
Rings and jewelry fit, a much faster start, the load order health check, head-only mods (earrings, circlets,
wigs) on UBE characters, and outfits for male UBE characters. After updating: start the Tailor (it updates the
patch by itself), re-convert the pieces it lists as outdated, then Batch Build in BodySlide.

**Who needs the male parts?** Most players use a female UBE character on the UBE female body: for them nothing
changes. The two entries about men (male UBE characters see their outfits; LDD Male Shape Shifters sliders) only
matter if you play a male UBE character or have male UBE NPCs.

- **UBE men see their outfits.** A UBE man wears the UBE body (the female mesh shaped by male morphs), but the
  patch's UBE armor addons kept the outfit's own male model: none at all for most outfit mods, so a male UBE
  character in a converted outfit was invisible but for head, hands and feet; otherwise the vanilla male mesh. The
  UBE copies now give men the converted female model too (third and first person), as UBE's own armor patch does.
  On the test modpack: 2897 copies showed nothing on men and 5285 the vanilla male mesh, now all 8416 the UBE one.
  Nothing else in the patch changes, and other races keep the mod's male model.
- **Outfits follow male UBE bodies (optional, experimental).** Sliders imported into UBE's own "... Male" projects, such as LDD
  Male Shape Shifters for UBE 2.0 (in Outfit Studio: Slider > Import > Import OSD, then Save Project), share UBE's
  body data, and the Tailor now gives them to every outfit it converts, always off by default (female bodies and
  presets do not change). Without them a body armor had 6281 to 10399 points inside the body at the Shape Shifter /
  Graves shapes; with them 227 to 309. Nothing changes when no such sliders are installed. Re-convert outfits made
  before to get them.
  **Experimental:** these numbers are measured by the Tailor on our test list, but we have not yet played a male
  character with LDD in game, so we cannot promise every outfit follows every LDD shape perfectly. Please tell us
  how it looks for you (screenshots help).
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
