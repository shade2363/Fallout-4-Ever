"""Bake Fallout 3 'Enable Parent' (XESP) initial states into the converted plugin.

xConvert strips XESP from every reference, so objects that FO3 keeps disabled through an enable parent (destroyed-Megaton pieces,
quest-state variants, ...) all show at once and overlap into a mess. This script reads the SOURCE plugin, resolves each reference's
initial enabled state (own 'initially disabled' flag 0x800, or parent disabled; XESP flag bit0 inverts the parent state) and sets the
Initially Disabled record flag (0x800) on the matching converted REFR. Patches record header flags in place (no size change).

  python fix_enable_state.py --src "<FO3 Data>\Fallout3.esm" --in tool\output\Fallout3.esm --out Fallout3.state.esm
Only Fallout3.esm-owned references are handled (source index 00 -> converted 01). Scripts that enable/disable things later are not
reproduced (that needs the Papyrus quest port)."""
import argparse, struct, sys, collections
sys.path.insert(0, r'X:\__CAPITAL_WORKDIR__\navmesh')
from navlib import iter_records, subrecords

ap = argparse.ArgumentParser()
ap.add_argument('--master-src', default=None, help='Fallout3.esm source when --src is a DLC (DLC masters = Fallout3.esm only)'); ap.add_argument('--src', required=True); ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--out', required=True)
a = ap.parse_args()
def load(path, hi_shift):
    d = open(path, 'rb').read()
    out = {}
    for r in iter_records(d):
        if r.sig in ('REFR', 'ACHR', 'ACRE', 'PGRE', 'PMIS', 'PBEA', 'PFLA', 'PCBE'):
            x = None
            if r.size:
                for k, b in subrecords(d, r):
                    if k == 'XESP': x = struct.unpack_from('<IB', b, 0)
            out[r.fid] = (r.flags, x)
    return out
src = load(a.src, 0)
if a.master_src:
    # DLC: own records have source index 1 (masters: Fallout3.esm = 0); master refs the DLC does not override come from the FO3 source
    for f, v in load(a.master_src, 0).items():
        src.setdefault(f, v)

memo = {}
def disabled(f, depth=0):
    if f in memo: return memo[f]
    fl, x = src.get(f, (0, None))
    d = bool(fl & 0x800)
    if x and depth < 10 and x[0] in src:
        pd = disabled(x[0], depth + 1)
        if x[1] & 1: pd = not pd
        d = d or pd
    memo[f] = d
    return d

dc = bytearray(open(a.inp, 'rb').read())
stat = collections.Counter()
for r in iter_records(bytes(dc)):
    if r.sig != 'REFR': continue
    # converted index -> source index: Fallout3.esm: 01->00; DLC (masters Fallout4, Fallout3): 01->00 (FO3 override), 02->01 (own)
    sf = (r.fid & 0xFFFFFF) | ((((r.fid >> 24) - 1) << 24) if a.master_src else 0)
    if sf not in src: stat['no source ref'] += 1; continue
    if disabled(sf) and not (r.flags & 0x800):
        struct.pack_into('<I', dc, r.off + 8, r.flags | 0x800); stat['set initially-disabled'] += 1
    else:
        stat['unchanged'] += 1
open(a.out, 'wb').write(dc)
print(dict(stat), '->', a.out)
