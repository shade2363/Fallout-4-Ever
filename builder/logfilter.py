"""Keeps the window and builder.log readable.

The converter prints one line per record (millions of lines) and Elric prints a long error for every mesh it cannot convert.  Pushing all of that into the window froze
it for about 45 minutes in one tester's run.  This filter turns that flood into a few progress lines and writes the full text to raw-output.log (file only).
"""
import re, time

CONVERTER = re.compile(r'^\s*<\d\d:\d\d:\d\d\.\d{3}>')
EXTRACT = re.compile(r'^\s*Extracting: (\d+)/(\d+) - ')
CONVERTER_EVERY = 50000            # progress line every N converter lines
EXTRACT_EVERY = 1000


class LogFilter:
    def __init__(self, raw_path=None):
        self.raw = open(raw_path, 'a', encoding='utf-8', errors='replace', buffering=1 << 16) if raw_path else None
        self.t0 = time.time()
        self.conv = 0
        self.conv_failed = 0

    def feed(self, line):
        """returns the list of lines (usually 0 or 1) to show for this raw line"""
        line = line.rstrip('\r\n')
        if self.raw:
            self.raw.write(line + '\n')
        if CONVERTER.match(line):
            self.conv += 1
            if 'FAILED' in line:
                self.conv_failed += 1
            if self.conv % CONVERTER_EVERY == 0:
                return ['      converter: %s lines processed, %.0f min so far' % (format(self.conv, ','), (time.time() - self.t0) / 60)]
            return []
        m = EXTRACT.match(line)
        if m:
            i, n = int(m.group(1)), int(m.group(2))
            if i % EXTRACT_EVERY == 0 or i == n or i == 1:
                return ['      extracting %s of %s files' % (format(i, ','), format(n, ','))]
            return []
        return [line]

    def finish(self):
        out = []
        if self.conv:
            out.append('      converter: %s lines in total, %s meshes it could not convert (a known problem, handled later; details in raw-output.log)'
                       % (format(self.conv, ','), format(self.conv_failed, ',')))
        if self.raw:
            self.raw.close()
            self.raw = None
        return out
