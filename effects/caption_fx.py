#!/usr/bin/env python3
"""Three caption looks rebuilt frame by frame from a reference edit.

  highlight  TX13  Selection highlight sweep: a light-blue box (Background + Rectangle mask, level 0.3) fills in behind the
                      words from left to right, led by a dark-blue rounded "bulb" bar (second Background + Rectangle + Ellipse),
                      Soft Glow on top; one Transform moves bulb and mask together, S keys. Frame check of the reference
                      opening, 2.4 s (every frame): the bar appears at the left edge of the line, sweeps right in about 10 frames, the
                      words inside turn pale blue, the bar leaves at the end of the line and the highlight stays.
  dropstop   TX14  Word drop stop-motion: Follower per word, offset Y +0.2 to 0 (falls into place) over 25 to 30 frames, out
                      cubic with the handle pulled, delay 0.5, opacity 0 to 1 over 5 to 7 frames, then a Stop Motion node set to 2
                      (the picture updates every second frame, so it looks hand-animated).

  python3 effects/caption_fx.py highlight "Cinematic Captions" --bg clip.mov --at 0 --dur 1.6 --y 0.7 -o out.mp4
  shakyerode TX15  Shaky erode rise: handwritten letters thicken from thin strokes in held steps, jitter, and rise (see shakyerode()).

  python3 effects/caption_fx.py shakyerode "Custom Title" --bg clip.mov --at 0 --dur 2 -o out.mp4
  python3 effects/caption_fx.py dropstop  "Smooth word drop"   --bg clip.mov --at 0 --dur 2.2 --y 0.7 -o out.mp4
"""
import argparse, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

HN = "/System/Library/Fonts/HelveticaNeue.ttc"
SF = "/System/Library/Fonts/SFNS.ttf"
F24 = 23.976


def s_curve(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def highlight(bgs, fps, text, y, size=96, n24=10, box_rgb=(150, 175, 255), bar_rgb=(40, 80, 230)):
    H, W = bgs[0].shape[:2]
    f = ImageFont.truetype(HN, size, index=1)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = d0.textbbox((0, 0), text, font=f)
    tw, th = r - l, b - t
    x0, ty = (W - tw) / 2, H * y - th / 2
    pad = size * 0.18
    bx0, bx1, by0, by1 = x0 - pad, x0 + tw + pad, ty - pad * 1.2, ty + th + pad * 1.2
    n = round(n24 * fps / F24)
    start = round(3 * fps / F24)                                 # the line is up a few frames before the sweep
    out = []
    for i, bg in enumerate(bgs):
        img = Image.fromarray((bg * 255).astype(np.uint8)).convert("RGBA")
        p = float(s_curve((i - start) / n)) if i >= start else 0.0
        edge = bx0 + (bx1 - bx0) * p
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        if p > 0:
            dl.rectangle((bx0, by0, edge, by1), fill=box_rgb + (int(255 * 0.30),))     # level 0.3 box
        # words: white outside the box, pale blue inside it
        txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(txt).text((x0 - l, ty - t), text, font=f, fill=(255, 255, 255, 255))
        if p > 0:
            tint = Image.new("RGBA", (W, H), (205, 218, 255, 255))
            m = Image.new("L", (W, H), 0)
            ImageDraw.Draw(m).rectangle((bx0, by0, edge, by1), fill=255)
            m = Image.composite(txt.getchannel("A"), Image.new("L", (W, H), 0), m)
            txt.paste(tint, (0, 0), m)
        lay.alpha_composite(txt)
        if 0 < p < 1:                                            # the bulb: a rounded bar on the leading edge
            bw = size * 0.16
            dl2 = ImageDraw.Draw(lay)
            dl2.rounded_rectangle((edge - bw / 2, by0 - pad * 0.6, edge + bw / 2, by1 + pad * 0.2), radius=bw / 2, fill=bar_rgb + (255,))
            dl2.ellipse((edge - bw * 0.8, by0 - pad * 0.9 - bw * 0.6, edge + bw * 0.8, by0 - pad * 0.9 + bw), fill=bar_rgb + (255,))
        glow = lay.filter(ImageFilter.GaussianBlur(size * 0.12))           # Soft Glow, gain down
        glow.putalpha(glow.getchannel("A").point(lambda v: int(v * 0.5)))
        img.alpha_composite(glow)
        img.alpha_composite(lay)
        out.append(np.asarray(img.convert("RGB"), np.float32) / 255)
    return out


def dropstop(bgs, fps, text, y, size=96, n24=27, delay=0.5, fade24=6, offset=0.2, hold=2):
    H, W = bgs[0].shape[:2]
    f = ImageFont.truetype(HN, size, index=1)              # heavy rounded sans, close to Drowner
    words = text.split()
    space = f.getlength(" ")
    widths = [f.getlength(w) for w in words]
    x = (W - (sum(widths) + space * (len(words) - 1))) / 2
    sprites = []
    for w, wd in zip(words, widths):
        im = Image.new("RGBA", (int(wd) + 20, int(size * 1.4)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10, int(size * 0.1)), w, font=f, fill=(255, 255, 255, 255))
        sprites.append((im, x - 10))
        x += wd + space
    out = []
    for i, bg in enumerate(bgs):
        i_held = (i // hold) * hold                               # Stop Motion node: the text updates every 2nd frame
        t24 = i_held * F24 / fps
        img = Image.fromarray((bg * 255).astype(np.uint8)).convert("RGBA")
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for k, (sp, sx) in enumerate(sprites):
            local = t24 - k * delay * n24
            if local <= 0:
                continue
            p = 1 - (1 - min(local / n24, 1.0)) ** 4.2
            op = min(local / fade24, 1.0)
            dy = -(1 - p) * offset * H * 0.18                    # falls from above (measured: about 70 px at 1080x1920)
            s = sp.copy()
            s.putalpha(s.getchannel("A").point(lambda v: int(v * op)))
            lay.paste(s, (round(sx), round(H * y - size * 0.7 + dy)), s)
        img.alpha_composite(lay)
        out.append(np.asarray(img.convert("RGB"), np.float32) / 255)
    return out


def shakyerode(bgs, fps, text, y, size=110, hold=4, n_erode24=10, n_rise24=25, jitter=0.035, seed=70):
    """TX15 ('shaking erode up'): Follower order random, delay high; Transform Y modified with Perturb (speed up,
    wobble and strength down, X scale off, Y scale on, seed 70) = small random up-down per letter; Erode/Dilate keyed from thin to
    full over about 10 frames; Stop Motion (Frame Repeat 4); then a Transform rise from low to 0.5 over 25 frames,
    out cubic. Frame check of the reference, every unique frame: the letters start as thin strokes and thicken to full
    weight in 2 to 3 held steps, each held step the letters sit at slightly different heights."""
    import random
    H, W = bgs[0].shape[:2]
    fp = "/System/Library/Fonts/Noteworthy.ttc"
    f = ImageFont.truetype(fp, size, index=1) if Path(fp).exists() else ImageFont.truetype(HN, size, index=1)
    widths = [f.getlength(c) for c in text]
    x0 = (W - sum(widths)) / 2
    out = []
    for i, bg in enumerate(bgs):
        ih = (i // hold) * hold
        t24 = ih * F24 / fps
        e = min(t24 / n_erode24, 1.0)
        p = 1 - (1 - min(t24 / n_rise24, 1.0)) ** 3
        rise = (1 - p) * H * 0.06
        rnd = random.Random(seed * 1000 + ih)
        lay = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(lay)
        x = x0
        for c, wd in zip(text, widths):
            jy = (rnd.random() * 2 - 1) * jitter * size
            d.text((x, H * y - size * 0.7 + rise + jy), c, font=f, fill=255)
            x += wd
        if e < 1:                                            # Erode: thin strokes that thicken
            k = 1 + 2 * round((1 - e) * 2)                  # 5, 3, 1 px min filter
            thin = lay.filter(ImageFilter.MinFilter(k)) if k > 1 else lay
            lay = Image.blend(thin, lay, e * 0.6)
        img = Image.fromarray((bg * 255).astype(np.uint8)).convert("RGBA")
        white = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        img.paste(white, (0, 0), lay)
        out.append(np.asarray(img.convert("RGB"), np.float32) / 255)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["highlight", "dropstop", "shakyerode"]), ap.add_argument("text")
    ap.add_argument("--bg", required=True), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=1.8)
    ap.add_argument("--y", type=float, default=0.7), ap.add_argument("--size", type=int, default=96)
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    bgs = fx.read_frames(a.bg, a.at, n, a.w, a.h, a.fps)
    if a.kind == "highlight":
        out = highlight(bgs, a.fps, a.text, a.y, a.size)
    elif a.kind == "shakyerode":
        out = shakyerode(bgs, a.fps, a.text, a.y, max(a.size, 110))
    else:
        out = dropstop(bgs, a.fps, a.text, a.y, a.size)
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for f in out:
        wr.write(f)
    wr.close()
    print(f"{a.kind}: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
