# Troubleshooting

The window's **LOG** panel and the file `builder.log` in your work folder (default `%LOCALAPPDATA%\CapitalBuild`) hold every message. When asking for help, send that file.

## It will not start
| Symptom | Fix |
|---|---|
| Nothing happens when you double-click `CapitalConvert.exe` | Unzip the whole release first (do not run it from inside the zip). If it still does nothing, the window may be off-screen after a monitor change: delete nothing, just reboot and try again, and send `builder.log`. |
| Windows SmartScreen says "unknown publisher" | The program is not code-signed yet. *More info* > *Run anyway*, if you downloaded it from the official Releases page. Compare the file's SHA-256 with `SHA256SUMS.txt` in the release. |
| Antivirus quarantines `CapitalConvert.exe` | False alarms are common for programs built with PyInstaller. Check the SHA-256 against `SHA256SUMS.txt` and allow the folder. |

## The CHECKS panel shows `[XX]`
| Message | Fix |
|---|---|
| Fallout 4 was not found | Install it from Steam, or use **Browse** to pick the folder that contains `Fallout4.exe`. |
| Fallout 3 was not found | Use **Browse** to pick the Fallout 3 **Data** folder (the one with `Fallout3.esm`). The Game of the Year Edition is required. |
| Fallout 3 archive missing | The Fallout 3 install is incomplete. In Steam: right-click the game > Properties > Installed Files > Verify. |
| Archive2 / Elrich not found | Install the free **Fallout 4 Creation Kit** from Steam (Library > Tools), run it once, close it. |
| Fallout 4 version 1.10.x | Update Fallout 4 in Steam to 1.11.x. |
| Only N GB free | Pick a work folder on a drive with 150 GB free (**Browse** next to *Work folder*). |
| Fallout 4 is running | Close it (and the Creation Kit, xEdit) before pressing INSTALL / RESUME. |

## A step failed
Press **INSTALL / RESUME** again: finished steps are kept and the failed one is retried. If it fails twice, send `builder.log`.

| Where | Likely cause |
|---|---|
| Download of the tools fails | No internet, a proxy or a firewall. Download the two files named in `builder\tools.lock.json` yourself and set the environment variable `CAPITAL_TOOLS_DIR` to the folder that holds them; they are still checked against the fingerprints. |
| "SHA-256 does not match" | The download was damaged or changed. Run again; if it repeats, report it (do **not** work around it). |
| Convert plugins (step 3) crashes or the PC freezes | Not enough memory. Close other programs; it needs about 20 GB free RAM. |
| Actors (step 6) stops or hangs | Something clicked or covered the xEdit window. Close everything, do not touch the mouse or keyboard, and run again. |
| "Access denied" while installing | Run the program as Administrator, or install Steam games outside `Program Files`. |
| Convert plugins (step 3) shows "Not responding" | Older builds froze the window while the converter ran. This version shows a progress line every 50,000 records (it is normal for step 3 to take 1-2 hours). The full output is in `raw-output.log` in the work folder. Do not close it. |
| Meshes (step 15) prints a warning list at the end | A few meshes cannot be converted by the Fallout 4 mesh converter; the objects that use them stay invisible. The summary names them. The build is still usable. |
| The program closes at once or stops with no message | Look in `%LOCALAPPDATA%\CapitalConvert\crash.log` and send it with `builder.log`. |
| Disk full | Free space on the work folder drive and run again. |

## The game
| Symptom | Fix |
|---|---|
| The main menu appears but the Capital Wasteland is missing | Plugins are not enabled. Check `%LOCALAPPDATA%\Fallout4\plugins.txt` lists `*Fallout3.esm` ... `*CapitalActors.esp`. Run **INSTALL / RESUME** again to rewrite it. |
| First launch seems frozen | The world is large: wait about 3 minutes with a black window before worrying. |
| Black screen and no movement after typing `coc MegatonEntrance` at the main menu | Do not start that way: it skips the start-up and the game stays in a half-run intro. Choose **New Game** instead. If you already did, quit to the desktop and start again. |
| Crash on start | Disable other mods, run the game once without them, then try again. Send `builder.log` and your Fallout 4 version. |
| Flat or odd lighting, no weather changes | Expected in this demo: weather and lighting are not rebuilt yet. |
| Everything is invisible after an update | Run **INSTALL / RESUME** so the changed steps and the install run again. |

## Starting over
Close the window, delete the work folder (it is only scratch space) and run again. Your games are never modified except for the files added by the install, which
the **Uninstall** button removes.
