# Install guide

## Before you start
* Fallout 3 **Game of the Year Edition** (all 5 DLC) and Fallout 4 are installed. Fallout 4 should be **version 1.11.x** (Steam keeps it up to date; if you use a downgrade it may not work).
* **Fallout 4 Creation Kit** is installed (Steam > Library > Tools). It provides the tools the conversion needs. Run it once so it creates its settings, then close it.
* You have **150 GB free** on the drive you pick for the work folder (default: your Windows drive, `%LOCALAPPDATA%\CapitalBuild`). Most of it is temporary; the finished
  result added to Fallout 4 is about 3 GB.
* Close Fallout 3, Fallout 4, the Creation Kit and xEdit. **Do not use the keyboard and mouse while step 6 runs** (see below).

## Steps
1. Unzip the release anywhere, for example `C:\Games\FalloutEver`. Do not unzip it into a Fallout folder.
2. Double-click **`CapitalConvert.exe`**. The window opens.
3. **YOUR GAMES** shows the Fallout 4 folder, the Fallout 3 *Data* folder and the work folder. They are found automatically on Steam, GOG and Epic installs, and on any
   drive. If something is missing, use **Browse**. The **CHECKS** panel must show no `[XX]` lines (`[!!]` are warnings you can usually accept).
4. Click **INSTALL / RESUME**.
5. The first run downloads the two tools it needs from their official pages (*fnv-to-fo4* and *xEdit*, about 136 MB). Each file is checked against a fixed fingerprint; a
   changed or damaged file is refused.
6. The steps run one after another (the list shows `[>>] running` and `[OK] done`):

   | Step | Takes about |
   |---|---|
   | Prepare folders and tools | 1 min |
   | Convert Fallout 3 meshes, textures, materials | 1.5 to 2 h |
   | Convert the Fallout 3 plugins | 45 to 100 min (needs about 20 GB RAM) |
   | World repairs, terrain LOD | 1 min |
   | **Actors** | 6 min: **it drives xEdit by simulated clicks and typing. Do not touch the keyboard or mouse until the log says the step is done.** |
   | Navmesh, crash fixes, door and terminal meshes | 1 min |
   | Install into Fallout 4 | 10 min |

7. When the status line says **FINISHED**, the plugins are enabled for you.

## Play
* Start Fallout 4 from Steam. The first start loads about 3 minutes (the world is large).
* Choose **New Game**. Instead of Fallout 4's pre-war intro you arrive right outside Vault 101 with a Pip-Boy; the quest *Escape!* is already completed, and the character
  editor and SPECIAL screen open first. (While the mod is installed every New Game starts this way; uninstall to get the normal start back.)
* To go somewhere else: press `~` and type `coc MegatonPlaza` (or `coc TheMallMonument`, `coc RivetCityExterior04`). `tgm` is god mode.

## What the install changes on your PC
* Adds the converted files to `Fallout 4\Data` (plugins, archives, a few loose meshes and videos). Anything it would replace is copied to the `backup` folder first.
* Writes the list of installed files to `installed-files.txt` in your work folder.
* **`plugins.txt` (`%LOCALAPPDATA%\Fallout4`): replaced by a clean list** with only this mod's plugins, because other mods that are enabled (a New Vegas port, say) would load
  together with the Capital Wasteland. The list that was there is saved first in the `backup` folder of your work folder (`plugins.txt.pre-capital`) and the install says so.
  To keep your other plugins enabled instead, build with `CapitalConvert.exe build --keep-other-plugins`. Fallout 4 loads its own master and DLC files without `plugins.txt`.
* Sets `bEnableFileSelection=1` in `Fallout4Prefs.ini` (it is what makes the game read `plugins.txt`) and adds the loose-file settings to `Fallout4Custom.ini` if that file does not
  exist. The previous values are remembered so uninstalling puts them back.
* The last lines of the install log list all of this again, with the paths.
* Never modifies the original Fallout 3 or Fallout 4 game files.

## Uninstall
Close Fallout 4, open `CapitalConvert.exe` and press **Uninstall**. It shows a preview and asks first, then removes **only the
files listed in `installed-files.txt`**, puts back any file it had replaced from `backup\`, **puts your earlier `plugins.txt` list back** (plugins you added after the install stay) and
restores your ini values. Your Fallout 3 and Fallout 4 game files are never touched.

## Test it without risk
`-Sandbox <folder>` installs into a throw-away folder instead of Fallout 4, so you can look at the result first.
