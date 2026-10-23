# Which scripts ship in the demo, and why

The full project (kept on the maintainer's PC) converts thousands of Fallout 3 scripts. The demo only ships a script when **both** are true:
1. it was verified working in the game (evidence in the maintainer's `AUDIT.md`), and
2. it does not depend on a plugin or tool the demo does not ship (quests, dialogue, items, F4SE).

| Script group | Status in the audit | Needs | In the demo |
|---|---|---|---|
| **New Game start** (`start/`: spawn outside Vault 101, Pip-Boy, "Escape!" completed, character editor) | new, small, written for the demo; tested in game before release (see the release checklist) | only Fallout3.esm and Fallout 4 | **yes** |
| World repair, navmesh, crash-fix and terminal-lock *scripts* (Python build steps) | verified in game (world loads, navmesh soak test, 0 crashes) | nothing extra | yes (these are the build, not game scripts) |
| Quest scripts (`CapQ_*`, about 190 quests) | built and compile; only partly verified | `CapitalQuests.esp`, dialogue | no |
| Original "Escape!" driver (Vault 101 childhood and escape) | starts correctly; only the first conversation verified | quests, dialogue, items | no (replaced by the small start above) |
| Object, NPC and trigger scripts (`CapS_*`, about 2,000) | built and attached; spot-checked only | `CapitalScripts.esp` | no |
| Terminal result scripts | verified in game for three terminals | `CapitalItems.esp` (terminal menus) | no |
| Skills, perks, SPECIAL screen logic | skill/perk screens verified in the lab; skills have no gameplay effect yet | F4SE | no |
| Dialogue fragments and voice | built; voice playback not confirmed | `CapitalDialogue.esp` and audio | no |
| Radio, music, ambient sound scripts | built; never confirmed by ear | audio plugins | no |

A group moves into the demo when it passes both conditions. Nothing is added "because it compiles".

## What the start script does
* Replaces the script of Fallout 4's own new-game intro (`QF_MQ101_0001ED86`, a loose file that shadows the one in the game archives), so **New Game no longer plays the
  pre-war intro**: it plays a black two-frame movie the engine needs, then moves the player to the spot where a Fallout 3 player steps out of the vault door.
* Starts the quest *Escape!* and completes it: the Pip-Boy shows it under completed quests.
* Gives and equips the Pip-Boy, then opens the character editor, then the SPECIAL screen.
* While the mod is installed, **every New Game starts this way**; uninstalling removes the replacement script and Fallout 4's normal start comes back.
