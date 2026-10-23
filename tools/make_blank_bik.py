"""Cut the first N frames out of a Bink 1 (.bik) file -> a tiny but valid movie (FO4 needs a REAL movie for its new-game movie call: a missing file hangs the New Game load).
  python tools/make_blank_bik.py "<FO3>\\Data\\Video\\1 year later.bik" "<FO4>\\Data\\Video\\F3Blank.bik" [frames=2] [audio track id=1]
Bink header: sig, size-8, frames, largest frame, frames again, w, h, fps num/den, flags, tracks | per track: max decoded size, rate+flags, id | frame table (frames+1 u32, bit 0 = key frame) | frames."""
import struct, sys
src, dst = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 2
tid = int(sys.argv[4]) if len(sys.argv) > 4 else 1
d = open(src, 'rb').read()
assert d[:3] == b'BIK', 'not a Bink 1 file'
frames = struct.unpack_from('<I', d, 8)[0]
ntr = struct.unpack_from('<I', d, 40)[0]
tab = 44 + 12 * ntr
offs = list(struct.unpack_from('<%dI' % (frames + 1), d, tab))
first = offs[0] & ~1
new_tab_len = 4 * (n + 1)
new_first = tab + new_tab_len
delta = new_first - first
noffs = [((o & ~1) + delta) | (o & 1) for o in offs[:n + 1]]
data = d[first:offs[n] & ~1]
sizes = [(offs[i + 1] & ~1) - (offs[i] & ~1) for i in range(n)]
out = bytearray(d[:tab])
struct.pack_into('<I', out, 8, n); struct.pack_into('<I', out, 16, n)
struct.pack_into('<I', out, 12, max(sizes))
for t in range(ntr): struct.pack_into('<I', out, 44 + 8 * ntr + 4 * t, tid)
out += struct.pack('<%dI' % (n + 1), *noffs) + data
struct.pack_into('<I', out, 4, len(out) - 8)
open(dst, 'wb').write(out)
print('wrote %s: %d frames, %d bytes (source had %d frames, %d bytes), audio track ids %d' % (dst, n, len(out), frames, len(d), tid))
