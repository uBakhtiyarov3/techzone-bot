"""Demo katalog uchun mahsulot rasmlarini chizadi (Pillow). Bir marta ishga tushiriladi:

    python tools/gen_demo_images.py

Natija: webapp/img/demo/*.jpg (900×900, och studiya foni). Haqiqiy do'konda admin paneldan
haqiqiy rasmlar yuklanadi, demo mahsulotlar esa bitta tugma bilan o'chiriladi.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "webapp" / "img" / "demo"
S = 900          # yakuniy o'lcham
K = 2            # supersampling (silliq qirralar uchun)
W = S * K

COLORS = {
    "black": (38, 38, 42), "blue": (120, 150, 190), "pink": (236, 190, 200), "natural": (196, 186, 170),
    "titan_black": (60, 60, 64), "gray": (128, 130, 136), "navy": (46, 58, 92), "lilac": (190, 170, 220),
    "purple": (120, 90, 160), "midnight": (44, 52, 66), "silver": (214, 216, 220), "white": (240, 240, 242),
    "green": (150, 175, 150), "red": (200, 50, 45),
}


def canvas() -> Image.Image:
    """Och studiya foni: yuqoridan yorug'lik, pastda yumshoq gradient."""
    img = Image.new("RGB", (W, W), (244, 244, 246))
    glow = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(glow)
    d.ellipse((W * 0.1, -W * 0.25, W * 0.9, W * 0.75), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(W * 0.12))
    img.paste((255, 255, 255), mask=glow)
    shade = Image.linear_gradient("L").resize((W, W))
    img = Image.composite(Image.new("RGB", (W, W), (226, 226, 230)), img, shade.point(lambda v: v * 0.55))
    return img.convert("RGBA")


def shadow(base: Image.Image, box, blur=40, alpha=90) -> None:
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(box, fill=(0, 0, 0, alpha))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur * K)))


def shade(c, f):
    return tuple(max(0, min(255, int(x * f))) for x in c)


def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def screen(d, box, r):
    """Ekran: to'q fon, qizil-binafsha "wallpaper"."""
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, r, fill=(12, 12, 16))
    wall = Image.new("RGBA", (int(x1 - x0), int(y1 - y0)))
    g = Image.linear_gradient("L").resize(wall.size)
    a = Image.new("RGBA", wall.size, (224, 56, 43, 255))
    b = Image.new("RGBA", wall.size, (30, 20, 60, 255))
    wall = Image.composite(a, b, g)
    m = Image.new("L", wall.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, wall.size[0] - 1, wall.size[1] - 1), r, fill=255)
    return wall, m, (int(x0), int(y0))


def phone_back(color, cam="dual", rot=-8) -> Image.Image:
    lay, d = layer()
    w, h = W * 0.36, W * 0.74
    x0, y0 = (W - w) / 2, (W - h) / 2
    r = W * 0.06
    d.rounded_rectangle((x0 - 6, y0 - 6, x0 + w + 6, y0 + h + 6), r + 6, fill=shade(color, 0.7))
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), r, fill=color)
    # yorug'lik chizig'i
    d.rounded_rectangle((x0 + w * 0.06, y0 + h * 0.02, x0 + w * 0.12, y0 + h * 0.98), 8, fill=shade(color, 1.12))
    cx, cy = x0 + w * 0.08, y0 + h * 0.04
    if cam == "pro":
        size = w * 0.5
        d.rounded_rectangle((cx, cy, cx + size, cy + size), r * 0.7, fill=shade(color, 0.85))
        for px, py in ((0.28, 0.28), (0.28, 0.72), (0.72, 0.5)):
            lx, ly, lr = cx + size * px, cy + size * py, size * 0.2
            d.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), fill=(20, 20, 24))
            d.ellipse((lx - lr * 0.55, ly - lr * 0.55, lx + lr * 0.55, ly + lr * 0.55), fill=(40, 46, 70))
    elif cam == "vertical":
        for i in range(3):
            lx, ly, lr = cx + w * 0.14, cy + w * 0.16 + i * w * 0.24, w * 0.1
            d.ellipse((lx - lr - 6, ly - lr - 6, lx + lr + 6, ly + lr + 6), fill=shade(color, 0.8))
            d.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), fill=(18, 18, 22))
            d.ellipse((lx - lr * 0.5, ly - lr * 0.5, lx + lr * 0.5, ly + lr * 0.5), fill=(38, 44, 66))
    else:
        size = w * 0.42
        d.rounded_rectangle((cx, cy, cx + size, cy + size), r * 0.6, fill=shade(color, 0.9))
        for px, py in ((0.3, 0.3), (0.7, 0.7)):
            lx, ly, lr = cx + size * px, cy + size * py, size * 0.22
            d.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), fill=(20, 20, 24))
            d.ellipse((lx - lr * 0.5, ly - lr * 0.5, lx + lr * 0.5, ly + lr * 0.5), fill=(40, 46, 70))
    return lay.rotate(rot, resample=Image.BICUBIC, center=(W / 2, W / 2))


def phone_front(color, rot=8) -> Image.Image:
    lay, d = layer()
    w, h = W * 0.36, W * 0.74
    x0, y0 = (W - w) / 2, (W - h) / 2
    r = W * 0.06
    d.rounded_rectangle((x0 - 6, y0 - 6, x0 + w + 6, y0 + h + 6), r + 6, fill=shade(color, 0.75))
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), r, fill=(10, 10, 12))
    wall, m, pos = screen(d, (x0 + 14, y0 + 14, x0 + w - 14, y0 + h - 14), r - 12)
    lay.paste(wall, pos, m)
    d.rounded_rectangle((W / 2 - w * 0.16, y0 + 30, W / 2 + w * 0.16, y0 + 30 + w * 0.09), 40, fill=(6, 6, 8))
    return lay.rotate(rot, resample=Image.BICUBIC, center=(W / 2, W / 2))


def compose(*layers_with_offset) -> Image.Image:
    img = canvas()
    shadow(img, (W * 0.18, W * 0.83, W * 0.82, W * 0.93))
    for lay, dx, dy, scale in layers_with_offset:
        if scale != 1:
            lay = lay.resize((int(W * scale), int(W * scale)), Image.LANCZOS)
        img.alpha_composite(lay, (int(dx * W + (W - lay.width) / 2), int(dy * W + (W - lay.height) / 2)))
    return img


def phone(color, cam="dual") -> Image.Image:
    return compose((phone_front(color), 0.13, 0.02, 0.92), (phone_back(color, cam), -0.12, 0, 0.92))


def laptop(color) -> Image.Image:
    img = canvas()
    shadow(img, (W * 0.08, W * 0.78, W * 0.92, W * 0.9))
    lay, d = layer()
    sw, sh = W * 0.7, W * 0.44
    x0, y0 = (W - sw) / 2, W * 0.2
    d.rounded_rectangle((x0, y0, x0 + sw, y0 + sh), 28, fill=shade(color, 0.6))
    wall, m, pos = screen(d, (x0 + 16, y0 + 16, x0 + sw - 16, y0 + sh - 16), 14)
    lay.paste(wall, pos, m)
    by = y0 + sh
    d.polygon([(x0 - W * 0.06, by + W * 0.07), (x0 + sw + W * 0.06, by + W * 0.07), (x0 + sw, by), (x0, by)],
              fill=color)
    d.rectangle((x0 - W * 0.06, by + W * 0.07, x0 + sw + W * 0.06, by + W * 0.085), fill=shade(color, 0.75))
    d.rounded_rectangle((W / 2 - W * 0.07, by + W * 0.055, W / 2 + W * 0.07, by + W * 0.07), 6,
                        fill=shade(color, 0.85))
    img.alpha_composite(lay)
    return img


def tablet(color) -> Image.Image:
    lay, d = layer()
    w, h = W * 0.56, W * 0.76
    x0, y0 = (W - w) / 2, (W - h) / 2
    d.rounded_rectangle((x0 - 8, y0 - 8, x0 + w + 8, y0 + h + 8), 56, fill=color)
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), 48, fill=(10, 10, 12))
    wall, m, pos = screen(d, (x0 + 22, y0 + 22, x0 + w - 22, y0 + h - 22), 30)
    lay.paste(wall, pos, m)
    return compose((lay.rotate(-6, resample=Image.BICUBIC, center=(W / 2, W / 2)), 0, 0, 0.95))


def earbuds(color) -> Image.Image:
    img = canvas()
    shadow(img, (W * 0.2, W * 0.76, W * 0.8, W * 0.88))
    lay, d = layer()
    cw, ch = W * 0.42, W * 0.34
    x0, y0 = W * 0.3, W * 0.42
    d.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), 110, fill=color)
    d.line((x0 + 20, y0 + ch * 0.32, x0 + cw - 20, y0 + ch * 0.32), fill=shade(color, 0.8), width=6)
    d.ellipse((x0 + cw / 2 - 12, y0 + ch * 0.55, x0 + cw / 2 + 12, y0 + ch * 0.55 + 24), fill=(120, 220, 140))
    for bx in (W * 0.2, W * 0.72):
        d.ellipse((bx, W * 0.2, bx + W * 0.13, W * 0.33), fill=color)
        d.ellipse((bx + W * 0.03, W * 0.23, bx + W * 0.08, W * 0.28), fill=(30, 30, 34))
        d.rounded_rectangle((bx + W * 0.045, W * 0.3, bx + W * 0.085, W * 0.44), 30, fill=shade(color, 0.96))
    img.alpha_composite(lay)
    return img


def headphones(color) -> Image.Image:
    img = canvas()
    shadow(img, (W * 0.15, W * 0.8, W * 0.85, W * 0.92))
    lay, d = layer()
    d.arc((W * 0.2, W * 0.12, W * 0.8, W * 0.78), 180, 360, fill=shade(color, 0.85), width=int(W * 0.05))
    for cx in (W * 0.2, W * 0.8):
        d.rounded_rectangle((cx - W * 0.11, W * 0.42, cx + W * 0.11, W * 0.76), 90, fill=color)
        d.rounded_rectangle((cx - W * 0.075, W * 0.46, cx + W * 0.075, W * 0.72), 70, fill=shade(color, 0.7))
    img.alpha_composite(lay)
    return img


def watch(color, size=1.0) -> Image.Image:
    img = canvas()
    shadow(img, (W * 0.3, W * 0.84, W * 0.7, W * 0.93))
    lay, d = layer()
    bw = W * 0.34 * size
    x0, y0 = (W - bw) / 2, (W - bw * 1.2) / 2
    d.rounded_rectangle((W / 2 - bw * 0.36, W * 0.05, W / 2 + bw * 0.36, W * 0.95), 50, fill=shade(color, 0.9))
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bw * 1.2), 70, fill=shade(color, 0.7))
    wall, m, pos = screen(d, (x0 + 18, y0 + 18, x0 + bw - 18, y0 + bw * 1.2 - 18), 52)
    lay.paste(wall, pos, m)
    d.rounded_rectangle((x0 + bw, y0 + bw * 0.3, x0 + bw + 18, y0 + bw * 0.5), 8, fill=shade(color, 0.6))
    img.alpha_composite(lay)
    return img


def powerbank(color) -> Image.Image:
    lay, d = layer()
    w, h = W * 0.4, W * 0.66
    x0, y0 = (W - w) / 2, (W - h) / 2
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), 60, fill=color)
    for i in range(4):
        cx = W / 2 - 60 + i * 40
        d.ellipse((cx - 8, y0 + h * 0.86, cx + 8, y0 + h * 0.86 + 16), fill=(90, 170, 255) if i < 3 else (70, 70, 74))
    d.rounded_rectangle((W / 2 - 50, y0 - 4, W / 2 + 50, y0 + 14), 6, fill=(20, 20, 22))
    return compose((lay.rotate(-10, resample=Image.BICUBIC, center=(W / 2, W / 2)), 0, 0, 0.9))


def charger(color) -> Image.Image:
    img = canvas()
    shadow(img, (W * 0.25, W * 0.78, W * 0.75, W * 0.9))
    lay, d = layer()
    s = W * 0.4
    x0, y0 = (W - s) / 2, W * 0.36
    for px in (W / 2 - s * 0.2, W / 2 + s * 0.12):
        d.rounded_rectangle((px, y0 - s * 0.35, px + s * 0.08, y0 + 10), 10, fill=(170, 170, 176))
    d.rounded_rectangle((x0, y0, x0 + s, y0 + s), 70, fill=color)
    d.rounded_rectangle((W / 2 - 40, y0 + s - 50, W / 2 + 40, y0 + s - 26), 8, fill=shade(color, 0.6))
    img.alpha_composite(lay)
    return img


def save(img: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").resize((S, S), Image.LANCZOS).save(OUT / f"{name}.jpg", quality=84, optimize=True,
                                                         progressive=True)


JOBS = {
    "iphone15-black": lambda: phone(COLORS["black"]),
    "iphone15-blue": lambda: phone(COLORS["blue"]),
    "iphone15-pink": lambda: phone(COLORS["pink"]),
    "iphone15pm-natural": lambda: phone(COLORS["natural"], "pro"),
    "iphone15pm-black": lambda: phone(COLORS["titan_black"], "pro"),
    "s24u-gray": lambda: phone(COLORS["gray"], "vertical"),
    "s24u-black": lambda: phone(COLORS["titan_black"], "vertical"),
    "a55-navy": lambda: phone(COLORS["navy"], "vertical"),
    "a55-lilac": lambda: phone(COLORS["lilac"], "vertical"),
    "rn13-black": lambda: phone(COLORS["black"], "pro"),
    "rn13-purple": lambda: phone(COLORS["purple"], "pro"),
    "x14t-black": lambda: phone(COLORS["black"], "pro"),
    "x14t-gray": lambda: phone(COLORS["gray"], "pro"),
    "mba-midnight": lambda: laptop(COLORS["midnight"]),
    "mba-silver": lambda: laptop(COLORS["silver"]),
    "ideapad": lambda: laptop(COLORS["gray"]),
    "tuf": lambda: laptop(COLORS["black"]),
    "ipadair-gray": lambda: tablet(COLORS["gray"]),
    "ipadair-blue": lambda: tablet(COLORS["blue"]),
    "tabs9fe": lambda: tablet(COLORS["silver"]),
    "airpods": lambda: earbuds(COLORS["white"]),
    "jbl-black": lambda: headphones(COLORS["black"]),
    "jbl-white": lambda: headphones(COLORS["white"]),
    "watch9-midnight": lambda: watch(COLORS["midnight"]),
    "watch9-silver": lambda: watch(COLORS["silver"]),
    "anker": lambda: powerbank(COLORS["black"]),
    "charger": lambda: charger(COLORS["white"]),
}

if __name__ == "__main__":
    for name, job in JOBS.items():
        save(job(), name)
        print("✓", name)
