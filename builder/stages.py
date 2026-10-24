"""The build, as an ordered list of stages.  Every stage lists the pipeline steps to run (existing project scripts, unchanged), the inputs it
needs ('requires', {wd}=work folder, {fo4}, {fo3}=FO3 Data) and the files that prove it finished ('produces').

Source of the order: README.md "Run order (rebuilding from scratch)" and install-output.ps1.  Stages marked  unverified  were NOT run on a clean
machine by the builder yet: they work in the original working tree, but depend on intermediate files from earlier manual sessions (lab\\...).
The first run on a clean PC is expected to stop at such a stage with a precise message; that is what the resume state is for.
"""

# what is copied into the work folder (relative to the project root / payload folder)
PAYLOAD_DIRS = [
    'builder', 'worldfix', 'actors', 'ai', 'audio', 'dialogue', 'quests', 'items', 'navmesh', 'perks', 'skills', 'objscripts', 'npcfaces',
    'look', 'voice', 'packaging', 'tests', 'tools', 'scripts/src', 'scripts/src_obj', 'scripts/compiler', 'scripts/f4se_stub',
    'tool/build', 'tool/bin', 'tool/xedit', 'tool/src', 'tool/src-xconvert',
    'ui',
]
PAYLOAD_FILES = [
    'setup.ps1', 'convert-fo3-assets.ps1', 'install-output.ps1', 'rename-master.ps1', 'build-actor-map.ps1',
    'audit-fo3-fo4.ps1', 'tools-launch-fo4.ps1', 'tools-send-keys.ps1', 'tools-test-plugins.ps1', 'README.md', 'ROADMAP.md',
    'tool/LICENSE', 'tool/README.md',
]
# folders never copied (generated / extracted Bethesda content produced by the build itself)
PAYLOAD_SKIP_DIRS = ['ui/fo3', 'ui/fo4', 'ui/fo4tex', 'ui/fo4mesh', 'ui/out', 'ui/preview', 'ui/bink/__pycache__', 'tool/build/xedit_converter/data/_cache']
# never copied (large, generated or Bethesda content)
PAYLOAD_SKIP_EXT = {'.pyc', '.dds', '.nif', '.ba2', '.bsa', '.esm', '.esp', '.esl', '.bik', '.bk2', '.png', '.jpg', '.wav', '.ogg', '.mp3', '.fuz', '.xwm', '.lip'}
# text files whose embedded machine paths are rewritten while staging
REWRITE_EXT = {'.py', '.ps1', '.bat', '.cmd', '.psc', '.tmpl', '.txt', '.md', '.json', '.ini', '.cfg', '.sh', '.csv', '.pas'}

FO3_PLUGINS = ['Fallout3', 'Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta']

STAGES = [
    dict(id='01-prepare', title='Prepare folders, converter and Creation Kit settings', eta='1 min',
         steps=[('call', 'prepare')], produces=['{wd}/tool/build/xedit_converter/xConvert.exe']),
    dict(id='02-assets', title='Convert Fallout 3 meshes, textures and materials (BSA -> BA2)', eta='2-4 h',
         steps=[('ps', 'convert-fo3-assets.ps1', '-Plugins', ','.join(FO3_PLUGINS))],
         requires=['{fo3}/Fallout - Meshes.bsa', '{fo4}/Tools/Archive2/Archive2.exe', '{fo4}/Tools/Elric/Elrich.exe'],
         produces=['{wd}/tool/output/Fallout3 - Main.ba2']),
    dict(id='03-plugins', title='Convert the Fallout 3 plugins (xConvert, six plugins)', eta='1-2 h', unverified=True,
         steps=[('call', 'convert_plugins')], produces=['{wd}/lab/Data/Fallout3.esm']),
    dict(id='04-worldfix', title='World repairs (stub cells, refs, regions, enable state, interior lighting)', eta='20 min', unverified=True,
         steps=[('call', 'seed_worldfix'), ('ps', 'worldfix/apply-fixes.ps1')], requires=['{wd}/lab/Data/Fallout3.esm'], produces=['{wd}/tool/output/Fallout3.esm']),
    dict(id='05-lod', title='Terrain LOD settings', eta='1 min', steps=[('call', 'lod_settings')], produces=['{wd}/tool/output/LODSettings']),
    dict(id='06-actors', title='Actors (CapitalActors.esp): export, map, place, name', eta='30-60 min', unverified=True,
         steps=[('call', 'actors')], produces=['{wd}/tool/output/CapitalActors.esp']),
    dict(id='06b-dlc-actors', title='DLC actors (CapitalDLCActors.esp): map, place, name, faces', eta='3 min (+ the Creation Kit FaceGen bake: npcfaces/ck_export_dlc.ps1, game closed)', unverified=True, optional=True,
         steps=[('py', 'actors/dlc_actor_map.py'), ('py', 'actors/build_dlc_actors.py'), ('py', 'npcfaces/apply_faces.py', '--plugin', '{wd}/tool/output/CapitalDLCActors.esp'),
                ('py', 'npcfaces/fix_sex.py', '--plugin', '{wd}/tool/output/CapitalDLCActors.esp')], requires=['{wd}/tool/output/Fallout3.esm'], produces=['{wd}/tool/output/CapitalDLCActors.esp']),
    dict(id='07-items', title='Items, terminals and containers (CapitalItems.esp)', eta='1 min',
         steps=[('py', 'items/build_items.py')], produces=['{wd}/tool/output/CapitalItems.esp']),
    dict(id='08-quests', title='Quests and driver scripts (CapitalQuests.esp)', eta='3 min',
         steps=[('py', 'quests/build_quests.py'), ('ps', 'quests/compile_all.ps1')], produces=['{wd}/tool/output/CapitalQuests.esp']),
    dict(id='09-dialogue', title='Dialogue (CapitalDialogue.esp)', eta='1 min',
         steps=[('py', 'dialogue/build_all_dialogue.py'), ('ps', 'dialogue/compile_tif.ps1')], produces=['{wd}/tool/output/CapitalDialogue.esp']),
    dict(id='09b-dlc-dialogue', title='DLC dialogue (CapitalDLCDialogue.esp; needs the DLC actors + DLC quests)', eta='1 min', unverified=True, optional=True,
         steps=[('py', 'dialogue/dlc_merge.py'), ('py', 'dialogue/build_all_dialogue.py', '--dlc'), ('ps', 'dialogue/compile_tif.ps1')], requires=['{wd}/tool/output/CapitalDLCActors.esp'], produces=['{wd}/tool/output/CapitalDLCDialogue.esp']),
    dict(id='09c-dlc-ai', title='DLC AI packages, outfits, voice types (CapitalDLCAI.esp)', eta='1 min', unverified=True, optional=True,
         steps=[('py', 'dialogue/dlc_merge.py'), ('py', 'ai/build_ai.py', '--dlc')], requires=['{wd}/tool/output/CapitalDLCActors.esp'], produces=['{wd}/tool/output/CapitalDLCAI.esp']),
    dict(id='10-navmesh', title='Navmesh (CapitalNavmesh.esp)', eta='15 min', unverified=True,
         steps=[('py', 'navmesh/convert_navmesh.py', '--src', '{fo3}/Fallout3.esm', '--conv', '{wd}/tool/output/Fallout3.esm', '--out', '{wd}/tool/output/CapitalNavmesh.esp', '--vanilla-navi', '{fo4}/Data/Fallout4.esm')], produces=['{wd}/tool/output/CapitalNavmesh.esp']),
    dict(id='10b-dlc-navmesh', title='DLC navmesh (CapitalNavmeshDLC.esp: DLC meshes + the whole NAVI index)', eta='1 min', unverified=True, optional=True,
         steps=[('py', 'navmesh/build_dlc_navmesh.py')], requires=['{wd}/tool/output/CapitalNavmesh.esp'], produces=['{wd}/tool/output/CapitalNavmeshDLC.esp']),
    dict(id='11-extras', title='Skills, perks, AI packages, object scripts, faces', eta='30 min', unverified=True, optional=True,
         steps=[('call', 'extras')], produces=['{wd}/tool/output/F3_Skills.esp']),
    dict(id='12-fixes', title='Crash fixes (CapitalFixes.esp)', eta='1 min',
         steps=[('py', 'worldfix/fix_crashers.py'), ('py', 'worldfix/lock_terminals.py')], produces=['{wd}/tool/output/CapitalFixes.esp']),
    dict(id='13-furniture', title='Furniture markers (CapitalFurniture.esp)', eta='2 min',
         steps=[('call', 'furn_keywords'), ('py', 'worldfix/furn_markers.py'), ('py', 'worldfix/build_furniture.py')], produces=['{wd}/tool/output/CapitalFurniture.esp']),
    dict(id='14-scripts', title='Attach the converted object scripts (CapitalScripts.esp)', eta='2 min',
         steps=[('call', 'sounds_placeholder'), ('py', 'objscripts/attach.py')], produces=['{wd}/tool/output/CapitalScripts.esp']),
    dict(id='15-meshes', title='Loose meshes: animated doors, skipped meshes, terminal models', eta='15 min',
         steps=[('call', 'meshes')], produces=['{wd}/tool/output/loose']),
    dict(id='16-faces', title='NPC faces (head parts)', eta='5 min', optional=True,
         steps=[('call', 'faces')], produces=['{wd}/lab/fo4_headparts.json']),
    dict(id='17-ui', title='Main menu and character editor (Gene Projector)', eta='1 min',
         steps=[('call', 'ui')], produces=['{wd}/tool/output/menu/Interface/LooksMenu.swf']),
    dict(id='17b-pack', title='Pack loose actors / items / textures into BA2 archives (staged, nothing installed)', eta='10-20 min', optional=True,
         steps=[('ps', 'packaging/pack_ba2.ps1')], produces=['{wd}/tool/output/ba2-stage/stage.json']),
    dict(id='18-install', title='Install into Fallout 4 (plugins, archives, scripts, F4SE, menu)', eta='10 min', unverified=True,
         steps=[('ps', 'install-output.ps1'), ('ps', 'capital-profile.ps1', '-Capital')],
         requires=['{wd}/tool/output/Fallout3.esm'], produces=['{fo4}/Data/Fallout3.esm']),
]


# ---- demo release: world + actors + navmesh only (the full port's other stages stay in the dev tree) ----------------------------------------
DEMO_STAGES = ['01-prepare', '02-assets', '03-plugins', '04-worldfix', '05-lod', '06-actors', '10-navmesh', '12-fixes', '15-meshes', '18-install']
STAGES = [s for s in STAGES if s['id'] in DEMO_STAGES]
PAYLOAD_DIRS = ['builder', 'worldfix', 'actors', 'navmesh', 'packaging', 'tool/xedit/Edit Scripts']
PAYLOAD_FILES = ['convert-fo3-assets.ps1', 'rename-master.ps1', 'build-actor-map.ps1', 'install-output.ps1',
                 'tools/make_blank_bik.py', 'tools/patch_bink_track.py', 'tests/crashers.txt', 'CREDITS.md']      # install-output.ps1 patches the FO3 videos with these

# DLC worlds: put back the markers / map markers / caps that xConvert drops from the five DLC plugins (not part of apply-fixes.ps1)
for _s in STAGES:
    if _s['id'] == '04-worldfix':
        _s['steps'] = list(_s['steps']) + [('py', 'worldfix/restore_dlc_refs.py', '--all')]

# the demo installs with install-output.ps1 only: capital-profile.ps1 (the dev load-order switcher) is not part of it
for _s in STAGES:
    if _s['id'] == '18-install':
        _s['steps'] = [st for st in _s['steps'] if st[1] != 'capital-profile.ps1']

# New Game start: outside Vault 101 with the Escape! quest completed (start/build_start.py builds CapitalStart.esp and compiles two scripts with your Creation Kit compiler)
_start = dict(id='16-start', title='New Game start: outside Vault 101, Escape! completed (CapitalStart.esp)', eta='1 min',
              steps=[('py', 'start/build_start.py', '--conv', '{wd}/tool/output/Fallout3.esm', '--fo4', '{fo4}', '--out', '{wd}/tool/output/CapitalStart.esp',
                      '--src', '{wd}/scripts/src', '--scripts-out', '{wd}/scripts/out', '--special', '{special}')],         # {special}: screen (default) or default, see --no-special-screen
              requires=['{wd}/tool/output/Fallout3.esm', '{fo4}/Papyrus Compiler/PapyrusCompiler.exe'],
              produces=['{wd}/tool/output/CapitalStart.esp', '{wd}/scripts/out/CapStartDemo.pex'])
STAGES.insert([_s['id'] for _s in STAGES].index('18-install'), _start)
PAYLOAD_DIRS = PAYLOAD_DIRS + ['start']
