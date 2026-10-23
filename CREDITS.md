# Credits

**Fallout 4-Ever** (Capital Convert) by TikTok@yourstruly_0, with opness1549.

This project (scripts under the MIT licence, see LICENSE) is a set of scripts that drives other people's software. None of it would exist without the teams below. Each tool keeps its own
licence; we do not claim any of it, and none of it is changed by us unless stated.

## The converter at the core
| Software | Team | Licence | Where |
|---|---|---|---|
| **Fallout 3 / Fallout: New Vegas to Fallout 4 converter** (`fnv-to-fo4`, v63) | terry-haire and contributors | GPL-3.0 | https://github.com/terry-haire/fnv-to-fo4 , Nexus mod 75425 |
| **xEdit / TES5Edit** 4.1.5f (also the engine inside the converter's `xConvert`) | the xEdit team (ElminsterAU, Zilav, Sheson and contributors) | MPL-2.0 | https://github.com/TES5Edit/TES5Edit |
| **NifSkope** (model converter inside the converter) | NifTools / the NIF File Format Library and Tools | BSD-3-Clause | https://github.com/niftools/nifskope |
| **BSA Browser** (`bsab`, archive reader inside the converter) | its authors (see `tool\bin\bsab\LICENSE.txt` after setup) | GPL-3.0 | bundled with the converter |
| .NET / CoreFX, SharpZipLib, Pfim, lz4.net, TextEditor.Extended | their authors | MIT and similar | texts in `tool\bin\bsab\Licenses\` after setup |
| **cx_Freeze** (packs the converter) | Marcelo Duarte, Anthony Tuininga, Computronix | PSF-style | `tool\frozen_application_license.txt` after setup |

The converter and xEdit are downloaded by the installer from their official release pages, checked against a pinned SHA-256, and kept in your own
work folder, together with their licence files. Their source code is available at the links above.

## Tools from your own game install (never copied or shipped by us)
Elrich (Elric), Archive2, the Papyrus compiler and the Creation Kit come from your own Fallout 4 / Creation Kit install
(Bethesda Game Studios / ZeniMax Media). The Fallout 3 files being converted are yours too.

## Libraries and runtimes
| Software | Team | Licence |
|---|---|---|
| Python 3 and Tcl/Tk (the window) | Python Software Foundation, Tcl/Tk community | PSF, Tcl/Tk |
| Pillow (window artwork) | Jeffrey A. Clark and contributors | HPND |
| NumPy | NumPy developers | BSD-3-Clause |
| py7zr (optional 7z fallback) | Hiroshi Miura and contributors | LGPL-2.1+ |
| PyInstaller (builds the exe) | PyInstaller team | GPL-2.0 with the bootloader exception |
| bsdtar / libarchive (unpacks the 7z with Windows' own `tar.exe`) | libarchive project / Microsoft | BSD-2-Clause |

## Games and trademarks
Fallout, Fallout 3 and Fallout 4 are trademarks of Bethesda Softworks LLC / ZeniMax Media Inc. This project is not affiliated with, endorsed by or
sponsored by them. You need your own legal copies of Fallout 3 and Fallout 4 (and the Creation Kit). No game content is included or distributed;
everything converted is built on your PC from your own files, for your personal use only.

## Artwork
The window banner (a ruined Washington DC skyline: Washington Monument, Capitol, Lincoln Memorial) is drawn in code by this project. No
Bethesda artwork, characters, logos or fonts are used.

## Thanks
To the Fallout 3 and Fallout 4 modding community, whose tools and years of documentation (the GECK and Creation Kit wikis, the xEdit
Discord, the Tale of Two Wastelands and Capital Wasteland porting efforts) made projects like this possible.

If your work is used here and is missing or credited wrongly, tell us and we will fix it straight away.
