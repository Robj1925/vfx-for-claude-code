#!/usr/bin/env python3
"""FX02 4:3 rounded window: the clip shows through a 4:3 rectangle with rounded corners on a black background.
Build: Fusion composition,
Background node (black), Rectangle node sized to 4:3, rounded corners up, Invert so the video shows through.
The reference is only visible small in the Fusion viewer, so the values come from the Rectangle settings and viewer (Width 0.607, Height 1.0, Corner Radius 0.024: about 3.4 % of the window width).

  python3 effects/window_43.py clip.mov --at 2 --dur 3 -o out.mp4 [--width 0.92] [--radius 0.06] [--y 0.5] [--bg 0,0,0]
"""
import argparse, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402


def rounded_mask(W, H, cx, cy, w, h, r):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = np.maximum(np.abs(x - cx) - (w / 2 - r), 0)
    dy = np.maximum(np.abs(y - cy) - (h / 2 - r), 0)
    d = np.sqrt(dx * dx + dy * dy) - r
    return np.clip(0.5 - d, 0, 1)                       # 1 px anti-aliased edge


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=3.0)
    ap.add_argument("--width", type=float, default=0.92), ap.add_argument("--radius", type=float, default=0.031)
    ap.add_argument("--y", type=float, default=0.5), ap.add_argument("--bg", default="0,0,0", help="background colour r,g,b in 0..255")
    ap.add_argument("--focus", type=float, default=0.32, help="which part of a 9:16 clip fills the window (0 top, 1 bottom)")
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    ww = min(a.width * a.w, a.h * 0.92 * 4 / 3)               # landscape: keep the 4:3 window inside the frame height
    wh = ww * 3 / 4
    bw, bh = round(ww), round(wh)
    full_h = max(round(bw * a.h / a.w), bh)                              # the clip at the window's width, then a 4:3 slice
    full = fx.read_frames(a.clip, a.at, n, bw, full_h, a.fps)
    top = int(np.clip(a.focus * full_h - bh / 2, 0, full_h - bh))
    frames = full[:, top:top + bh]
    m = rounded_mask(a.w, a.h, a.w / 2, a.h * a.y, bw, bh, a.radius * a.w)[..., None]
    bg = np.array([float(v) for v in a.bg.split(",")], np.float32) / 255
    x0, y0 = round(a.w / 2 - bw / 2), round(a.h * a.y - bh / 2)
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for f in frames:
        canvas = np.broadcast_to(bg, (a.h, a.w, 3)).copy()
        canvas[y0:y0 + bh, x0:x0 + bw] = f
        wr.write(canvas * m + bg * (1 - m))
    wr.close()
    print(f"4:3 window: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
