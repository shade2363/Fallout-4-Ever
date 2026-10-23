"""Copy a tree of DDS textures into a staging tree with Archive2-compatible headers (the pixel data is never touched).

Archive2 (-format=DDS) silently SKIPS every DDS whose format it does not accept ("contains features not supported by the archiver"). Our converted loose
textures use BC5_TYPELESS (DXGI 82) for all normal / specular maps, which the engine reads fine as a loose file but Archive2 refuses. This copies each file with
  * DX10 header, typeless BCn / RGBA format      -> the _UNORM twin (82 -> 83, 79 -> 80, 76 -> 77, 73 -> 74, 70 -> 71, 27 -> 28, 90 -> 91)
  * DX10 header written with arraySize 0 (and miscFlags2 1: the two fields swapped, as our converters did) -> arraySize 1, miscFlags2 0
  * legacy FourCC header with ATI1 / ATI2 / BC4U / BC5U -> DX10 header (BC4_UNORM 80 / BC5_UNORM 83); legacy DXT1/3/5 and DX10 UNORM files are copied as they are.
Only the 4-byte format field (or the 20-byte DX10 extension) changes; the mip chain bytes after the header are identical (checked per file).

  python packaging/stage_dds.py <src dir> <dst dir> [--strip <prefix dir>]    (relative layout below <src dir> is kept; <dst dir> is created)
  python packaging/stage_dds.py --check <src dir> <dst dir>                   re-verify an existing staging tree (same file set, same pixel bytes)
Prints a summary line: files, converted, unchanged, unsupported (the unsupported list is printed and the exit code is 1).
"""
import os, struct, sys

TYPELESS = {82: 83, 79: 80, 76: 77, 73: 74, 70: 71, 27: 28, 90: 91, 44: 45, 33: 34}   # typeless -> unorm
OK_DXGI = {71, 72, 74, 75, 77, 78, 80, 81, 83, 84, 87, 88, 91, 28, 29, 61, 98, 99, 95, 96, 10, 2}   # formats Archive2 / the engine take as they are
LEGACY = {b'ATI1': 80, b'BC4U': 80, b'ATI2': 83, b'BC5U': 83}


def split(buf):
    """-> (header bytes, pixel bytes, fourcc, dxgi or None)"""
    if buf[:4] != b'DDS ' or len(buf) < 128:
        return None
    fourcc = buf[84:88]
    if fourcc == b'DX10':
        return buf[:148], buf[148:], fourcc, struct.unpack_from('<I', buf, 128)[0]
    return buf[:128], buf[128:], fourcc, None


def convert(buf):
    """-> (new bytes or None when unsupported, what) ; what in 'same', 'typeless', 'legacy'"""
    s = split(buf)
    if s is None:
        return None, 'not a DDS'
    hdr, pix, fourcc, dxgi = s
    if dxgi is not None:
        h = bytearray(hdr)
        changed = False
        if dxgi in TYPELESS:
            struct.pack_into('<I', h, 128, TYPELESS[dxgi])
            changed = True
        # DX10 extension = (format, resourceDimension, miscFlag, arraySize, miscFlags2). Our converted textures were written with arraySize 0 / miscFlags2 1
        # (the last two swapped): Archive2 refuses arraySize 0, the engine does not care.
        array_size = struct.unpack_from('<I', h, 140)[0]
        misc2 = struct.unpack_from('<I', h, 144)[0]
        if array_size == 0:
            struct.pack_into('<I', h, 140, 1)
            changed = True
        if array_size == 0 and misc2 == 1:
            struct.pack_into('<I', h, 144, 0)
        return (bytes(h) + pix, 'fixed') if changed else (buf, 'same')
    if fourcc in LEGACY:
        h = bytearray(hdr)
        # pixel format: dwFlags = FOURCC, fourcc = DX10 ; then the 20 byte DX10 extension (format, TEXTURE2D=3, miscFlag 0, arraySize 1, miscFlags2 0)
        h[84:88] = b'DX10'
        ext = struct.pack('<IIIII', LEGACY[fourcc], 3, 0, 1, 0)
        return bytes(h) + ext + pix, 'legacy'
    if fourcc in (b'DXT1', b'DXT3', b'DXT5'):
        return buf, 'same'
    return None, 'unsupported FourCC %r' % fourcc


def walk(base):
    for dp, dn, fn in os.walk(base):
        for f in fn:
            full = os.path.join(dp, f)
            yield full, os.path.relpath(full, base)


def stage(src, dst):
    n = same = conv = 0
    bad = []
    for full, rel in walk(src):
        n += 1
        buf = open(full, 'rb').read()
        if not rel.lower().endswith('.dds'):
            bad.append((rel, 'not a .dds'))
            continue
        out, what = convert(buf)
        if out is None:
            bad.append((rel, what))
            continue
        # pixel data must be identical
        a, b = split(buf), split(out)
        assert a[1] == b[1], rel
        target = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'wb') as fh:
            fh.write(out)
        if what == 'same':
            same += 1
        else:
            conv += 1
    return n, conv, same, bad


def check(src, dst):
    ok = bad = 0
    s_files = {rel.lower(): full for full, rel in walk(src)}
    d_files = {rel.lower(): full for full, rel in walk(dst)}
    missing = sorted(set(s_files) - set(d_files))
    extra = sorted(set(d_files) - set(s_files))
    for k, full in s_files.items():
        if k not in d_files:
            continue
        a = split(open(full, 'rb').read())
        b = split(open(d_files[k], 'rb').read())
        if a is None or b is None or a[1] != b[1]:
            bad += 1
        else:
            ok += 1
    return ok, bad, missing, extra


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--check':
        ok, bad, missing, extra = check(a[1], a[2])
        print('stage check: %d identical pixel data, %d differing, %d missing, %d extra' % (ok, bad, len(missing), len(extra)))
        sys.exit(0 if not (bad or missing or extra) else 1)
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    n, conv, same, bad = stage(a[0], a[1])
    print('stage_dds: %d files, %d header-converted, %d copied unchanged, %d unsupported' % (n, conv, same, len(bad)))
    for rel, why in bad[:20]:
        print('  UNSUPPORTED', rel, why)
    sys.exit(1 if bad else 0)
