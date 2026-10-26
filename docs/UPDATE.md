# Updating

Updates come from the project's GitHub releases (`github.com/shade2363/Fallout-4-Ever`). The program only contacts GitHub when **you press Check for updates**: no background
checks, no tracking.

## How to update
1. Open the program, press **Updates**, then **Check for updates**.
2. It shows the latest version, the release notes and a **save compatibility** line:
   * *Safe for existing saves.*
   * *Existing saves may break: start a new save after updating.*
   * *Existing saves will NOT work: start a new game after updating.*
3. Press **Install update**. Close the Updates window and press **INSTALL / RESUME**.

## What happens
* The update is a small package of our scripts (no game files). Its description is **signed**; the program refuses anything that is not signed with the project's key, or whose
  size or fingerprint differs from the signed values, or that contains program files or game file types.
* It is unpacked next to your settings and used by the next run. The previous version is kept, so **Roll back** returns to it.
* Only the steps whose scripts changed run again, plus every step after them. A script fix usually takes minutes; the long conversion steps (hours) only repeat if the tools
  or their scripts changed, and the release notes say so.
* If an update needs a **new program version** (the window itself changed), the Updates window says so and links to the new download. Unzip it over the old folder; your
  work folder and progress are kept.

## Without internet / manual
Download the release files yourself and unzip the new program over the old one. Your work folder and progress stay.

## Command line
```
CapitalConvert.exe --help               (every command; "<command> --help" shows its options; nothing is started)
CapitalConvert.exe --version
CapitalConvert.exe detect               (the games that were found and every problem)
CapitalConvert.exe plan                 (the stages and which are done)
CapitalConvert.exe build [--from ID] [--only ID] [--to ID] [--workdir DIR] [--fo4 DIR] [--fo3 DIR] [--yes]
                         [--keep-other-plugins] [--no-special-screen]
CapitalConvert.exe status
CapitalConvert.exe update-check
CapitalConvert.exe update-install
CapitalConvert.exe update-rollback
CapitalConvert.exe uninstall            (preview; add --yes to remove)
```
`--keep-other-plugins` and `--no-special-screen` are remembered in your work folder; `--no-keep-other-plugins` and `--special-screen` switch them off again. A stage whose
option changed runs again (the start and the install, about a minute).
