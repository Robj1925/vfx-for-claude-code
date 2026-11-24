#!/usr/bin/env python3
"""TX10 Apple bounce rise.
Build (Resolve, used on titles and on the same "file" cards): Transform after the template, angle 2.6, Center Y keyed
0.2 -> 0.5 over 40 frames, spline shaped by hand to "curve all the way up, go down, then go back up" (an overshoot and settle),
or Size > Anim Curves > Elastic with time scale about 1.9 to 3. Frame check of a reference edit (first 5 s at 6 fps): Apple style
white and black cards; the tilted black cards rise from below, overshoot a little, settle; words ghost in word by word.

  python3 effects/apple_bounce.py --bg clip.mov --at 0 --dur 2.2 --text "Introducing" -o out.mp4          # a title
  python3 effects/apple_bounce.py --bg clip.mov --at 0 --dur 2.2 --image card.png -o out.mp4               # any image or screenshot
"""
import argparse, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

HN = "/System/Library/Fonts/HelveticaNeue.ttc"
F24 = 23.976


def overshoot(t, amp=0.10):
    """Rise, pass the target by about 10 %, dip back under it a little, settle (a hand-drawn spline)."""
    t = np.clip(t, 0, 1)
    base = 1 - (1 - t) ** 3
    wob = amp * np.sin(np.pi * 2.2 * t) * (1 - t) ** 1.6 * (t > 0.15)
    return base + wob


def element(text, image, W):
    if image:
        im = Image.open(image).convert("RGBA")
        s = W * 0.62 / im.width
        return im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    f = ImageFont.truetype(HN, 120, index=1)
    l, t, r, b = f.getbbox(text)
    pad = 60
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    h = b - t
    grad = Image.new("RGBA", im.size)                                        # gradient: yellow orange to pink purple
    gd = ImageDraw.Draw(grad)
    for y in range(im.size[1]):
        k = np.clip((y - pad) / max(h, 1), 0, 1)
        c = tuple(int(255 * v) for v in (1.0 * (1 - k) + 0.85 * k, 0.72 * (1 - k) + 0.25 * k, 0.15 * (1 - k) + 0.95 * k))
        gd.line([(0, y), (im.size[0], y)], fill=c + (255,))
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).text((pad - l, pad - t), text, font=f, fill=255)
    im.paste(grad, (0, 0), mask)
    glow = im.filter(ImageFilter.GaussianBlur(18))                         # soft glow
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(glow)
    out.alpha_composite(im)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bg", required=True), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=2.2)
    ap.add_argument("--text", default="Introducing"), ap.add_argument("--image")
    ap.add_argument("--angle", type=float, default=2.6), ap.add_argument("--y", type=float, default=0.5)
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    W, H = a.w, a.h
    bgs = fx.read_frames(a.bg, a.at, n, W, H, a.fps)
    el = element(a.text, a.image, W).rotate(a.angle, resample=Image.BICUBIC, expand=True)
    n40 = round(40 * a.fps / F24)
    wr = fx.Writer(a.out, W, H, a.fps)
    for i, bg in enumerate(bgs):
        p = float(overshoot(i / n40))
        y = 0.2 + (a.y - 0.2) * p                                             # Fusion Y is up: 0.2 is low in the frame
        cy = H * (1 - y)
        op = min(i / (5 * a.fps / F24), 1.0)
        img = Image.fromarray((bg * 255).astype(np.uint8)).convert("RGBA")
        e = el.copy()
        if op < 1:
            e.putalpha(e.getchannel("A").point(lambda v: int(v * op)))
        img.alpha_composite(e, (round(W / 2 - e.width / 2), round(cy - e.height / 2)))
        wr.write(np.asarray(img.convert("RGB"), np.float32) / 255)
    wr.close()
    print(f"apple bounce: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
