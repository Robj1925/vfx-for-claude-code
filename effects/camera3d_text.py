#!/usr/bin/env python3
"""TX09 3D camera fly-through text.
Build (Resolve Fusion): Fusion clip; the video on an ImagePlane3D, each text template on its own ImagePlane3D at a different
depth (the first right up front), Camera3D + Merge3D + Renderer3D; Camera Z offset keyed over 75 frames with S keys smoothed
"a whole bunch"; a Gaussian Blur on each text ramps up as the camera reaches it.
Frame check of a reference edit, first 4 s (every frame): the camera creeps in; the first line (left, near) ghosts in,
grows and slides off the left edge going soft; the second line (right, further) does the same to the right a moment later;
the video behind grows slowly the whole time.

  python3 effects/camera3d_text.py clip.mov --at 0 --dur 3.2 --lines "built in code|no plugins|just Python" -o out.mp4
Each line gets its own plane: alternating left and right, each one deeper than the last.
"""
import argparse, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

HN = "/System/Library/Fonts/HelveticaNeue.ttc"
F24 = 23.976


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * t * (t * (6 * t - 15) + 10)            # smootherstep: S keys smoothed heavily


def text_sprite(text, size):
    f = ImageFont.truetype(HN, size, index=1)
    l, t, r, b = f.getbbox(text)
    pad = size // 2
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=f, fill=(255, 255, 255, 255))
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=3.2)
    ap.add_argument("--lines", required=True), ap.add_argument("--travel", type=float, default=3.4, help="camera Z distance")
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    W, H = a.w, a.h
    frames = fx.read_frames(a.clip, a.at, n, W, H, a.fps)
    lines = a.lines.split("|")
    base = 90
    sprites = [text_sprite(t, base * 2) for t in lines]            # drawn at 2x, scaled down by perspective
    planes = []
    for i, t in enumerate(lines):                                   # depth, side offset (fraction of W), height, start
        side = -0.16 if i % 2 == 0 else 0.16
        planes.append({"z": 1.6 + 1.2 * i, "x": side, "y": -0.04 + 0.05 * i, "start": i * 0.45})
    zbg, focal = 14.0, 1.0
    nmove = round(75 * a.fps / F24)
    out = []
    for k in range(n):
        cz = a.travel * float(smooth(k / nmove))
        # the video plane: it grows as the camera creeps toward it
        sbg = (zbg - 0) / (zbg - cz)
        bg = Image.fromarray((frames[k] * 255).astype(np.uint8))
        bw, bh = round(W * sbg), round(H * sbg)
        bg = bg.resize((bw, bh), Image.BICUBIC).crop(((bw - W) // 2, (bh - H) // 2, (bw - W) // 2 + W, (bh - H) // 2 + H)).convert("RGBA")
        t = k / a.fps
        for p, sp in sorted(zip(planes, sprites), key=lambda q: -q[0]["z"]):       # far to near
            d = p["z"] - cz
            if d <= 0.25 or t < p["start"]:
                continue
            s = focal / d * 0.5                                                      # 0.5: sprite was drawn at 2x
            op = min((t - p["start"]) / 0.25, 1.0)                                   # ghost in over ~7 frames
            blur = max(0.0, (focal / d - 1.4)) * 6                                   # Gaussian ramps up near the lens
            im = sp.resize((max(1, round(sp.width * s)), max(1, round(sp.height * s))), Image.BICUBIC)
            if blur > 0.3:
                im = im.filter(ImageFilter.GaussianBlur(blur))
            if op < 1:
                im.putalpha(im.getchannel("A").point(lambda v: int(v * op)))
            cx = W / 2 + p["x"] * W * focal / d
            cy = H * 0.42 + p["y"] * H * focal / d
            bg.alpha_composite(im, (round(cx - im.width / 2), round(cy - im.height / 2))) if (
                -im.width < cx - im.width / 2 < W and -im.height < cy - im.height / 2 < H) else None
        out.append(np.asarray(bg.convert("RGB"), np.float32) / 255)
    wr = fx.Writer(a.out, W, H, a.fps)
    for f in out:
        wr.write(f)
    wr.close()
    print(f"3D camera text: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
