# Contributing

Thanks for wanting to help. This project converts *your own* Fallout 3 installation for Fallout 4, so there are a few ground rules that protect everyone.

## The one hard rule: no game content
**Never** put anything from Fallout 3, Fallout 4 or the Creation Kit into an issue, pull request or discussion: no plugins (`.esm`, `.esp`), archives (`.ba2`, `.bsa`), meshes, textures, audio,
videos, compiled scripts from the games, or screenshots of the game. This includes files the program builds on your PC. Describe what you see in words instead.
Pull requests that contain such files are closed. A repository gate (`publish/`) and CI also reject them.

## Reporting a problem
Use the *Bug report* form. Attach `builder.log` from your work folder (default `%LOCALAPPDATA%\CapitalBuild`). The log contains folder names that include your Windows user name:
open it and replace anything you do not want to share before attaching.

## Suggesting something
Use the *Feature request* form or start a Discussion. Please check [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/SCRIPTS.md](docs/SCRIPTS.md) first: a lot of the unreleased
project is waiting for verification, not for ideas.

## Code changes
1. Fork, branch from `main`.
2. Make a small, focused change. Match the style of the surrounding code.
3. Run the checks (no game needed):
   ```
   python -m pip install pillow cryptography pywinauto
   python -m unittest discover -s tests
   python tools/leak_scan.py
   ```
4. Add or update tests for what you change (`tests/`) and update the docs.
5. Open a pull request using the template. Explain *what* and *why*, and say how you tested it (including whether you ran it against a real game install).

## What gets accepted
* Bug fixes with a test, clearer messages, better detection of game installs (Steam / GOG / Epic edge cases), documentation.
* New conversion steps only when they are **verified in the game** and **self-contained** (the rule in [docs/SCRIPTS.md](docs/SCRIPTS.md)).
* Not accepted: anything that bundles or downloads game content, bypasses ownership checks, adds telemetry, or loosens the update signature checks.

## Licence
By contributing you agree that your contribution is released under the project's [MIT licence](LICENSE).
