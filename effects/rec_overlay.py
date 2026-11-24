#!/usr/bin/env python3
"""FX05 REC recording overlay: a small white "REC." with a red dot, held over the whole video, flickering on at the start.
Build (checked frame by frame on a reference edit): a flicker text preset types "REC.", stretched to the end of the video,
then Fusion > Template > Modifiers > Text > Character Level Styling: the dot alone set to red, so it reads as a live recording.
Measured: heavy condensed sans, about 4.5 % of the frame width tall, steady once on, no blinking.

  python3 effects/rec_overlay.py clip.mov --at 0 --dur 6 -o out.mp4 [--x 0.5 --y 0.5] [--size 70] [--no-flicker]
"""
import argparse, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402
from text_fx import glitch_opacity  # flicker opacity keys, shared with TX03  # noqa: E402

HN = "/System/Library/Fonts/HelveticaNeue.ttc"   # 9 = Condensed Black


def rec_sprite(size, red=(255, 45, 45)):
    f = ImageFont.truetype(HN, size, index=9)
    w_rec = f.getlength("REC")
    l, t, r, b = f.getbbox("REC.")
    pad = 20
    im = Image.new("RGBA", (int(r - l) + 2 * pad, int(b - t) + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((pad - l, pad - t), "REC", font=f, fill=(255, 255, 255, 255))
    d.text((pad - l + w_rec, pad - t), ".", font=f, fill=red + (255,))
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=6.0)
    ap.add_argument("--x", type=float, default=0.5), ap.add_argument("--y", type=float, default=0.5)
    ap.add_argument("--size", type=int, default=70), ap.add_argument("--no-flicker", action="store_true")
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    frames = fx.read_frames(a.clip, a.at, n, a.w, a.h, a.fps)
    sp = rec_sprite(a.size)
    pos = (round(a.w * a.x - sp.width / 2), round(a.h * a.y - sp.height / 2))
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for i, f in enumerate(frames):
        op = 1.0 if a.no_flicker else glitch_opacity(i * 23.976 / a.fps)
        img = Image.fromarray((f * 255).astype(np.uint8)).convert("RGBA")
        if op > 0:
            s = sp.copy()
            s.putalpha(s.getchannel("A").point(lambda v: int(v * op)))
            img.alpha_composite(s, pos)
        wr.write(np.asarray(img.convert("RGB"), np.float32) / 255)
    wr.close()
    print(f"REC overlay: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
