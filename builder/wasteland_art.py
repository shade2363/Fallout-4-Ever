"""Original artwork for the installer window, drawn entirely in code (so it is ours): a ruined Washington DC skyline at dusk.

The Washington Monument, the Capitol and the Lincoln Memorial are real public landmarks; everything here is silhouettes, gradients and noise
generated from a fixed random seed.  No Bethesda art, characters, logos or fonts are used or imitated.
make_wasteland() gives the coloured banner; phosphor() turns any image into the green monochrome terminal look with scanlines.
"""
import math
import random


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_wasteland(W, H, seed=7, z=0.6):
    """banner W x H (ground line 26 px above the bottom); z = size of the landmarks relative to a 650 px high scene"""
    from PIL import Image, ImageDraw, ImageFilter, ImageChops
    S = 2
    w, h = W * S, H * S
    rnd = random.Random(seed)
    ground = H - 26
    cx0 = W / 2

    def X(x):
        return cx0 + (x - 520) * z

    def Y(y):                                                    # y given for a scene whose ground is at 650
        return ground + (y - 650) * z

    stops = [(0.00, (8, 22, 20)), (0.35, (30, 52, 38)), (0.62, (104, 82, 36)), (0.82, (214, 128, 44)), (0.93, (150, 78, 28)), (1.0, (40, 22, 12))]
    col = Image.new('RGB', (1, h))
    px = col.load()
    for y in range(h):
        t = y / (h - 1)
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                px[0, y] = _lerp(stops[i][1], stops[i + 1][1], (t - stops[i][0]) / (stops[i + 1][0] - stops[i][0]))
                break
    img = col.resize((w, h))

    def blob(color, cx, cy, rx, ry, blur, alpha):
        nonlocal img
        m = Image.new('L', (w, h), 0)
        ImageDraw.Draw(m).ellipse(((cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S), fill=255)
        m = m.filter(ImageFilter.GaussianBlur(blur * S)).point(lambda v: int(v * alpha))
        img = Image.composite(Image.new('RGB', (w, h), color), img, m)

    blob((255, 168, 58), X(700), ground - 30, 300 * z + 120, 110, 40, 0.55)
    blob((90, 255, 60), W * 0.88, H * 0.12, 260, 120, 50, 0.20)
    for _ in range(14):
        blob(rnd.choice([(24, 40, 30), (70, 56, 30), (40, 34, 26)]), rnd.uniform(-50, W + 50), rnd.uniform(10, H * 0.6),
             rnd.uniform(80, 220), rnd.uniform(6, 20), 14, rnd.uniform(0.18, 0.4))

    def layer():
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        return im, ImageDraw.Draw(im)

    def poly(d, pts, fill):
        d.polygon([(X(x) * S, Y(y) * S) for x, y in pts], fill=fill)

    def rect(d, x0, y0, x1, y1, fill):
        poly(d, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill)

    def line(d, x0, y0, x1, y1, fill, width):
        d.line((X(x0) * S, Y(y0) * S, X(x1) * S, Y(y1) * S), fill=fill, width=max(1, int(width * z * S)))

    G = 650

    def jag_top(x0, x1, y_top, y_base, step=6, amp=9):
        pts = [(x0, y_base)]
        x = x0
        while x < x1:
            pts.append((x, y_top + rnd.uniform(-amp, amp * 0.4)))
            x += rnd.uniform(step * 0.6, step * 1.6)
        pts += [(x1, y_top + rnd.uniform(-amp, 0)), (x1, y_base)]
        return pts

    # far ruins (hazy), spread across the whole banner width
    far, fd = layer()
    x = (X(0) - cx0) / z + 520 - 1400                            # start left of the screen in scene units
    while X(x) < W + 40:
        bw = rnd.uniform(22, 48)
        bh = rnd.uniform(40, 150)
        poly(fd, jag_top(x, x + bw, G - bh, G + 4, 5, 12), (96, 62, 30, 255))
        x += bw + rnd.uniform(-6, 10)
    far = far.filter(ImageFilter.GaussianBlur(1.0 * S))

    mid, md = layer()
    DK = (22, 15, 10, 255)
    # Lincoln Memorial: steps, colonnade with a fallen column, collapsed roof corner
    x0, x1 = 60, 330
    rect(md, x0 - 24, G - 14, x1 + 24, G + 4, DK)
    rect(md, x0 - 12, G - 28, x1 + 12, G - 14, DK)
    rect(md, x0 - 4, G - 38, x1 + 4, G - 28, DK)
    n = 9
    for i in range(n):
        cx = x0 + i * (x1 - x0) / (n - 1)
        if i == 3:
            continue
        top = G - 38 - (80 if i != 6 else rnd.uniform(26, 44))
        poly(md, [(cx - 6, G - 38), (cx - 5, top), (cx + 5, top + rnd.uniform(0, 5)), (cx + 6, G - 38)], DK)
    poly(md, [(x0 - 10, G - 118), (x1 + 10, G - 118), (x1 + 10, G - 132), (x1 - 40, G - 138), (x1 - 70, G - 128), (x1 - 100, G - 132),
              (x0 + 90, G - 134), (x0 + 40, G - 128), (x0 - 10, G - 134)], DK)
    poly(md, [(x0 + 20, G - 134), (x1 - 30, G - 134), (x1 - 60, G - 150), (x1 - 100, G - 156), (x0 + 110, G - 152), (x0 + 60, G - 148)], DK)
    poly(md, [(x1 - 4, G - 38), (x1 + 40, G - 24), (x1 + 70, G - 8), (x1 + 20, G + 2)], DK)
    # Washington Monument with a shattered tip
    cx = 560
    poly(md, [(cx - 14, G + 4), (cx - 9, G - 330), (cx - 5, G - 346), (cx + 1, G - 338), (cx + 4, G - 352), (cx + 9, G - 330), (cx + 14, G + 4)], DK)
    poly(md, [(cx - 22, G + 4), (cx - 18, G - 14), (cx + 18, G - 14), (cx + 24, G + 4)], DK)
    # Capitol: wings, portico, drum, dome with a bite blown out, lantern
    c = 868
    poly(md, jag_top(c - 135, c - 56, G - 52, G + 4, 8, 7), DK)
    poly(md, jag_top(c + 56, c + 150, G - 48, G + 4, 8, 12), DK)
    poly(md, [(c - 58, G + 4), (c - 58, G - 66), (c - 20, G - 70), (c, G - 92), (c + 22, G - 70), (c + 58, G - 66), (c + 58, G + 4)], DK)
    rect(md, c - 36, G - 108, c + 36, G - 66, DK)
    dome = [(c - 40 + 80 * k / 24, G - 108 - 58 * math.sin(math.pi * k / 24)) for k in range(25)]
    dome = [p for p in dome if not (c + 8 < p[0] < c + 34 and p[1] < G - 138)]
    poly(md, [(c - 40, G - 108)] + dome + [(c + 40, G - 108)], DK)
    poly(md, [(c + 8, G - 140), (c + 14, G - 128), (c + 22, G - 134), (c + 34, G - 118), (c + 20, G - 112)], DK)
    rect(md, c - 7, G - 188, c + 7, G - 160, DK)
    poly(md, [(c - 3, G - 188), (c, G - 206), (c + 3, G - 188)], DK)
    for xx in (390, 430, 470, 640, 690, 1000, -60, 1100, 1180):
        bw = rnd.uniform(26, 44)
        poly(md, jag_top(xx, xx + bw, G - rnd.uniform(46, 110), G + 4, 6, 10), DK)

    near, nd = layer()
    NR = (7, 5, 3, 255)
    pts = [(-1500, 1200), (-1500, G + 6)]
    x = -1500
    while x < 2600:
        x += rnd.uniform(10, 28)
        pts.append((x, G + rnd.uniform(-10, 12)))
    pts += [(2600, G + 6), (2600, 1200)]
    poly(nd, pts, NR)
    for _ in range(40):
        sx = rnd.uniform(-300, 1400)
        ln = rnd.uniform(18, 62)
        ang = rnd.uniform(-0.45, 0.45)
        line(nd, sx, G + 4, sx + math.sin(ang) * ln, G + 4 - math.cos(ang) * ln, NR, 2)
    tx = -60
    line(nd, tx, G + 4, tx + 4, G - 150, NR, 7)
    for (ox, oy, ex, ey) in [(4, -60, 46, -112), (4, -90, -22, -140), (4, -120, 34, -170), (4, -138, -8, -190), (46, -112, 66, -118), (-22, -140, -38, -132)]:
        line(nd, tx + ox, G + oy, tx + ex, G + ey, NR, 3)
    line(nd, 470, G + 4, 484, G - 150, NR, 4)
    line(nd, 456, G - 140, 506, G - 150, NR, 3)
    line(nd, 486, G - 136, 520, G - 112, NR, 1)

    for lay in (far, mid, near):
        img = Image.alpha_composite(img.convert('RGBA'), lay).convert('RGB')
    blob((190, 110, 40), W / 2, ground - 4, W * 0.7, 14, 10, 0.40)
    sp, spd = layer()
    for _ in range(int(W * H / 1500)):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.choice([0.8, 1.1, 1.5])
        c1 = (255, 150, 50, rnd.randint(120, 230)) if rnd.random() < 0.55 else (190, 190, 170, rnd.randint(50, 110))
        spd.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=c1)
    img = Image.alpha_composite(img.convert('RGBA'), sp.filter(ImageFilter.GaussianBlur(0.6))).convert('RGB')
    return img.resize((W, H), Image.LANCZOS)


def phosphor(img, tint=(70, 255, 120), floor=(0, 14, 4), scan=3, bloom=True):
    """turn an RGB image into a green monochrome CRT picture with scanlines and a soft glow"""
    from PIL import Image, ImageOps, ImageFilter, ImageChops
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    out = ImageOps.colorize(g, floor, tint, mid=(8, 70, 26))
    if bloom:
        out = ImageChops.add(out, out.filter(ImageFilter.GaussianBlur(3)).point(lambda v: int(v * 0.45)))
    w, h = out.size
    sl = Image.new('L', (w, h), 255)
    px = sl.load()
    for y in range(0, h, scan):
        for x in range(w):
            px[x, y] = 190
    return ImageChops.multiply(out, Image.merge('RGB', (sl, sl, sl)))
