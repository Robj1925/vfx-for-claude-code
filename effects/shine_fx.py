#!/usr/bin/env python3
"""Three looks rebuilt from reference edits, built on the Krokodove
(KRO) Fusion tools that now ship inside Resolve 21. Ours draws the same looks in numpy + PIL.

  sweep    TX07   Bevel shine sweep title: KRO Bevel (filter Gaussian, size 0.8, height 0.1654, read from the inspector),
                    Light tab position keyed from left to right over about 15 frames with S keys, so a highlight runs across
                    the bevelled letters. Grey by default (Color Corrector to recolour).
  halftone TX08   Halftone resolve title: KRO Rasterize on the text (channel luminance, grid 2), Size keyed from big to
                    small with S keys. Frame check: big white dots in one row become smaller dots, then the
                    clean words.
  rays     FX10  Light rays wipe: KRO Microwaves, shape Round, brightness up, only edges about 0.9, length keyed down
                    over about 50 frames: rays burst out of the bright parts of the frame and slowly pull back in.

  python3 effects/shine_fx.py sweep    "SHINE SWEEP" --bg clip.mov --at 0 --dur 2 -o out.mp4 [--y 0.3]
  python3 effects/shine_fx.py halftone "Your words"  --bg clip.mov --at 0 --dur 2 -o out.mp4
  python3 effects/shine_fx.py rays     ""            --bg clip.mov --at 0 --dur 2.5 -o out.mp4
"""
import argparse, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

HN = "/System/Library/Fonts/HelveticaNeue.ttc"
F24 = 23.976


def text_alpha(text, W, H, y, size, index=3):
    f = ImageFont.truetype(HN, size, index=index)
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    d.text(((W - (r - l)) / 2 - l, H * y - (b - t) / 2 - t), text, font=f, fill=255)
    return np.asarray(im, np.float32) / 255


def s_curve(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def sweep(bgs, fps, text, y, size=130, n24=15, base=(0.62, 0.63, 0.66), loop=True):
    H, W = bgs[0].shape[:2]
    a = text_alpha(text, W, H, y, size)
    hgt = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(size * 0.06)), np.float32) / 255
    gy, gx = np.gradient(hgt * size * 0.1654)
    nz = 1 / np.sqrt(gx ** 2 + gy ** 2 + 1)
    nx, ny = -gx * nz, -gy * nz
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rows = np.nonzero(a.max(1) > 0.1)[0]
    cols = np.nonzero(a.max(0) > 0.1)[0]
    x0, x1 = cols.min(), cols.max()
    n = round(n24 * fps / F24)
    out = []
    for i, bg in enumerate(bgs):
        k = (i % (n + round(3 * fps / F24))) if loop else i   # measured: the sweep repeats about every 15 to 18 frames
        lx = x0 - 0.3 * (x1 - x0) + 1.6 * (x1 - x0) * float(s_curve(k / max(n, 1)))   # light runs across the word
        ly = rows.min() - 0.6 * size
        L = np.dstack([lx - xx, ly - yy, np.full_like(xx, size * 0.9)])
        L /= np.linalg.norm(L, axis=2, keepdims=True)
        diff = np.clip(nx * L[..., 0] + ny * L[..., 1] + nz * L[..., 2], 0, 1)
        band = np.exp(-((xx - lx) / (size * 0.9)) ** 2)                                   # the moving sheen
        spec = (diff ** 12) * (0.35 + 0.9 * band)
        rgb = np.clip(np.array(base) * (0.45 + 0.65 * diff)[..., None] + spec[..., None], 0, 1)
        out.append(rgb * a[..., None] + bg * (1 - a[..., None]))
    return out


def halftone(bgs, fps, text, y, size=120, n24=20):
    H, W = bgs[0].shape[:2]
    a = text_alpha(text, W, H, y, size, index=1)
    n = round(n24 * fps / F24)
    out = []
    big = size * 0.55                                           # first cell ~ half the letter height: one row of dots
    for i, bg in enumerate(bgs):
        p = float(s_curve(i / max(n, 1)))
        cell = big * (1 - p) + 2 * p
        if cell <= 2.5:
            lay = a
        else:
            c = max(2, int(round(cell)))
            gh, gw = H // c, W // c
            small = a[: gh * c, : gw * c].reshape(gh, c, gw, c).mean((1, 3))
            im = Image.new("L", (W, H), 0)
            d = ImageDraw.Draw(im)
            for (r, q) in zip(*np.nonzero(small > 0.02)):
                rad = c * 0.5 * np.sqrt(small[r, q])
                cx, cy = q * c + c / 2, r * c + c / 2
                d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=255)
            lay = np.asarray(im, np.float32) / 255
        out.append(lay[..., None] + bg * (1 - lay[..., None]))
    return out


def rays(bgs, fps, n24=50, thresh=0.30, length0=2.2, gain=3.6):
    n = round(n24 * fps / F24)
    out = []
    for i, bg in enumerate(bgs):
        L = length0 * (1 - float(s_curve(i / max(n, 1))))
        if L < 0.01:
            out.append(bg)
            continue
        lum = bg.mean(2, keepdims=True)
        hi = np.clip((lum - thresh) / (1 - thresh), 0, 1) * bg          # only the bright edges throw rays
        streak = fx.zoom_blur(hi, L, samples=24)
        out.append(np.clip(bg + streak * gain, 0, 1))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["sweep", "halftone", "rays"]), ap.add_argument("text")
    ap.add_argument("--bg", required=True), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=2.0)
    ap.add_argument("--y", type=float, default=0.3), ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    bgs = fx.read_frames(a.bg, a.at, n, a.w, a.h, a.fps)
    if a.kind == "sweep":
        out = sweep(bgs, a.fps, a.text, a.y, a.size or 130)
    elif a.kind == "halftone":
        out = halftone(bgs, a.fps, a.text, a.y, a.size or 120)
    else:
        out = rays(bgs, a.fps)
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for f in out:
        wr.write(f)
    wr.close()
    print(f"{a.kind}: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
