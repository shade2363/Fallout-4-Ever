"""Bethesda plugin helpers for the FO3 -> FO4 navmesh converter (pure python, standard library only).

Reads plugins (groups, records, subrecords, zlib-compressed records) and writes records/groups/subrecords.
Nothing here modifies an input file.
"""
import struct
import zlib

GRUP = b'GRUP'


class Rec:
    __slots__ = ('sig', 'off', 'size', 'flags', 'fid', 'chain', 'vc', 'ver')

    def __init__(self, sig, off, size, flags, fid, chain, vc, ver):
        self.sig, self.off, self.size, self.flags, self.fid, self.chain, self.vc, self.ver = sig, off, size, flags, fid, chain, vc, ver


def iter_records(data, start=None):
    """Yield Rec for every non-group record. chain = tuple of (label_bytes, group_type) for the enclosing groups."""
    n = len(data)
    if start is None:
        start = 24 + struct.unpack_from('<I', data, 4)[0]
    stack = []  # (end_offset, chain_tuple)
    q = start
    chain = ()
    while q < n:
        while stack and q >= stack[-1][0]:
            stack.pop()
        chain = stack[-1][1] if stack else ()
        sig = data[q:q + 4]
        size = struct.unpack_from('<I', data, q + 4)[0]
        if sig == GRUP:
            label = data[q + 8:q + 12]
            gtype = struct.unpack_from('<I', data, q + 12)[0]
            stack.append((q + size, chain + ((label, gtype),)))
            q += 24
            continue
        flags, fid, vc, ver = struct.unpack_from('<IIIH', data, q + 8)
        yield Rec(sig.decode('latin1'), q, size, flags, fid, chain, vc, ver)
        q += 24 + size


def record_bytes(data, rec):
    return data[rec.off:rec.off + 24 + rec.size]


def subrecords(data, rec):
    """Return list of (sig, bytes) for a record, decompressing if needed and honouring XXXX size extension."""
    body = data[rec.off + 24:rec.off + 24 + rec.size]
    if rec.flags & 0x40000:
        body = zlib.decompress(body[4:])
    out = []
    p = 0
    ext = None
    while p < len(body):
        s = body[p:p + 4].decode('latin1')
        sz = struct.unpack_from('<H', body, p + 4)[0]
        if s == 'XXXX':
            ext = struct.unpack_from('<I', body, p + 6)[0]
            p += 10
            continue
        if ext is not None:
            sz = ext
            ext = None
        out.append((s, body[p + 6:p + 6 + sz]))
        p += 6 + sz
    return out


def plugin_header(data):
    """Return (masters list, flags)."""
    hdr_size = struct.unpack_from('<I', data, 4)[0]
    flags = struct.unpack_from('<I', data, 8)[0]
    masters = []
    p = 24
    while p < 24 + hdr_size:
        s = data[p:p + 4]
        sz = struct.unpack_from('<H', data, p + 4)[0]
        if s == b'MAST':
            masters.append(data[p + 6:p + 6 + sz].rstrip(b'\0').decode('latin1'))
        p += 6 + sz
    return masters, flags


# ---------------------------------------------------------------- writers
def sub(sig, payload):
    """Encode one subrecord, using the XXXX size extension when the payload exceeds 65535 bytes."""
    if len(payload) > 0xFFFF:
        return b'XXXX' + struct.pack('<HI', 4, len(payload)) + sig.encode('latin1') + struct.pack('<H', 0) + payload
    return sig.encode('latin1') + struct.pack('<H', len(payload)) + payload


def record(sig, fid, subs, flags=0, vc=0, ver=131, vc2=0):
    body = b''.join(subs)
    return sig.encode('latin1') + struct.pack('<IIIIHH', len(body), flags, fid, vc, ver, vc2) + body


def group(label, gtype, payload, stamp=0):
    if isinstance(label, int):
        label = struct.pack('<I', label)
    return GRUP + struct.pack('<I', 24 + len(payload)) + label + struct.pack('<IHHI', gtype, stamp, 0, 0) + payload
