#!/usr/bin/env python3
"""FX01 Box flash (inverted boxes), rebuilt frame by frame from a reference
opening montage (8 s, every frame).

Build: a white Solid Color on the track above, composite mode Difference (or the clip duplicated with Exclusion /
Divide), cropped to a box. Inside the box the picture is inverted. A new box every 5 or 6 frames, some gaps of about
8 frames with no box, sometimes two boxes at once, sometimes the whole frame, sometimes a thin bar for 1 frame.

  python3 effects/box_flash.py clip.mov --at 3.0 --dur 3.0 -o out.mp4                 # automatic pattern, head box from the person matte
  python3 effects/box_flash.py clip.mov --at 3.0 --dur 3.0 --boxes boxes.json -o out.mp4
boxes.json: [{"f": 0, "n": 5, "box": [x, y, w, h]}, ...]  (frames from the start, box in 0..1 of the frame)
--mode difference (white solid, a clean invert) or exclusion (softer, washed).
"""
import argparse, json, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402


def head_box(frame):
    """Box around the head and shoulders from the Vision person matte (the usual target: the head only)."""
    m = fx.person_matte(frame) > 0.5
    ys, xs = np.nonzero(m)
    if not len(ys):
        return [0.3, 0.2, 0.4, 0.3]
    h, w = m.shape
    top = ys.min()
    hh = (ys.max() - top) * 0.42                      # head and a little shoulder
    row = m[top:int(top + hh)]
    cols = np.nonzero(row.any(0))[0]
    x0, x1 = cols.min(), cols.max()
    pad = 0.06
    return [max(x0 / w - pad, 0), max(top / h - pad / 2, 0), min((x1 - x0) / w + 2 * pad, 1), min(hh / h + pad, 1)]


def auto_pattern(n, head):
    """Rhythm from the reference montage (24 fps frames): box 5-6 frames, gap, two at once, full frame, 1-frame bar."""
    hx, hy, hw, hh = head
    plan = [
        (0, 6, head),                                  # head box
        (8, 5, [0.62, 0.08, 0.30, 0.22]),              # sky corner box
        (14, 1, [0.47, 0.0, 0.03, 1.0]),               # thin vertical bar, 1 frame
        (16, 5, [hx - 0.05, hy, hw + 0.10, hh]),       # head again, a bit wider (back to the head)
        (16, 5, [0.05, 0.62, 0.40, 0.12]),             # second box at the same time
        (23, 3, [0.0, 0.0, 1.0, 1.0]),                 # whole frame
        (34, 6, [0.12, 0.30, 0.76, 0.28]),             # wide band after an 8-frame gap
        (40, 1, [0.0, 0.71, 1.0, 0.012]),              # thin horizontal bar, 1 frame
        (42, 6, head),
        (50, 4, [0.55, 0.45, 0.30, 0.30]),
        (56, 5, [0.0, 0.0, 1.0, 1.0]),
        (63, 6, head),
    ]
    out, period = [], 70
    for rep in range(0, n, period):
        out += [{"f": rep + f, "n": k, "box": b} for f, k, b in plan if rep + f < n]
    return out


def apply(frames, boxes, mode, fps):
    H, W = frames[0].shape[:2]
    scale = fps / 23.976
    out = []
    for i, fr in enumerate(frames):
        img = fr.copy()
        f24 = i / scale
        for b in boxes:
            if b["f"] <= f24 < b["f"] + b["n"]:
                x, y, w, h = b["box"]
                x0, y0 = int(max(x, 0) * W), int(max(y, 0) * H)
                x1, y1 = int(min(x + w, 1) * W), int(min(y + h, 1) * H)
                if x1 - x0 < 2 and w > 0:
                    x1 = x0 + 2
                if y1 - y0 < 2 and h > 0:
                    y1 = y0 + 2
                reg = img[y0:y1, x0:x1]
                img[y0:y1, x0:x1] = (1 - reg) if mode == "difference" else (reg + 1 - 2 * reg * 1.0) * 0.5 + reg * 0.5
        out.append(img)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=3.0)
    ap.add_argument("--boxes"), ap.add_argument("--mode", default="difference", choices=["difference", "exclusion"])
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    frames = fx.read_frames(a.clip, a.at, n, a.w, a.h, a.fps)
    boxes = json.loads(Path(a.boxes).read_text()) if a.boxes else auto_pattern(round(n * 23.976 / a.fps), head_box(frames[0]))
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for f in apply(frames, boxes, a.mode, a.fps):
        wr.write(f)
    wr.close()
    print(f"box flash: {n} frames, {len(boxes)} boxes -> {a.out}")


if __name__ == "__main__":
    main()
