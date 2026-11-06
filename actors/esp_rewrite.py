"""In-place record rewriting for generated plugins: replace the subrecords of chosen records and re-serialize the file with every GRUP size recomputed (no stale group sizes).
  rebuild(data, {formid: fn(subs) -> subs}, sigs={b'NPC_'}) -> bytes;  subs are (sig bytes, payload bytes) pairs; compressed records come out uncompressed."""
import struct, sys, zlib
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import sub


def raw_subs(body):
    q = 0; res = []; big = None
    while q < len(body):
        k = body[q:q + 4]; n = struct.unpack_from('<H', body, q + 4)[0]; q += 6
        if k == b'XXXX': big = struct.unpack_from('<I', body, q)[0]; q += n; continue
        if big is not None: n = big; big = None
        res.append((k, body[q:q + n])); q += n
    return res


def rebuild(data, edits, sigs):
    hdr = 24 + struct.unpack_from('<I', data, 4)[0]
    def walk(q, end):
        out = bytearray()
        while q < end:
            sig = data[q:q + 4]; size = struct.unpack_from('<I', data, q + 4)[0]
            if sig == b'GRUP':
                inner = walk(q + 24, q + size)
                out += data[q:q + 4] + struct.pack('<I', 24 + len(inner)) + data[q + 8:q + 24] + inner; q += size
            else:
                fid = struct.unpack_from('<I', data, q + 12)[0]; rec = data[q:q + 24 + size]
                if sig in sigs and fid in edits:
                    flags = struct.unpack_from('<I', data, q + 8)[0]; body = data[q + 24:q + 24 + size]
                    if flags & 0x40000: body = zlib.decompress(body[4:]); flags &= ~0x40000
                    nb = b''.join(sub(k.decode(), v) for k, v in edits[fid](raw_subs(body)))
                    rec = sig + struct.pack('<II', len(nb), flags) + data[q + 12:q + 24] + nb
                out += rec; q += 24 + size
        return out
    return bytes(data[:hdr]) + bytes(walk(hdr, len(data)))
