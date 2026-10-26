# Changelog

## 0.2.1 (2026-10-24)
Fixes from the second outside test. Save compatibility: **existing saves may break: start a new save** (the five DLC plugins gain 160 placed objects, 66 meshes that were missing now
exist, and the plugin list is replaced by a clean one). A build of this version is a pre-release without a signed update manifest: the *Updates* button does not offer it; download the zip
from the Releases page instead.
* **The plugin list is checked.** The install never writes a `plugins.txt` that lacks this mod's plugins (an empty list leaves the game on a black screen that then stops responding,
  because the New Game script is installed but the world is not loaded): if none of the plugins reached `Data` it stops with the reason and leaves the old list alone; a read-only
  `plugins.txt` is made writable; after writing, the file is read back and the install fails if a plugin is missing. The log says `checked: all N plugins are in ...`.
* **Step 3 (convert the plugins) can be run again.** After any stop or failure after the first DLC plugin was converted, the next run failed with
  `Master FalloutNV.esm not found in ...\lab\Data\Anchorage.esm`: the converted DLC plugin is already the final file, xConvert refuses to overwrite it (it prints "A file of that name
  exists already", crashes and still exits with 0, which the build ignored), and the rename step then looked for a master that an earlier run had already renamed. A finished output is
  now recognised (complete on disk and newer than the Fallout 3 file) and kept; an unfinished or older one is removed before xConvert runs; xConvert's errors stop the step with the real
  message; and `rename-master.ps1` accepts a plugin whose master is already the new name. This also makes the upgrade from 0.2.0 in the same work folder work.
* **Mesh optimizer (Elric) no longer crashes.** The cause was found: Elric dies on a mesh whose collision points at a rigid body that has no shape. All 49 meshes that crashed it
  (36 Fallout 3 ones: hats, helmets, glasses, the baby carriage, the Tranquility pod, the metro door, the vault overseer desks ...; 13 DLC ones: the Anchorage mine, the Pitt cart,
  the Broken Steel stage, Tesla coil and water barrel, the Point Lookout ferris wheel and coffins, the Zeta machine, rubble and globe) have such a body, and none of 150 meshes picked
  at random has. `worldfix/elric_prep.py` cuts that collision link (a body without a shape collided with nothing in Fallout 3 either) before Elric runs, so every mesh is
  optimized and none is skipped, including the 17 that used to be removed by name. A mesh that still crashes is retried without collision, then skipped and listed in
  `elric-failures.txt`; the loose-meshes step (15) converts those one by one. Checked with the real Elric on the 49 and on the 17: all converted, exit 0.
  The ~33 MB Windows crash dumps the old retries left in `%LOCALAPPDATA%\CrashDumps` are no longer left behind (only dumps of this run are removed, never older ones).
* **The Vault 101 door, the vault ruins door and the metro tunnel door animate.** They were repaired as loose files but the animation step only looked in the archives
  ("model missing from archives"), so the doors stayed static. It now reads loose models first. When the bulk pass converts them (see above) they are found in the archives anyway.
* **Meshes that Fallout 3 itself never shipped** (51 "ABSENT" ones: test, effect and unused meshes) are listed in `missing-in-fallout3.txt` with an explanation instead of one count.
* **Placed objects:** the log named one opaque reason, "base not converted" (6,163 in `Fallout3.esm`, 940 in Zeta, 644 in The Pitt ...). It now names the real one: editor markers
  (room, collision, north, radiation markers), ambient sound emitters, ambient effect meshes (dust, mist, falling rocks), placeable water planes and engine marker forms: nothing
  Fallout 4 can take as a placed reference. Separately, **160 real objects that the DLC place into Capital Wasteland cells** (Broken Steel 136, The Pitt 16, Point Lookout 5, Zeta 3)
  were skipped as "cell of another plugin" and are now restored into the DLC's override of that cell.
* **`plugins.txt` is a clean list.** The install used to append its plugins to whatever was enabled, so a New Vegas port or any other mod loaded together with the Capital Wasteland.
  It now writes a clean list with only this mod's plugins, saves the earlier list in the work folder's `backup\` first, and the uninstall puts it back (plugins you added since stay).
  `CapitalConvert.exe build --keep-other-plugins` keeps the old behaviour. The install's last lines now say everything it changed outside `Data` (`plugins.txt`,
  `bEnableFileSelection=1` in `Fallout4Prefs.ini`, `Fallout4Custom.ini`); the uninstall restores each of them.
* **Texture archives:** `Archive2` exited with 1 on all six `* - Textures.ba2` builds because the Fallout 3 archives also hold font definitions, atlases and editor files
  (`.fnt .tex .psd .tai`, `dirinfo.txt`) it cannot take. Those are left out before it runs (Fallout 4 never reads them), the one interface texture it still refuses is listed in
  `archive2-skipped.txt`, any other refused texture is a warning, and an archive that is not written now stops the stage (the extracted files used to be deleted regardless).
  The archives are the same as before (Zeta: 371 textures, identical). The install no longer claims "textures as loose files" when there are none.
* **The install needed a `python` on the PATH** for the movie fixes and the world repairs (`apply-fixes.ps1`), which a PC with only the packaged program does not have. The packaged
  program now answers a plain `python script.py` call itself.
* **Command line:** `CapitalConvert.exe --help`, `<command> --help`, `help <command>` and `--version` print real help and start nothing. `uninstall --help` used to run the uninstall
  preview and a plain `--help` opened the window; a mistyped option is now refused (exit 2) instead of ignored.
* **`SYNC-MANIFEST.json` matches the repository.** It held the hashes of the development tree's copies, so it never matched files edited here (and listed a file that is not here).
  It now fingerprints the program payload as this repository holds it (line endings do not matter) and keeps the development copy's hash as `dev_sha256`.
  `python tools/verify_manifest.py` checks the repository, `--root <folder>` checks a built payload (`dist\CapitalConvert\_internal\payload`), `--update` rewrites it, and a unit test fails when it is stale.
* **New Game can no longer leave you stuck behind the SPECIAL screen on a PC where its Done button cannot be reached** (a game window larger than the screen): the checks warn about
  that setting before the build, and `CapitalConvert.exe build --no-special-screen` makes the start give the character 4 in every stat instead of opening the screen.
  Not tested in the game. The default is unchanged.
* Not changed: where New Game puts you. The spawn is the Fallout 3 trigger box `CG04SunBlindDummy` (rotation 0); the nearest objects are two canyon cave-entrance cliffs; there is
  no wooden object within 2,500 units of it in the source cell. Whether the first view is a bad one has to be looked at in the game.

## 0.2.0 (2026-10-22)
Save compatibility: first release with the New Game start; a save made with 0.1.x is not affected (0.1.x had no start script).
* Tested in the real game (2026-10-22, launched through F4SE): New Game, the fragment script, the spawn outside Vault 101, the Pip-Boy, *Escape!* completed, the
  character editor and the SPECIAL screen all ran. Found and fixed during that test: the compiler picked the game's own script instead of ours; the screen stayed black
  because nothing faded it back in; the Pip-Boy was added twice.
* Fixes from the first outside test (2026-10-22/23):
  * The window no longer freezes during the long conversion step: the converter's millions of per-record lines are reduced to a progress line every 50,000 records (the full text
    goes to `raw-output.log` in your work folder), and the log pane keeps the last 2,000 lines.
  * The mesh repair step (15) works in the packaged program: the audit no longer needs a plugin the demo does not build, the repair scripts run through the packaged program,
    and the Vault 101 and metro door meshes (and about 100 other skipped meshes) are repaired. A failed audit now stops the step instead of reporting success.
  * The end of a build shows a warning summary (what could not be converted and what that means in the game) instead of hiding problems.
  * A crashing helper script now ends with an error code and a `crash.log` entry; the packaged program used to show a hidden error dialog and wait for hours.
  * The installer no longer writes the 19 development-only plugins into `plugins.txt`, and its last line says what to do: start Fallout 4 from Steam, choose New Game.
    (Do not use the console command `coc MegatonEntrance` from the main menu: it skips the intro and leaves the game stuck.)
* New Game now starts right outside Vault 101 with a Pip-Boy and the quest *Escape!* completed (character editor and SPECIAL screen first). Only scripts that are
  verified and self-contained are in the demo: see docs/SCRIPTS.md.

## 0.1.1
Fixes only; save-safe.
* The packaged program could not find its tool list, so step 1 failed before downloading anything. Fixed.
* An update check without internet showed an error trace; it now says it cannot reach the update server.
* Added a window icon and an Uninstall button; no console window flashes any more.

## 0.1.0 (demo)
First release.
* World: the Capital Wasteland and the Anchorage, The Pitt, Broken Steel, Point Lookout and Zeta worlds converted from your own Fallout 3 install.
* Actors: about 4,260 placed NPCs and creatures (`CapitalActors.esp`), 300+ named characters as stand-ins.
* Navmesh: 7,198 navmeshes (`CapitalNavmesh.esp`).
* Fixes: crash-causing base objects made invisible instead of crashing (`CapitalFixes.esp`), locked terminals, animated doors and terminal models.
* Installer: one window, automatic detection of Steam / GOG / Epic installs and a drive scan, hash-checked tool downloads, resumable steps, safe install with backups and
  an uninstall that removes only what it installed.
* Updates: signed updates with rollback, and per-step change detection so updates only rebuild what changed.

Save compatibility: first release.
