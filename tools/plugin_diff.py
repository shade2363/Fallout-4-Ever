"""Record-level comparison of two builds of the same plugins.

  python tools/plugin_diff.py A_DIR B_DIR [plugin ...] [--show N]

For every plugin present in both folders: record counts per type, records only in A / only in B, records present in both whose content differs
(grouped by type, with the first differing subrecord types).  Used to compare a clean sandbox build against the dev build.
"""
import argparse, collections, hashlib, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'navmesh'))
from navlib import iter_records, subrecords


def load(path):
    d = open(path, 'rb').read()
    recs = {}
    for r in iter_records(d):
        subs = subrecords(d, r)
        hh = hashlib.sha1()
        hh.update(r.sig.encode() if isinstance(r.sig, str) else r.sig)
        hh.update(r.flags.to_bytes(4, 'little'))
        for k, b in subs:
            hh.update(k.encode() if isinstance(k, str) else k)
            hh.update(bytes(b))
        recs[(r.sig if isinstance(r.sig, str) else r.sig.decode(), r.fid)] = (hh.hexdigest(), [k if isinstance(k, str) else k.decode() for k, _ in subs], len(subs),
                                                                              [(k, hashlib.sha1(bytes(b)).digest()) for k, b in subs], r.flags)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('plugins', nargs='*')
    ap.add_argument('--show', type=int, default=8)
    a = ap.parse_args()
    names = a.plugins or sorted(set(f for f in os.listdir(a.a) if f.lower().endswith(('.esm', '.esp'))) & set(os.listdir(a.b)))
    for n in names:
        A, B = load(os.path.join(a.a, n)), load(os.path.join(a.b, n))
        only_a, only_b = sorted(set(A) - set(B)), sorted(set(B) - set(A))
        both = set(A) & set(B)
        diff = sorted(k for k in both if A[k][0] != B[k][0])
        print('== %s: A=%d records, B=%d records, only A=%d, only B=%d, changed=%d, identical=%d' % (n, len(A), len(B), len(only_a), len(only_b), len(diff), len(both) - len(diff)))
        for label, lst in (('only in A', only_a), ('only in B', only_b)):
            c = collections.Counter(k[0] for k in lst)
            if c:
                print('   %s by type: %s' % (label, ', '.join('%s %d' % kv for kv in c.most_common(12))))
                for k in lst[:a.show]:
                    print('      %s %08X' % (k[0], k[1]))
        why = collections.Counter()                      # (record type, what differs) over all changed records
        for k in diff:
            ha, hb = A[k][3], B[k][3]
            da, db = collections.Counter(ha), collections.Counter(hb)
            sigs = sorted({s for s, _ in (da - db).keys()} | {s for s, _ in (db - da).keys()})
            if A[k][4] != B[k][4]:
                sigs.append('flags')
            why[(k[0], '+'.join(sigs) or 'order')] += 1
        if why:
            print('   what differs (record type: subrecords):')
            for (t, s), n in why.most_common(14):
                print('      %-5s %-28s %d' % (t, s, n))
        c = collections.Counter(k[0] for k in diff)
        if c:
            print('   changed by type: %s' % ', '.join('%s %d' % kv for kv in c.most_common(12)))
            for k in diff[:a.show]:
                sa, sb = A[k][1], B[k][1]
                print('      %s %08X  subrecords A=%s B=%s' % (k[0], k[1], ','.join(sa[:10]), ','.join(sb[:10])))


main()
