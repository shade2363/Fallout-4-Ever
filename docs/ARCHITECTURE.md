# How it works

## The idea
Fallout 4-Ever never contains game data. It is a set of scripts that run on *your* PC, read *your* Fallout 3 files, and drive existing tools to convert them for Fallout 4.
Everything it produces stays on your PC.

## The pieces
| Piece | Folder | What it is |
|---|---|---|
| The program | `builder/` | the window (`gui.py`), the stage runner (`capital_builder.py`), detection of your games (`detect.py`), tool downloads (`fetch_tools.py`), updates (`updater.py`) |
| The payload | `worldfix/ actors/ navmesh/ packaging/ start/ tool/xedit/Edit Scripts/` | our conversion scripts, copied into the work folder when you press INSTALL |
| The installer script | `install-output.ps1` | copies the result into Fallout 4's Data folder, with backups, a manifest and an exact uninstall |
| The packaging tools | `tools/` | build the exe (`builder/make_exe.py`), sign a release (`tools/release.py`), smoke-test the packaged exe, leak-scan, etc. |
| The publishing guard | `publish/` | the only way this project is pushed to GitHub; it blocks personal data, secrets and game files |

## The steps (stages)
Each stage is resumable and records a fingerprint of the scripts it used, so an update only re-runs what changed.

| # | Stage | What it does | Time |
|---|---|---|---|
| 01 | prepare | creates the work folder, downloads the converter and xEdit (hash-checked), allows several masters in the Creation Kit | 1 min |
| 02 | assets | converts Fallout 3's meshes, textures and materials into Fallout 4 archives (uses the Archive2 and Elric tools from your Creation Kit) | about 2 h |
| 03 | plugins | converts `Fallout3.esm` and the five DLC plugins (xConvert, which is built on xEdit) | about 1 h |
| 04 | worldfix | repairs what the converter loses: ground cells, placed references, regions, enable states, DLC markers | 1 min |
| 05 | lod | terrain level-of-detail settings | 1 min |
| 06 | actors | places the Fallout 3 NPCs and creatures as Fallout 4 actors (drives xEdit with simulated clicks, so do not touch the PC) | 6 min |
| 10 | navmesh | converts 7,198 navigation meshes | 1 min |
| 12 | fixes | crash-fix overrides and locked terminals | 1 min |
| 15 | meshes | animated doors, terminal models | 1 min |
| 16 | start | builds the New Game start (`start/`), compiles two scripts with your Creation Kit compiler | 1 min |
| 18 | install | copies everything into Fallout 4's Data folder and enables the plugins | several min |

The numbering has gaps on purpose: those stages of the full project (quests, dialogue, items, audio ...) are not in the demo. See [ROADMAP.md](ROADMAP.md).

## The New Game start
Fallout 4's New Game plays a pre-war intro driven by a script attached to the quest MQ101. `start/` ships a **replacement** of that script (a loose file, which shadows the one
in the game's archives): it gives the engine the black two-frame movie it waits for, moves the player to a spot outside Vault 101 (a reference in `Fallout3.esm`), and starts our
quest. That quest (`CapitalStart.esp`) gives the Pip-Boy, completes the quest *Escape!*, fades the screen in, and opens the character editor then SPECIAL.
The replacement exists only while the mod is installed; uninstalling removes it.

## Work folder layout (`%LOCALAPPDATA%\CapitalBuild` by default)
```
builder.log, builder-state.json   log and progress (which stages are done and their fingerprints)
tool/                             downloaded converter and xEdit, and tool/output (what the stages produce)
scripts/                          our scripts compiled on your PC
backup/                           copies of any file the install replaced
installed-files.txt               every file the install placed in Fallout 4 (the uninstall removes exactly these)
```

## Updates
`builder/updater.py` asks this repository's latest GitHub release for `manifest.json` and `manifest.sig`, checks the signature with the public key built into the program
(`builder/update_key.py`), and only then downloads the payload zip (our scripts), checking its size and SHA-256 against the signed manifest. A new payload is kept next to
your settings and used by the next build; the previous one stays for rollback. Nothing downloaded is ever executed.
More: [UPDATE.md](UPDATE.md).

## Why there is a `publish/` folder
Releases are made by `tools/release.py` (build, leak-scan, sign) and published by `publish/publish.py`. The publish tool pushes only a separate clean `public` branch, created by the
tool from a tree that passed a gate (no game files, no credentials, no private paths or names), under a no-reply identity, and a git hook blocks any other push.
Maintainer details: [publish/README.md](../publish/README.md).

## Tests
`python -m unittest discover -s tests` runs the offline tests (updates and signatures, change detection, game detection on simulated installs, the start builder, the publish gate,
the command line, the mesh preparation for Elric, the install on a throw-away sandbox: its plugin list and uninstall, and that `SYNC-MANIFEST.json` still describes the payload).
`SYNC-MANIFEST.json` fingerprints the program payload; after editing a payload file run `python tools/verify_manifest.py --update`, and
`python tools/verify_manifest.py --root dist\CapitalConvert\_internal\payload` proves a built program carries exactly the files of this repository.
`python tools/smoke_exe.py` runs the *packaged* exe the way a stranger would. Game-dependent checks are listed in [RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md).
