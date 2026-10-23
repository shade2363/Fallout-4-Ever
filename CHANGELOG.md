# Changelog

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
