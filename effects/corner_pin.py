#!/usr/bin/env python3
"""FX14 Screen replacement (corner pin).
Build (Resolve Fusion): Planar Tracker on the laptop screen (box, Set, track right and left), Operation Corner Pin, the four
corners dragged onto the screen corners at 200 to 400 %, then the new image through Merge > Color Corrector > Blur into the
tracker's corner-pin input; saturation down and a tint toward the shot so it is "not too perfect". Frame check of a reference
result (every 3 s, plus a full frame): the replacement sits inside the screen bezel, a little darker and less saturated than
the source, edges slightly soft.

Ours has no automatic planar tracker (no OpenCV here): give the screen corners at a few times and they are interpolated.

  python3 effects/corner_pin.py shot.mov --at 0 --dur 2 --content screenshot.png --corners pins.json -o out.mp4
pins.json: [{"t": 0.0, "c": [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]}, {"t": 1.7, "c": [...]}]   (top-left, top-right, bottom-right,
bottom-left, output pixels, t in seconds from --at). --content may be an image or a video.
"""
import argparse, json, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageFilter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402


def coeffs(dst, src):
    """PIL PERSPECTIVE coefficients mapping output (dst) points back to source points."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def corners_at(keys, t):
    keys = sorted(keys, key=lambda k: k["t"])
    if t <= keys[0]["t"]:
        return np.array(keys[0]["c"], float)
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t <= b["t"]:
            f = (t - a["t"]) / max(b["t"] - a["t"], 1e-6)
            return np.array(a["c"], float) * (1 - f) + np.array(b["c"], float) * f
    return np.array(keys[-1]["c"], float)


def match(img, sat=0.8, gain=0.88, blur=0.8):
    a = np.asarray(img.convert("RGB"), np.float32) / 255
    g = a.mean(2, keepdims=True)
    a = (g + (a - g) * sat) * gain
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return out.filter(ImageFilter.GaussianBlur(blur))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shot"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=2.0)
    ap.add_argument("--content", required=True), ap.add_argument("--corners", required=True)
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    W, H = a.w, a.h
    shots = fx.read_frames(a.shot, a.at, n, W, H, a.fps)
    keys = json.loads(Path(a.corners).read_text())
    is_img = Path(a.content).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    if is_img:
        src_frames = [match(Image.open(a.content))] * n
    else:
        m = fx.probe(a.content)
        cw, ch = m["w"], m["h"]
        vids = fx.read_frames(a.content, 0, n, cw, ch, a.fps)
        src_frames = [match(Image.fromarray((v * 255).astype(np.uint8))) for v in vids]
    wr = fx.Writer(a.out, W, H, a.fps)
    for i in range(n):
        src = src_frames[i]
        sw, sh = src.size
        c = corners_at(keys, i / a.fps)
        k = coeffs(c.tolist(), [(0, 0), (sw, 0), (sw, sh), (0, sh)])
        warped = src.convert("RGBA").transform((W, H), Image.PERSPECTIVE, k, Image.BICUBIC)
        mask = Image.new("L", (sw, sh), 255).transform((W, H), Image.PERSPECTIVE, k, Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.8))
        base = Image.fromarray((shots[i] * 255).astype(np.uint8)).convert("RGBA")
        base.paste(warped, (0, 0), mask)
        wr.write(np.asarray(base.convert("RGB"), np.float32) / 255)
    wr.close()
    print(f"corner pin: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
