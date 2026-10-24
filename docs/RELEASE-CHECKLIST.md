# Release checklist (maintainer)

Nothing is published until every box is ticked. Do the steps in order.

## Before building
- [ ] `python -m unittest discover -s tests -v` passes (updates, change detection, detection).
- [ ] `python tools/leak_scan.py` passes on the repo (0 problems).
- [ ] `python tools/verify_manifest.py` says the repository matches `SYNC-MANIFEST.json` (after editing a payload file: `--update`); after building the exe, `python tools/verify_manifest.py --root dist\CapitalConvert\_internal\payload` says the same of the packaged payload.
- [ ] `powershell -File tools\sandbox_install_test.ps1 -Work <finished work folder>` prints ALL PASSED (installs into a throw-away folder, reinstalls, uninstalls, proves nothing of ours or of someone else's is left or lost). Run it on the build and again on the copy downloaded from the release page.
- [ ] After building the exe: `python tools/smoke_exe.py` prints ALL PASSED (runs the PACKAGED exe in a fresh work folder: tool list, downloads, a step, update-check offline, uninstall preview, window). Run it after every packaging change; a source run does not prove the exe works.
- [ ] `builder/version.py`: `VERSION` bumped. `STEPS_REV` bumped **only** if the built-in steps in `builder/steps.py` now produce something different.
- [ ] `CHANGELOG.md` has an entry; the save-compatibility label is decided (`save-safe`, `needs-new-save`, `needs-new-game`).
- [ ] `tools/sync_from_dev.py` was run if scripts changed in the dev tree, and its diff was read (no new Bethesda text or data files).
- [ ] `CREDITS.md` and `THIRD_PARTY_LICENSES/` still match the tools in `builder/tools.lock.json`.
- [ ] No Bethesda art, logos, characters or fonts anywhere (window, docs, screenshots).

## Test (a machine that is NOT the dev PC, or a clean Windows VM)
- [ ] Fresh Windows 10 and 11: unzip, double-click CapitalConvert.exe (no console window may flash), games detected (Steam default library; Steam library on another drive; path with spaces).
- [ ] Full clean run to FINISHED; `builder.log` has no unexpected errors.
- [ ] Install into a real Fallout 4: it starts **without** F4SE, the main menu appears, `coc MegatonPlaza`, `coc TheMallMonument`, `coc RivetCityExterior04` load, Papyrus log has no errors from our plugins.
- [ ] New Game (from the main menu, no console; first done 2026-10-22 on the maintainer's PC through F4SE with a keyboard-driven run; STILL TO DO: plain Steam launch, a PC without the maintainer's custom menu files, and menus left untouched to confirm they wait for the player): no pre-war intro, you land outside Vault 101, Pip-Boy equipped, *Escape!* listed as completed, race menu then SPECIAL open, then you can walk. Papyrus log has no errors from CapStartDemo or QF_MQ101.
- [ ] Uninstall: Data folder, `plugins.txt` and the ini files are identical to before (hash compare).
- [ ] Stop and restart at different steps: the run resumes.
- [ ] Wrong inputs: Fallout 4 missing, Creation Kit missing, Fallout 3 without DLC, low disk space, Fallout 4 running: clear messages, nothing damaged.
- [ ] Update test against a real previous release: old version, `Check for updates`, install, rollback.
- [ ] Tool download blocked (offline): the message explains `CAPITAL_TOOLS_DIR` and works with manually downloaded files.

## Build and sign
- [ ] `python tools/release.py --version X.Y.Z --notes-file notes.txt --save-compat save-safe` (builds, runs the leak scan on the package, signs with `%USERPROFILE%\CapitalConvert-signing\release-private.key`).
- [ ] Unzip the produced `CapitalConvert-X.Y.Z.zip` on a clean machine and run it once.
- [ ] `SHA256SUMS.txt` matches the files; upload them to the release page.
- [ ] The private signing key is backed up somewhere safe and was never committed or shared.

## Publish
- [ ] Create the GitHub release with all five files (`gh release create vX.Y.Z "dist\release\vX.Y.Z\*" --repo shade2363/Fallout-4-Ever`).
- [ ] From an older install, *Check for updates* sees it and installs it.
- [ ] README links work; the release notes say what changed and the save-compatibility label.
