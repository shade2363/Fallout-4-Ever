"""Test helper: write an empty plugin (TES4 header only) with masters Fallout4.esm + Fallout3.esm.   python make_empty_plugin.py out.esp"""
import struct, sys
sys.path.insert(0, r'X:\__CAPITAL_WORKDIR__\navmesh')
from navlib import sub, record
hs = [sub('HEDR', struct.pack('<fII', 1.0, 0, 0x800)), sub('CNAM', b'x' + bytes(1))]
for m in ('Fallout4.esm', 'Fallout3.esm'):
    hs += [sub('MAST', m.encode() + bytes(1)), sub('DATA', bytes(8))]
open(sys.argv[1], 'wb').write(record('TES4', 0, hs, ver=131))
print('wrote', sys.argv[1])
