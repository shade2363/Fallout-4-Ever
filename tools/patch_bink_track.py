"""Set the id of every audio track in the header of Bink (.bik/.bk2) files, in place.
FO4 plays only the tracks whose id matches its language (vanilla videos carry tracks with ids 1..5); Fallout 3 videos have one track with id 0,
which FO4 never selects (silent movie).   python tools\\patch_bink_track.py 1 file1.bik file2.bik ..."""
import struct, sys
new_id = int(sys.argv[1])
for f in sys.argv[2:]:
    with open(f, 'r+b') as fh:
        h = fh.read(256)
        if h[:3] not in (b'BIK', b'KB2'):
            print('skip (not bink):', f); continue
        ntr = struct.unpack_from('<I', h, 40)[0]
        base = 44 + 8 * ntr                                  # max-decoded-size u32 and rate/flags u32 per track come first, then the ids
        ids = list(struct.unpack_from('<%dI' % ntr, h, base))
        if ids == [new_id] * ntr:
            print('already %d: %s' % (new_id, f)); continue
        fh.seek(base); fh.write(struct.pack('<%dI' % ntr, *([new_id] * ntr)))
        print('%s: track ids %s -> %s' % (f, ids, [new_id] * ntr))
