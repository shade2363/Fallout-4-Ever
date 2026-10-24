"""Why a placed reference that xConvert dropped cannot be put back: the reason in words, from the source plugin's base record.

restore_refs.py / restore_dlc_refs.py used to log one opaque count ("skipped: base not converted": 6,163 in Fallout3.esm, 940 in Zeta ...).  Nearly all of those are
things Fallout 4 has no placed-reference equivalent for: editor markers (room, collision, north, radiation markers ...), ambient sound emitters (SOUN), ambient effect
meshes (dust, mist, falling rocks) and placeable water planes (PWAT; Fallout 4 has water per cell instead).  The reason is now named, so a real loss stands out.

Library: index_bases(plugin_bytes) -> {formid: (signature, editor id, model)};  reason(info, raw_base_formid) -> label"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'navmesh'))
from navlib import iter_records, subrecords          # noqa: E402

REF_LIKE = ('REFR', 'ACHR', 'ACRE', 'CELL', 'WRLD', 'LAND', 'NAVM', 'INFO', 'DIAL', 'QUST', 'NAVI', 'PGRE', 'PMIS', 'PGRD', 'PARW', 'PBEA', 'PFLA', 'PCON', 'PBAR', 'PHZD')


def index_bases(data):
    out = {}
    for r in iter_records(data):
        if r.sig in REF_LIKE:
            continue
        try:
            s = dict(subrecords(data, r))
        except Exception:
            s = {}
        out[r.fid] = (r.sig, s.get('EDID', b'').rstrip(bytes(1)).decode('latin1'), s.get('MODL', b'').rstrip(bytes(1)).decode('latin1'))
    return out


def reason(info, raw_base):
    """info = the entry of index_bases for this base (or None when the plugin has no such record)"""
    if info is None:
        return 'engine form (marker)' if (raw_base & 0xFFFFFF) < 0x800 else 'base record not found'
    sig, edid, modl = info
    e = edid.lower()
    if sig == 'STAT' and ('marker' in e or not modl):
        return 'editor marker'
    if sig == 'SOUN':
        return 'ambient sound emitter'
    if sig == 'PWAT':
        return 'placeable water plane'
    if sig == 'MSTT' and modl.lower().startswith('effects'):
        return 'ambient effect (dust, mist, rocks)'
    return 'other: %s %s' % (sig, edid)
