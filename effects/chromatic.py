#!/usr/bin/env python3
"""FX16 Chromatic aberration. The equivalent in Resolve:
Lens Distortion node with Split Channels on (red, green, blue distortion each about -0.4, then adjusted per channel), as the last
node of the grade (Color page settings). Gives thin red and cyan fringes that grow toward the frame edges.

  python3 effects/chromatic.py clip.mov --at 0 --dur 3 -o out.mp4 [--amount 0.006]
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("clip"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=3.0)
ap.add_argument("--amount", type=float, default=0.006)
ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
ap.add_argument("-o", "--out", required=True)
a = ap.parse_args()
n = round(a.dur * a.fps)
wr = fx.Writer(a.out, a.w, a.h, a.fps)
for f in fx.read_frames(a.clip, a.at, n, a.w, a.h, a.fps):
    wr.write(fx.chromatic(f, a.amount))
wr.close()
print(f"chromatic aberration: {n} frames -> {a.out}")
