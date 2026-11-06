# Changelog

## 0.3.0 (2026-11-06) TESTING release
Save compatibility: `save-safe` (records are edited and added, none removed or renumbered). A new game is still the cleanest way to see the new lighting.
This is a testing release: the new look step was verified in the maintainer's game in parts (Vault 101, Moriarty's Saloon, Megaton, the sky at several hours), not everywhere.
* New step **12b look** (about 1 minute): rebuilds Fallout 3's lighting, weather, water and colour grade, in place on the converted plugins:
  * the converter wrote every weather as an empty shell: they are rebuilt from the Fallout 3 originals (colours, clouds, fog, climates) together with graded image spaces;
  * water is recoloured like Fallout 3's, interior cells get the Fallout 3 colour grade of their cell (Moriarty's amber, the vault teal, metro and cave greys);
  * the 467 lights that lost their flags, near clip and falloff in the conversion get them back (this removed the hard-edged pale arcs on walls);
  * 94 objects whose destructible header had no stages (Rivet City doors, the Broken Steel control panel, cars ...) are repaired: activating them used to crash the game.
* Terminals: the terminal models are placed and turned like Fallout 3's (per-model corrections); restored references now also work for the DLC worlds.
* The update after 0.2.0 only re-runs the changed steps (the 2 h and 1 h conversion steps are kept).
* Not in this release (needs plugins the demo does not ship, or not verified yet): the party and Vault 101 childhood, quests and dialogue, the Fallout 3 character editor, NPC outfits and inventories, generic NPC clones, object scripts, ambient sound emitters and parity refs.

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
