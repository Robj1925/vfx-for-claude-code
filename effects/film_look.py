#!/usr/bin/env python3
"""FX15 Film look grade.
Build (Resolve 20 Color page, node tree): noise reduction, exposure, balance, look/skin, colour space transform (S-Log to Rec.709), a LUT
with the key output gain down (LUT opacity), then Film Look Creator: preset 35 mm, Color Blend and Film Look Blend all the way down
(else skin goes ghostly), vignette about halfway, halation (the orange glow around bright edges and skin) to taste, bloom small,
grain on but not too much. Frame check of a reference graded shot (first frame full size, plus the graded viewer every 8 s): muted,
slightly olive greens, soft lifted blacks, warm skin, a gentle vignette, fine grain, bright edges with a faint warm glow.

  python3 effects/film_look.py clip.mov --at 0 --dur 3 -o out.mp4 [--strength 1.0] [--grain 0.035] [--halation 0.18] [--vignette 0.5]
  --compare writes the original on the left half and the graded on the right (for choosing settings).
"""
import argparse, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageFilter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402


def blur(a, r):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255


def grade(f, rng, strength=1.0, grain=0.035, halation=0.18, vignette=0.5, vig=None):
    x = f
    # gentle filmic curve: soft toe (lifted blacks) and shoulder (highlight roll-off)
    s_ = x * x * (3 - 2 * x)                                   # S curve for a little contrast
    x = 0.03 + 0.95 * (0.6 * x + 0.4 * s_)                     # lifted toe (0.03), shoulder rolls off at 0.98
    x = np.clip(x, 0, 1)
    # muted, olive greens; overall saturation down a touch; warm highlights, cool-neutral shadows
    g = x.mean(2, keepdims=True)
    x = g + (x - g) * 0.86
    green = np.clip(x[..., 1:2] - np.maximum(x[..., 0:1], x[..., 2:3]), 0, 1)
    x = x - green * np.array([0.0, 0.25, 0.0], np.float32) + green * np.array([0.08, 0.0, 0.0], np.float32)
    x = x + (g ** 2) * np.array([0.035, 0.012, -0.03], np.float32)
    # halation: red-orange glow from bright areas
    hi = np.clip((g - 0.62) / 0.38, 0, 1) * x
    x = x + blur(hi, 14) * np.array([1.0, 0.45, 0.2], np.float32) * halation
    # bloom: a small soft glow
    x = x + blur(np.clip(x - 0.75, 0, 1), 6) * 0.25
    if vignette and vig is not None:
        x = x * (1 - vig * vignette)
    x = f + (np.clip(x, 0, 1) - f) * strength
    if grain:
        x = x + rng.normal(0, grain, x.shape[:2] + (1,)).astype(np.float32)
    return np.clip(x, 0, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=3.0)
    ap.add_argument("--strength", type=float, default=1.0), ap.add_argument("--grain", type=float, default=0.035)
    ap.add_argument("--halation", type=float, default=0.18), ap.add_argument("--vignette", type=float, default=0.5)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    frames = fx.read_frames(a.clip, a.at, n, a.w, a.h, a.fps)
    vig = (1 - fx.ellipse_mask(a.w, a.h, rx=0.75, ry=0.62, soft=0.55))[..., None] * 0.55
    rng = np.random.default_rng(3)
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for f in frames:
        g = grade(f, rng, a.strength, a.grain, a.halation, a.vignette, vig)
        if a.compare:
            g = g.copy()
            g[:, : a.w // 2] = f[:, : a.w // 2]
            g[:, a.w // 2 - 1: a.w // 2 + 1] = 1.0
        wr.write(g)
    wr.close()
    print(f"film look: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
