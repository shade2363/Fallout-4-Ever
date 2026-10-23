"""Extract/list files of a general (GNRL) BA2 without unpacking everything.
  python ba2_extract.py <archive.ba2> list <substring>            list names containing substring (case-insensitive)
  python ba2_extract.py <archive.ba2> get <exact path> <out file> extract one file"""
import struct, sys, zlib
def open_ba2(path):
    f = open(path, 'rb'); h = f.read(24)
    magic, ver, typ, count, nameoff = struct.unpack('<4sI4sIQ', h)
    assert magic == b'BTDX' and typ == b'GNRL', (magic, typ)
    recs = []
    f.seek(24)
    for _ in range(count):
        crc, ext, dcrc, flags, off, psz, usz, pad = struct.unpack('<I4sIIQIII', f.read(36)); recs.append((off, psz, usz))
    f.seek(nameoff); names = []
    for _ in range(count):
        n, = struct.unpack('<H', f.read(2)); names.append(f.read(n).decode('latin1'))
    return f, names, recs
if __name__ == '__main__':
    f, names, recs = open_ba2(sys.argv[1])
    if sys.argv[2] == 'list':
        for n in names:
            if sys.argv[3].lower() in n.lower(): print(n)
    else:
        norm = lambda s: s.lower().replace(chr(92), '/')
        want = norm(sys.argv[3])
        for n, (off, psz, usz) in zip(names, recs):
            if norm(n) == want:
                f.seek(off); d = f.read(psz or usz); d = zlib.decompress(d) if psz else d
                open(sys.argv[4], 'wb').write(d); print('wrote', len(d), n); break
        else: print('not found')
