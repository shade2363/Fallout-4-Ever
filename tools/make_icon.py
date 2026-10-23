"""Draw the program icon (original artwork, no game art): a green phosphor terminal square with corner brackets and a '4'.  Writes assets/app.ico."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def draw(size=256):
    s = size
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, s - 8, s - 8), radius=s // 8, fill=(2, 20, 9, 255), outline=(77, 255, 136, 255), width=max(2, s // 40))
    b = s // 4
    for (cx, cy, sx, sy) in ((26, 26, 1, 1), (s - 26, 26, -1, 1), (26, s - 26, 1, -1), (s - 26, s - 26, -1, -1)):
        d.line((cx, cy, cx + b * sx, cy), fill=(77, 255, 136, 255), width=max(3, s // 32))
        d.line((cx, cy, cx, cy + b * sy), fill=(77, 255, 136, 255), width=max(3, s // 32))
    try:
        f = ImageFont.truetype('consolab.ttf', int(s * 0.62))
    except OSError:
        f = ImageFont.load_default()
    glow = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.text((s / 2, s / 2 - s * 0.02), '4', font=f, fill=(77, 255, 136, 255), anchor='mm')
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(s / 40)))
    ImageDraw.Draw(img).text((s / 2, s / 2 - s * 0.02), '4', font=f, fill=(184, 255, 208, 255), anchor='mm')
    return img


if __name__ == '__main__':
    out = os.path.join(HERE, 'assets')
    os.makedirs(out, exist_ok=True)
    big = draw(256)
    big.save(os.path.join(out, 'app.ico'), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    big.save(os.path.join(out, 'app-preview.png'))
    print('wrote', os.path.join(out, 'app.ico'))
