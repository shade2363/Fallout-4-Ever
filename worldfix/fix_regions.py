"""Repair converted REGN (region) records in place of dropping them.

xConvert writes RDAT as 6 bytes (type u32, flags u8, priority u8); Fallout 4 expects 8 (adds 2 unused bytes), and it leaves a stray
1-byte ICON subrecord in some regions. With the malformed regions loaded, the game silently refuses every travel into the Wasteland
from another worldspace (door, coc, FastTravel), only the first world loaded at startup works.

  python fix_regions.py --in Fallout3.esm --out Fallout3.regfix.esm
Rewrites the top-level REGN group only; everything else is copied byte for byte."""
import argparse, struct, zlib
ap = argparse.ArgumentParser()
ap.add_argument('--in', dest='inp', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--clear-border', action='store_true', help='clear the Border Region record flag (0x40); FO4 treats it as the map edge and refuses travel into it')
ap.add_argument('--types', default='all', help='RDAT data types to keep: comma list of 2 objects,3 weather,4 map,5 land,6 grass,7 sound; or all/none')
a = ap.parse_args()
d = open(a.inp, 'rb').read()

def fix_record(rec):
    sig, size, flags, fid, vc, ver, vc2 = struct.unpack_from('<4sIIIIHH', rec, 0)
    assert not (flags & 0x40000), 'compressed REGN'
    body = rec[24:]
    out = []; p = 0; changed = False; ext = None; cur = None
    keep_types = None if a.types == 'all' else ({int(x) for x in a.types.split(',') if x.strip()} if a.types != 'none' else set())
    while p < len(body):
        s = body[p:p + 4]; sz = struct.unpack_from('<H', body, p + 4)[0]
        if s == b'XXXX':
            ext = struct.unpack_from('<I', body, p + 6)[0]; out.append(body[p:p + 10]); p += 10; continue
        real = ext if ext is not None else sz
        ext = None
        payload = body[p + 6:p + 6 + real]
        if s == b'RDAT':
            cur = struct.unpack_from('<I', payload, 0)[0]
        if keep_types is not None and s in (b'RDAT', b'RDOT', b'RDWT', b'RDMP', b'RDGS', b'RDSA', b'RDMO', b'ANAM', b'RDMD', b'RDSD') and cur not in keep_types:
            changed = True; p += 6 + real; continue
        if s == b'RDAT' and real == 6:
            payload = payload + b'\x00\x00'; changed = True
        elif s == b'ICON':
            changed = True; p += 6 + real; continue
        out.append(s + struct.pack('<H', len(payload)) + payload)
        p += 6 + real
    nb = b''.join(out)
    if a.clear_border and (flags & 0x40):
        flags &= ~0x40; changed = True
    return struct.pack('<4sIIIIHH', sig, len(nb), flags, fid, vc, ver, vc2) + nb, changed

q = 24 + struct.unpack_from('<I', d, 4)[0]
parts = [d[:q]]; nrec = nfix = 0
while q < len(d):
    size = struct.unpack_from('<I', d, q + 4)[0]
    if d[q:q + 4] == b'GRUP' and d[q + 8:q + 12] == b'REGN':
        kept = []; p = q + 24
        while p < q + size:
            rs = struct.unpack_from('<I', d, p + 4)[0]
            rec, ch = fix_record(d[p:p + 24 + rs])
            kept.append(rec); nrec += 1; nfix += ch
            p += 24 + rs
        payload = b''.join(kept)
        parts.append(d[q:q + 4] + struct.pack('<I', 24 + len(payload)) + d[q + 8:q + 24] + payload)
    else:
        parts.append(d[q:q + size])
    q += size
open(a.out, 'wb').write(b''.join(parts))
print('%d REGN records, %d repaired -> %s' % (nrec, nfix, a.out))
