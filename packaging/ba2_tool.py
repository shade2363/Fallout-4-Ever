"""Read-only BA2 (BTDX) inspector/verifier for the Capital Convert packaging step. Handles GNRL and DX10 archives.

  python packaging/ba2_tool.py info    <ba2>                       header, counts, total sizes
  python packaging/ba2_tool.py list    <ba2> [substring]           names (case-insensitive substring filter)
  python packaging/ba2_tool.py verify  <ba2> --root <dir> [--sizes] <source dir> [<source dir> ...]
        every file under the source dirs (archive name = path relative to --root) must be inside the archive (and, with --sizes,
        GNRL entries must match the file size; DX10 entries must match the DDS header: width / height / mip count / DXGI format).
        Extra archive entries are reported too. Exit code 0 only when the two sets match exactly.
  python packaging/ba2_tool.py roundtrip <ba2> --root <dir> --archive2 <Archive2.exe> [--sample N] [--tmp <dir>] <source dir> [...]
        extracts the archive with Archive2 itself (independent of this reader) and compares every file (or N evenly spread ones)
        with the source: GNRL byte for byte, DX10 the pixel data after the DDS header.
  python packaging/ba2_tool.py json   <ba2>                        one-line JSON summary (used by pack_ba2.ps1)
"""
import json, os, struct, sys, zlib

DXGI = {  # legacy DDS fourcc / pixel format -> DXGI format id (only what Archive2 accepts)
    b'DXT1': 71, b'DXT3': 74, b'DXT5': 77, b'ATI1': 80, b'BC4U': 80, b'ATI2': 83, b'BC5U': 83,
}


def read_ba2(path):
    f = open(path, 'rb')
    h = f.read(24)
    magic, ver, typ, count, nameoff = struct.unpack('<4sI4sIQ', h)
    if magic != b'BTDX':
        raise SystemExit('%s: not a BTDX archive' % path)
    if ver in (2, 3):
        f.read(8)
    if ver == 3:
        f.read(4)
    recs = []
    if typ == b'GNRL':
        for _ in range(count):
            crc, ext, dcrc, flags, off, psz, usz, pad = struct.unpack('<I4sIIQIII', f.read(36))
            recs.append({'off': off, 'packed': psz, 'size': usz})
    elif typ == b'DX10':
        for _ in range(count):
            crc, ext, dcrc, unk, nch, chlen, h_, w_, mips, fmt, tile = struct.unpack('<I4sIBBHHHBBH', f.read(24))
            chunks = []
            for _c in range(nch):
                off, psz, usz, smip, emip, pad = struct.unpack('<QIIHHI', f.read(24))
                chunks.append((off, psz, usz, smip, emip))
            recs.append({'chunks': chunks, 'height': h_, 'width': w_, 'mips': mips, 'fmt': fmt,
                         'size': sum(c[2] for c in chunks), 'packed': sum(c[1] for c in chunks)})
    else:
        raise SystemExit('%s: unsupported type %r' % (path, typ))
    f.seek(nameoff)
    names = []
    for _ in range(count):
        n, = struct.unpack('<H', f.read(2))
        names.append(f.read(n).decode('latin1'))
    f.close()
    return {'version': ver, 'type': typ.decode(), 'names': names, 'recs': recs, 'bytes': os.path.getsize(path)}


def norm(p):
    return p.replace('/', '\\').lower()


def dds_info(path):
    with open(path, 'rb') as fh:
        d = fh.read(148)
    if d[:4] != b'DDS ':
        return None
    height, width = struct.unpack_from('<II', d, 12)
    mips = struct.unpack_from('<I', d, 28)[0]
    fourcc = d[84:88]
    if fourcc == b'DX10':
        fmt = struct.unpack_from('<I', d, 128)[0]
    else:
        fmt = DXGI.get(fourcc)
    return height, width, max(mips, 1), fmt


def cmd_info(a):
    b = read_ba2(a[0])
    tot = sum(r['size'] for r in b['recs'])
    print('%s: version %d, %s, %d files, %.1f MB on disk, %.1f MB unpacked' % (os.path.basename(a[0]), b['version'], b['type'], len(b['names']), b['bytes'] / 1048576, tot / 1048576))


def cmd_list(a):
    b = read_ba2(a[0])
    pat = a[1].lower() if len(a) > 1 else ''
    for n in b['names']:
        if pat in n.lower():
            print(n)


def cmd_json(a):
    b = read_ba2(a[0])
    print(json.dumps({'version': b['version'], 'type': b['type'], 'files': len(b['names']), 'bytes': b['bytes'], 'unpacked': sum(r['size'] for r in b['recs'])}))


def parse_opts(a, valued):
    """-> (positional list, {option: value or True})"""
    pos, opt, i = [], {}, 0
    while i < len(a):
        x = a[i]
        if x.startswith('--'):
            if x in valued:
                opt[x] = a[i + 1]
                i += 2
                continue
            opt[x] = True
        else:
            pos.append(x)
        i += 1
    return pos, opt


def collect(srcs, root):
    out = {}
    for src in srcs:
        for dp, dn, fn in os.walk(src):
            for x in fn:
                full = os.path.join(dp, x)
                out[norm(os.path.relpath(full, root))] = full
    return out


def cmd_verify(a):
    pos, opt = parse_opts(a, ('--root',))
    ba2, srcs = pos[0], pos[1:]
    root = opt.get('--root') or srcs[0]
    sizes = '--sizes' in opt
    b = read_ba2(ba2)
    inarch = {}
    dup = 0
    for n, r in zip(b['names'], b['recs']):
        k = norm(n)
        if k in inarch:
            dup += 1
        inarch[k] = r
    srcfiles = collect(srcs, root)
    missing = sorted(k for k in srcfiles if k not in inarch)
    extra = sorted(k for k in inarch if k not in srcfiles)
    bad = []
    if sizes:
        for k, full in srcfiles.items():
            r = inarch.get(k)
            if r is None:
                continue
            if b['type'] == 'GNRL':
                if r['size'] != os.path.getsize(full):
                    bad.append((k, 'size %d != %d' % (r['size'], os.path.getsize(full))))
            else:
                di = dds_info(full)
                if di is None:
                    bad.append((k, 'source is not a DDS'))
                    continue
                if di[3] is None:
                    bad.append((k, 'unmapped source format'))
                    continue
                if (di[0], di[1], di[2], di[3]) != (r['height'], r['width'], r['mips'], r['fmt']):
                    bad.append((k, 'dds hdr %s != archive %s' % (di, (r['height'], r['width'], r['mips'], r['fmt']))))
    print('%s [%s v%d]: archive %d entries, source %d files, missing %d, extra %d, duplicates %d, mismatched %d' % (
        os.path.basename(ba2), b['type'], b['version'], len(inarch), len(srcfiles), len(missing), len(extra), dup, len(bad)))
    for m in missing[:15]:
        print('  MISSING in archive:', m)
    for m in extra[:15]:
        print('  EXTRA in archive:', m)
    for m in bad[:15]:
        print('  MISMATCH:', m[0], m[1])
    sys.exit(0 if not (missing or extra or bad or dup) else 1)


def pixels(path):
    with open(path, 'rb') as fh:
        d = fh.read()
    if d[:4] != b'DDS ':
        return None
    return d[148:] if d[84:88] == b'DX10' else d[128:]


def same_file(a, b, chunk=1 << 22):
    if os.path.getsize(a) != os.path.getsize(b):
        return False
    with open(a, 'rb') as fa, open(b, 'rb') as fb:
        while True:
            x = fa.read(chunk)
            if not x:
                return True
            if x != fb.read(chunk):
                return False


def cmd_roundtrip(a):
    import shutil, subprocess, tempfile
    pos, opt = parse_opts(a, ('--root', '--archive2', '--sample', '--tmp'))
    ba2, srcs = pos[0], pos[1:]
    root = opt.get('--root') or srcs[0]
    exe = opt['--archive2']
    b = read_ba2(ba2)
    srcfiles = collect(srcs, root)
    keys = sorted(srcfiles)
    n = int(opt.get('--sample', 0))
    if n and n < len(keys):
        step = len(keys) / float(n)
        keys = [keys[int(i * step)] for i in range(n)]
    tmp = tempfile.mkdtemp(prefix='ba2rt_', dir=opt.get('--tmp'))
    try:
        r = subprocess.run([exe, ba2, '-extract=' + tmp, '-quiet'], capture_output=True, text=True)
        extracted = collect([tmp], tmp)
        bad, miss = [], []
        for k in keys:
            e = extracted.get(k)
            if e is None:
                miss.append(k)
                continue
            if b['type'] == 'GNRL':
                if not same_file(srcfiles[k], e):
                    bad.append(k)
            else:
                p1, p2 = pixels(srcfiles[k]), pixels(e)
                if p1 is None or p2 is None or p1 != p2:
                    bad.append(k)
        print('%s roundtrip (Archive2 -extract exit %d): compared %d of %d source files, %d not extracted, %d differ' % (
            os.path.basename(ba2), r.returncode, len(keys), len(srcfiles), len(miss), len(bad)))
        for m in miss[:10]:
            print('  NOT EXTRACTED:', m)
        for m in bad[:10]:
            print('  DIFFERS:', m)
        sys.exit(0 if not (miss or bad) else 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    {'info': cmd_info, 'list': cmd_list, 'verify': cmd_verify, 'roundtrip': cmd_roundtrip, 'json': cmd_json}[sys.argv[1]](sys.argv[2:])
