# Roadmap

An honest list of what exists and what does not. Nothing here is a promise or a date.

## In the demo (built, tested)
- [x] Fallout 3 and the five DLC worlds converted and loading in Fallout 4 (terrain, buildings, interiors, doors, terminal models and locks)
- [x] About 4,260 placed NPCs and creatures, 300+ named characters as stand-ins
- [x] 7,198 navigation meshes
- [x] Crash-fix overrides found by spawning every converted object
- [x] New Game start outside Vault 101 (Pip-Boy, *Escape!* completed, character editor, SPECIAL)
- [x] One-click program: detection of Steam / GOG / Epic installs, resumable stages, safe install with backups, exact uninstall
- [x] Signed updates with rollback, and update detection per stage

## Not in the demo yet (exists only in the maintainer's unreleased project; ships when verified and self-contained, see [SCRIPTS.md](SCRIPTS.md))
- [ ] Quests (about 190 converted, partly verified)
- [ ] Dialogue with the Fallout 3 style option list, and voice lines
- [ ] Weapons, armour and consumables mapped to working Fallout 4 equivalents
- [ ] Object, NPC and trigger scripts (about 2,000, spot-checked only)
- [ ] Music, radio and sound effects
- [ ] Weather and lighting rebuilt from Fallout 3's
- [ ] NPC faces and body skin tones matched to Fallout 3
- [ ] Skills, perks and the Fallout 3 character editor look (needs F4SE)
- [ ] Companions, furniture use (sit, sleep), AI daily routines

## Known limits of the demo
- Needs Fallout 4 version 1.11.x; other versions are untested.
- GOG and Epic detection is built and tested on simulated installs only.
- Game Pass / Microsoft Store Fallout 4 is not supported.
- The program is not code-signed, so Windows SmartScreen may warn (compare the SHA-256 on the release page).
- While the mod is installed, every New Game starts at Vault 101 (uninstall to get the normal start back).

## Where to follow along
Releases and notes: the repository's *Releases* page. Questions and ideas: *Discussions*. Problems: *Issues* (attach `builder.log` from your work folder).
