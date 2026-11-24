#!/usr/bin/env python3
"""FX11 Liquid glass pill.
Build (Resolve Fusion): adjustment clip; Merge, Merge, Displace (offset -1, refraction strength -4, spread up), a Rectangle with the corner
radius up as the displace map and the mask; the rectangle starts as a "little ball" low in the frame, its Center Y keyed up to
the middle in under 20 frames, then Width and Height keyed bigger over about 10 more frames, all out cubic / S.
Frame check of a reference edit, 3.2 s to 5 s (every frame): a small glass ball appears under the words, slides up into them,
stretches sideways into a pill around the line (about 6 frames), and later wraps a short phrase as a fitted pill with a bright
thin rim; the purple background bends at the pill's edges.

  python3 effects/liquid_glass.py clip.mov --at 0 --dur 2 --text "In Seconds" -o out.mp4 [--y 0.5] [--size 70]
"""
import argparse, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

HN = "/System/Library/Fonts/HelveticaNeue.ttc"
F24 = 23.976


def ease_out(t, p=3):
    t = np.clip(t, 0, 1)
    return 1 - (1 - t) ** p


def sdf_rrect(xx, yy, cx, cy, w, h, r):
    dx = np.abs(xx - cx) - (w / 2 - r)
    dy = np.abs(yy - cy) - (h / 2 - r)
    return np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2) + np.minimum(np.maximum(dx, dy), 0) - r


def glass(img, cx, cy, w, h, strength=26.0, rim=1.0):
    H, W = img.shape[:2]
    r = min(w, h) / 2
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = sdf_rrect(xx, yy, cx, cy, w, h, r)
    inside = d < 0
    if not inside.any():
        return img
    gy, gx = np.gradient(d)
    nrm = np.sqrt(gx ** 2 + gy ** 2) + 1e-6
    depth = np.clip(-d / max(r, 1), 0, 1)                       # 0 at the edge, 1 deep inside
    bend = strength * (1 - depth) ** 2                           # refraction strongest at the rim (Displace offset -1, strength -4)
    sx = np.clip(xx + gx / nrm * bend, 0, W - 1).astype(np.int32)
    sy = np.clip(yy + gy / nrm * bend, 0, H - 1).astype(np.int32)
    out = img.copy()
    out[inside] = img[sy[inside], sx[inside]] * 1.04 + 0.025      # a touch brighter, like glass
    edge = np.exp(-(d / 1.6) ** 2) * rim                           # thin bright rim
    top = np.clip((cy - yy) / max(h / 2, 1), 0, 1)                 # rim brighter on the top edge
    out = out + edge[..., None] * (0.35 + 0.45 * top[..., None])
    return np.clip(out, 0, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=2.0)
    ap.add_argument("--text", default=""), ap.add_argument("--y", type=float, default=0.5), ap.add_argument("--size", type=int, default=70)
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    W, H = a.w, a.h
    frames = fx.read_frames(a.clip, a.at, n, W, H, a.fps)
    f = ImageFont.truetype(HN, a.size, index=1)
    tw = f.getlength(a.text) if a.text else W * 0.5
    pw, ph = tw + a.size * 1.1, a.size * 1.45                     # fitted pill around the text
    ball = a.size * 0.55
    k = a.fps / F24
    rise, grow = round(16 * k), round(8 * k)
    cy_end = H * a.y
    out = []
    for i, fr in enumerate(frames):
        if i < rise:
            p = float(ease_out(i / rise))
            cx, cy, w, h = W / 2, cy_end + (1 - p) * H * 0.12, ball, ball
        else:
            p = float(ease_out((i - rise) / grow))
            cx, cy = W / 2, cy_end
            w, h = ball + (pw - ball) * p, ball + (ph - ball) * p
        img = glass(fr, cx, cy, w, h)
        if a.text:
            op = float(np.clip((i - rise) / (6 * k), 0, 1))
            if op > 0:
                pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
                layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                d = ImageDraw.Draw(layer)
                l, t, r, b = d.textbbox((0, 0), a.text, font=f)
                d.text((W / 2 - (r - l) / 2 - l, cy_end - (b - t) / 2 - t), a.text, font=f, fill=(255, 255, 255, int(255 * op)))
                pil.alpha_composite(layer)
                img = np.asarray(pil.convert("RGB"), np.float32) / 255
        out.append(img)
    wr = fx.Writer(a.out, W, H, a.fps)
    for fr in out:
        wr.write(fr)
    wr.close()
    print(f"liquid glass: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
