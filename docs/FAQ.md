# FAQ

**Is this legal?**
The program contains no Bethesda content. It converts files from *your own* copies of Fallout 3 and Fallout 4 on *your* PC, for personal use, and you are not allowed to share
the result. We are not lawyers and this is not legal advice; see [LEGAL.md](LEGAL.md).

**What works in the demo?**
The Capital Wasteland and the five DLC worlds load in Fallout 4, with converted terrain, buildings, interiors and doors; about 4,260 NPCs and creatures placed where they stood
in Fallout 3 (including 300+ named characters as stand-in settlers); 7,198 navmeshes so they can walk and chase; terminal models and terminal locks; crash fixes.

**Where does New Game start?**
Right outside Vault 101 with the Pip-Boy, the quest *Escape!* already completed, then the character editor and SPECIAL screen. It replaces Fallout 4's own intro
script while the mod is installed; uninstalling brings the normal start back. Details: [SCRIPTS.md](SCRIPTS.md).

**New Game asks "Creations are currently loaded ... Achievements are disabled". Is that normal?**
Yes: Fallout 4 shows that for any modded game. Press Enter to continue.

**What does not work yet?**
Quests, dialogue and voice, music and radio, weather and lighting, NPC faces, perks and skills, scripted set pieces, and the Fallout 3 character creation. It is a world to explore.

**Will it work with my mods?**
It is meant for a clean setup. It adds plugins (`Fallout3.esm`, the DLC esms, `CapitalActors.esp`, `CapitalNavmesh.esp`, `CapitalFixes.esp`) and some loose files. Mods that change
the same cells or the load order may conflict. Test on a copy of your saves.

**Will it break my existing saves?**
Adding plugins to a save and then removing them can damage that save (normal for any mod that adds worlds). Use a separate profile or new saves, and see the compatibility line
on every update.

**Does it need F4SE?**
No, not for the demo.

**Why does it take hours?**
It converts about 14,000 meshes and thousands of textures and 660,000 world records. It only has to do the long part once; updates reuse it.

**Can I move the work folder or delete it afterwards?**
After the install the game does not need the work folder. Keep it if you want fast updates; delete it to free 100+ GB (a later update then rebuilds from the start).

**Does it phone home?**
No. It only connects to the internet to download the two tools the first time and when you press *Check for updates*.

**Is the update safe?**
Updates are signed with a key that is built into the program, and checked for size and fingerprint. See [UPDATE.md](UPDATE.md).

**Fallout 3 from GOG or Epic?**
The program looks for them. GOG and Epic detection is built but only tested with simulated installs so far; if it is not found, use **Browse**.

**Game Pass / Microsoft Store Fallout 4?**
Not supported (those installs cannot load extra plugins reliably). Use the Steam version.

**Where do I report problems?**
On the project's GitHub *Issues* page; attach `builder.log` from your work folder.
