#!/usr/bin/env python3
"""FX13 Aesthetic moving gradient background.
Build (Resolve Fusion): Fusion composition, Fast Noise (detail 1.1, contrast and brightness up a tad, scale down so it is zoomed right in, seethe
rate low for a slow drift), Color > Gradient with three points (black, blue in the middle, light), then Film Grain (power a little
down). Frame check of a reference edit (3 fps, first 4 s, plus the full first frame): deep black on one side melting into a grainy
royal blue with dark speckle, slow drift; white text and file cards sit on top.

  python3 effects/noise_bg.py --dur 4 -o bg.mp4 [--colors "0,0,0;22,60,190;150,180,255"] [--rate 0.15] [--grain 0.06]
A generator: no input clip. Use it as the plate behind titles (TX*) or cards (TX10 --image).
"""
import argparse, sys, numpy as np
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402


def value_noise(gw, gh, seed):
    return np.random.default_rng(seed).random((gh, gw)).astype(np.float32)


def smooth_up(grid, W, H):
    return np.asarray(Image.fromarray((grid * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dur", type=float, default=4.0), ap.add_argument("--rate", type=float, default=0.06)
    ap.add_argument("--colors", default="0,0,0;18,45,150;70,110,215"), ap.add_argument("--grain", type=float, default=0.06)
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    W, H = a.w, a.h
    cols = np.array([[float(v) / 255 for v in c.split(",")] for c in a.colors.split(";")], np.float32)
    n = round(a.dur * a.fps)
    # two octaves of very low-frequency noise (Fast Noise scale down = zoomed in), cross-faded over time (seethe)
    oct1 = [smooth_up(value_noise(2, 3, s), W, H) for s in range(8)]
    oct2 = [smooth_up(value_noise(4, 6, 100 + s), W, H) for s in range(8)]
    speck = smooth_up(value_noise(W // 6, H // 6, 999), W, H)          # dark speckle seen in the reference frame
    xs = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    rng = np.random.default_rng(7)
    wr = fx.Writer(a.out, W, H, a.fps)
    for i in range(n):
        t = i / a.fps * a.rate * 4
        k, f = int(t) % 7, t - int(t)
        f = f * f * (3 - 2 * f)
        v = 0.85 * (oct1[k] * (1 - f) + oct1[k + 1] * f) + 0.15 * (oct2[k] * (1 - f) + oct2[k + 1] * f)
        v = np.clip((v - 0.5) * 0.7 + 0.36 + (xs - 0.5) * 1.1, 0, 1)     # contrast up, a side-to-side lean like the reference frame
        v = v - np.clip(speck - 0.83, 0, 1) * 1.4 * v                   # speckle
        seg = np.clip(v * (len(cols) - 1), 0, len(cols) - 1 - 1e-4)
        j = seg.astype(np.int32)
        fr = (seg - j)[..., None]
        img = cols[j] * (1 - fr) + cols[j + 1] * fr
        img = img + rng.normal(0, a.grain, (H, W, 1)).astype(np.float32)  # film grain
        wr.write(np.clip(img, 0, 1))
    wr.close()
    print(f"noise background: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
