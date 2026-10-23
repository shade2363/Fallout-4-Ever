"""Minimal Fallout 3 BSA (v104) reader.  python bsa_extract.py <archive.bsa> list <substr> | get <path> <out>"""
import struct, sys, zlib
def open_bsa(path):
    f = open(path, 'rb'); h = f.read(36)
    magic, ver, off, flags, nfold, nfile, tfn, tfl, ftype = struct.unpack('<4sIIIIIIII', h)
    assert magic == b'BSA\0' and ver == 104
    compressed_default = bool(flags & 4); embed = bool(flags & 0x100)
    folders = []
    f.seek(36)
    for _ in range(nfold):
        hsh, cnt, o = struct.unpack('<QII', f.read(16)); folders.append((cnt, o))
    names_out = []; recs = []
    for cnt, o in folders:
        n = f.read(1)[0]; fname = f.read(n).rstrip(b'\0').decode('latin1')
        for _ in range(cnt):
            hsh, size, foff = struct.unpack('<QII', f.read(16)); recs.append([fname, size, foff])
    for r in recs:
        s = b''
        while True:
            c = f.read(1)
            if c == b'\0': break
            s += c
        r[0] = (r[0] + chr(92) + s.decode('latin1')).lower()
    return f, recs, compressed_default, embed
def get(f, rec, comp, embed):
    name, size, off = rec
    inv = bool(size & 0x40000000); size &= 0x3fffffff
    f.seek(off); d = f.read(size)
    if embed:
        n = d[0]; d = d[1 + n:]
    c = comp != inv
    if c:
        d = zlib.decompress(d[4:])
    return d
if __name__ == '__main__':
    f, recs, comp, embed = open_bsa(sys.argv[1])
    if sys.argv[2] == 'list':
        for r in recs:
            if sys.argv[3].lower() in r[0]: print(r[0])
    else:
        want = sys.argv[3].lower().replace('/', chr(92))
        for r in recs:
            if r[0] == want: open(sys.argv[4], 'wb').write(get(f, r, comp, embed)); print('wrote', r[0]); break
        else: print('not found')
