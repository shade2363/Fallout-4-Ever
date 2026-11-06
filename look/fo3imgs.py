"""Fallout 3 IMGS (image space) colour grade: cinematic saturation / contrast / brightness and tint, read from DNAM.

FO3 stores three DNAM sizes (xEdit 'Image Space Data'): 152 bytes have an extra HDR float (Skin Dimmer), so its cinematic block starts at float 25; the 148 / 132 byte
variants start it at float 24.  Cinematic = Saturation, Contrast Avg Lum, Contrast, Brightness; then Tint = R, G, B, Value (amount).
Checked against the data: WastelandBaseImageSpace (148) = sat 0.55 / contrast 1.01 / brightness 1.08, no tint; ShackInterior01 (132) = sat 0.90, contrast 1.2,
brightness 1.1, tint (0.69, 0.56, 0.30) x 0.5; VaultImageSpace01 (152) = sat 1.0, contrast 1.5, tint (0.42, 0.56, 0.57) x 0.65.
The converter read the 148/132 variants one float off (WastelandBase came out with saturation 0.95)."""
import struct


def grade(dnam):
    """-> dict(sat, contrast, bright, tint_amt, tint=(r, g, b)) or None"""
    n = len(dnam) // 4
    if n < 32: return None
    f = struct.unpack('<%df' % n, dnam[:n * 4])
    c = 25 if len(dnam) >= 152 else 24
    sat, _avg, con, bri = f[c:c + 4]
    r, g, b, amt = f[c + 4:c + 8]
    clean = lambda v, d: d if v != v or v < 0 or v > 10 else v          # NaN / garbage -> default
    return {'sat': clean(sat, 1.0), 'contrast': clean(con, 1.0), 'bright': clean(bri, 1.0),
            'tint_amt': min(max(clean(amt, 0.0), 0.0), 1.0), 'tint': (clean(r, 1.0), clean(g, 1.0), clean(b, 1.0))}
