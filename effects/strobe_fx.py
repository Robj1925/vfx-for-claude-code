#!/usr/bin/env python3
"""Three strobe effects rebuilt frame by frame from reference edits.

  stutter   FX08  Stutter push-in: one 2-frame slice repeated over and over (cut, 2 frames on, duplicate x4, then copy the
                    group of 4), with an adjustment-clip Transform zoom across the whole stutter: S keys pulled so it rushes in
                    and then creeps. Use it on a word where the audio glitches or on a beat.
  redflash  FX09  Red flash strobe: two clips cut into 2-frame slices, alternating. Every other slice gets a copy of itself
                    on top in Linear Dodge (a hot glow); the slices without the glow get a red Solid Color in Darken, so they
                    turn into dark red silhouettes. Checked every frame of the reference: the order runs
                    A, A red, A, B glow, B red, B glow ... in 2-frame steps.
  vigblink  FX17  Vignette blink: dark soft edges flash on for 1 to 2 frames at a time, a few times (see vigblink()).

  python3 effects/strobe_fx.py stutter  clip.mov --at 4.2 --dur 1.6 -o out.mp4 [--zoom 1.25]
  python3 effects/strobe_fx.py redflash A.mov --at 2 B.mov --b-at 5 --dur 2 -o out.mp4
  python3 effects/strobe_fx.py vigblink clip.mov --at 0 --dur 1 -o out.mp4
"""
import argparse, sys, numpy as np
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

F24 = 23.976


def zoom(img, s):
    h, w = img.shape[:2]
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    sw, sh = round(w * s), round(h * s)
    big = im.resize((sw, sh), Image.BICUBIC)
    x0, y0 = (sw - w) // 2, (sh - h) // 2
    return np.asarray(big.crop((x0, y0, x0 + w, y0 + h)), np.float32) / 255


def stutter(frames, fps, n, z=1.25, slice24=2):
    k = max(1, round(slice24 * fps / F24))
    sl = frames[:k]
    out = [sl[i % k] for i in range(n)]
    # S keys pulled: comes in really fast, then goes in really slow
    t = np.linspace(0, 1, n)
    p = 1 - (1 - t) ** 5.0                      # measured: most of the push in the first few frames, then a creep
    return [zoom(f, 1 + (z - 1) * pi) for f, pi in zip(out, p)]


def redflash(A, B, fps, n, red=(1.0, 0.0, 0.0), glow=0.9):
    k = max(1, round(2 * fps / F24))
    pattern = [("A", ""), ("A", "red"), ("A", ""), ("B", "glow"), ("B", "red"), ("B", "glow")]
    out = []
    for i in range(n):
        src, fxk = pattern[(i // k) % len(pattern)]
        f = (A if src == "A" else B)[i]
        if fxk == "glow":                                   # copy on top in Linear Dodge (add)
            f = np.clip(f + f * glow, 0, 1)
        elif fxk == "red":                                  # red Solid Color, composite Darken
            f = np.minimum(f, np.array(red, np.float32))
        out.append(f)
    return out


def vigblink(frames, fps, n, peak=0.4):
    """FX17: black Solid Color compound clip with an inverted, very soft Ellipse (a dark vignette); opacity
    'tricks': up 3 frames in (never above about 40), back down, up a little, down again. Frame check of the reference,
    every unique frame: the dark edges flash on for 1 to 2 frames at a time, a few times, then the picture is clean."""
    H, W = frames[0].shape[:2]
    vig = (1 - fx.ellipse_mask(W, H, rx=0.62, ry=0.55, soft=0.6))[..., None]
    keys24 = {3: 1.0, 4: 0.6, 6: 0.5, 9: 0.85, 10: 0.4, 14: 0.6}       # held 1 frame each (24 fps), 0 elsewhere
    out = []
    for i, f in enumerate(frames[:n]):
        a = keys24.get(int(i * F24 / fps), 0.0) * peak
        out.append(f * (1 - vig * a))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["stutter", "redflash", "vigblink"]), ap.add_argument("clip")
    ap.add_argument("b", nargs="?"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--b-at", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=1.6), ap.add_argument("--zoom", type=float, default=1.25)
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    A = fx.read_frames(a.clip, a.at, n, a.w, a.h, a.fps)
    if a.kind == "stutter":
        out = stutter(A, a.fps, n, a.zoom)
    elif a.kind == "vigblink":
        out = vigblink(A, a.fps, n)
    else:
        B = fx.read_frames(a.b, a.b_at, n, a.w, a.h, a.fps)
        out = redflash(A, B, a.fps, n)
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for f in out:
        wr.write(f)
    wr.close()
    print(f"{a.kind}: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
