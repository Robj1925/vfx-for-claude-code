#!/usr/bin/env python3
"""FX03 Face lock follow: the head stays still in the frame while the world moves around it.
Build: Fusion Planar Tracker on the face,
motion type Translation, track forward, Operation Stabilize, then zoom in until the black edges are gone.
Ours: the head position per frame from the Vision person matte (top 40 % of the person), smoothed over 3 frames,
the frame shifted so the head stays where it was on frame 0, then a zoom to hide the edges.

  python3 effects/face_lock.py walking.mov --at 2 --dur 3 -o out.mp4 [--zoom 1.18]
Best on handheld walking or moving shots of a person; a locked-off talking head barely changes.
"""
import argparse, subprocess, sys, tempfile, numpy as np
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402


def head_track(frames):
    """Head centre (x, y in px) per frame, from one Vision segmentation pass over a small copy of the clip."""
    seg = fx.segment_bin()
    sw, sh = 270, 480
    H, W = frames[0].shape[:2]
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "s.mp4"
        p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{sw}x{sh}", "-r", "30",
                              "-i", "-", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(clip)], stdin=subprocess.PIPE)
        for f in frames:
            p.stdin.write(np.asarray(Image.fromarray((f * 255).astype(np.uint8)).resize((sw, sh)), np.uint8).tobytes())
        p.stdin.close()
        p.wait()
        raw = subprocess.run([str(seg), str(clip), "balanced"], capture_output=True).stdout
    m = np.frombuffer(raw, np.uint8)[: (len(raw) // (sw * sh)) * sw * sh].reshape(-1, sh, sw).astype(np.float32) / 255
    pts = []
    for k in range(len(frames)):
        mk = m[min(k, len(m) - 1)] > 0.5
        ys, xs = np.nonzero(mk)
        if not len(ys):
            pts.append(pts[-1] if pts else (W / 2, H / 3))
            continue
        top, bot = ys.min(), ys.max()
        sel = ys < top + 0.4 * (bot - top)
        pts.append((xs[sel].mean() * W / sw, ys[sel].mean() * H / sh))
    pts = np.array(pts)
    k = np.ones(3) / 3
    sm = np.stack([np.convolve(np.pad(pts[:, i], 1, mode="edge"), k, "valid") for i in range(2)], 1)
    return sm


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=3.0)
    ap.add_argument("--zoom", type=float, default=1.18)
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    frames = fx.read_frames(a.clip, a.at, n, a.w, a.h, a.fps)
    tr = head_track(frames)
    x0, y0 = tr[0]
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for f, (x, y) in zip(frames, tr):
        im = Image.fromarray((f * 255).astype(np.uint8))
        Z = a.zoom
        big = im.resize((round(a.w * Z), round(a.h * Z)), Image.BICUBIC)
        # place so the tracked head lands on the frame-0 head position
        left = x * Z - x0
        top = y * Z - y0
        left = float(np.clip(left, 0, big.width - a.w))
        top = float(np.clip(top, 0, big.height - a.h))
        out = big.crop((round(left), round(top), round(left) + a.w, round(top) + a.h))
        wr.write(np.asarray(out, np.float32) / 255)
    wr.close()
    print(f"face lock: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
