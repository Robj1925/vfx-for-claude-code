#!/usr/bin/env python3
"""Transitions, rebuilt frame by frame from reference edits. The notes above each function list the measured frames.

  python3 effects/transitions.py leak  A.mov --cut 12.4  B.mov --b-in 3.0  -o out.mp4 [--look warm|prism]
  python3 effects/transitions.py roto  A.mov --cut 12.4  B.mov --b-in 3.0  -o out.mp4
  python3 effects/transitions.py blink A.mov --cut 12.4  B.mov --b-in 3.0  -o out.mp4

A plays until --cut (seconds in A), then B from --b-in (seconds in B). The output holds --pre seconds of A
and --post seconds of B (default 1.0 each), 1080x1920 at 30 fps (vertical Shorts format; --fps 24 for the 24 fps look).
"""
import argparse, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402


# =================================================================== T01 overlay light leak
def leak_frames(n, w, h, look="warm", seed=7):
    """Procedural light-leak overlay, n frames, peak in the middle. Rendered small, then upscaled (it is soft)."""
    from PIL import Image
    rng = np.random.default_rng(seed)
    lw, lh = w // 6, h // 6
    y, x = np.mgrid[0:lh, 0:lw].astype(np.float32)
    x, y = x / lw, y / lh
    if look == "warm":      # red leak swells in from the left edge, a white-hot band burns along the bottom
        blobs = [((1.0, 0.08, 0.05), -0.25, 1.15, 0.30, 0.55, 0.60), ((1.0, 0.45, 0.10), -0.35, 0.95, 0.70, 0.35, 0.45),
                 ((1.0, 0.95, 0.85), -0.10, 1.10, 0.97, 0.80, 0.10)]
    else:                   # prism: cyan, green and magenta streaks with a white core
        blobs = [((0.10, 0.85, 1.00), -0.20, 1.20, 0.45, 0.30, 0.55), ((0.30, 1.00, 0.45), -0.30, 1.05, 0.55, 0.18, 0.40),
                 ((0.95, 0.25, 0.85), -0.05, 1.25, 0.70, 0.22, 0.35), ((1.0, 1.0, 1.0), -0.10, 1.10, 0.55, 0.12, 0.22)]
    out = []
    for i in range(n):
        t = i / max(n - 1, 1)
        img = np.zeros((lh, lw, 3), np.float32)
        for col, x0, x1, cy, rx, ry in blobs:
            cx = x0 + (x1 - x0) * t
            g = np.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2) * 2.2)
            img += g[..., None] * np.array(col, np.float32)
        img *= 1 + 0.08 * rng.standard_normal()          # slight flicker, like a scanned leak
        big = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out.append(np.asarray(big, np.float32) / 255.0)
    return out


def t_leak(A, B, look="warm", n=12):
    """Cut at the middle of n frames; the overlay is screened (Resolve 'Add') over both sides, peak on the cut."""
    half = n // 2
    leaks = leak_frames(n, A.shape[2], A.shape[1], look)
    env = fx.key_curve(n, [(0, 0.0), (half - 1, 1.0), (half, 1.0), (n - 1, 0.0)])
    pre, post = len(A), len(B)
    frames = list(A) + list(B)
    c = pre
    for k in range(n):
        f = c - half + k
        if 0 <= f < len(frames):
            frames[f] = np.clip(frames[f] + leaks[k] * env[k] * 1.4, 0, 1)    # Add composite, slightly hot
    return frames


# =================================================================== T02 roto pre-cut silhouette
def t_roto(A, B, n=4, lift_keys=((0, 1.0), (2, 1.0), (3, 0.0)), cream=(0.93, 0.96, 0.86), soft=3):
    """The next clip's subject (frozen first frame of B, cut out) appears over the last n frames of A:
    first as a flat light silhouette (Color Corrector lift all the way up), then in true colour, then the cut."""
    from PIL import Image, ImageFilter
    b0 = B[0]
    m = fx.person_matte(b0)
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(soft)), np.float32) / 255.0
    lift = fx.key_curve(n, list(lift_keys))
    frames = list(A) + list(B)
    c = len(A)
    for k in range(n):
        f = c - n + k
        if f < 0:
            continue
        subj = b0 * (1 - lift[k]) + np.array(cream, np.float32) * lift[k]
        frames[f] = frames[f] * (1 - m[..., None]) + subj * m[..., None]
    return frames


# =================================================================== T03 radial blur blink
def t_blink(A, B, side=3, blur_peak=0.22, vig_peak=0.55):
    """Adjustment layer 3 frames each side of the cut: radial blur 0 -> peak on the cut -> 0 (S keys), plus an
    inverted soft ellipse (dark vignette) whose level rises and falls with it: a camera 'blink'."""
    n = 2 * side
    curve = fx.key_curve(n + 1, [(0, 0.0), (side, 1.0), (n, 0.0)])
    h, w = A.shape[1], A.shape[2]
    vig = 1 - fx.ellipse_mask(w, h, rx=0.62, ry=0.50, soft=0.45)                 # 1 at the edges
    frames = list(A) + list(B)
    c = len(A)
    for k in range(n + 1):
        f = c - side + k
        if not 0 <= f < len(frames):
            continue
        a = curve[k]
        img = fx.zoom_blur(frames[f], blur_peak * a)
        frames[f] = img * (1 - vig[..., None] * vig_peak * a)
    return frames


# =================================================================== T04 camera move zoom-out (one Transform node)
def _zoom(img, s):
    """Scale about the centre by s (s > 1 zooms in), cropped back to the frame."""
    from PIL import Image
    h, w = img.shape[:2]
    if abs(s - 1) < 1e-4:
        return img
    src = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    sw, sh = round(w * s), round(h * s)
    big = src.resize((sw, sh), Image.BICUBIC)
    if s >= 1:
        x0, y0 = (sw - w) // 2, (sh - h) // 2
        return np.asarray(big.crop((x0, y0, x0 + w, y0 + h)), np.float32) / 255
    canvas = Image.new("RGB", (w, h))
    canvas.paste(big, ((w - sw) // 2, (h - sh) // 2))
    return np.asarray(canvas, np.float32) / 255


def steep_s(t, p=3.0):
    """Spline: S keys pulled so the curve is gentle at both ends and very steep in the middle (on the cut)."""
    t = np.clip(t, 0, 1)
    return np.where(t < 0.5, 0.5 * (2 * t) ** p, 1 - 0.5 * (2 * (1 - t)) ** p)


def t_zoomout(A, B, fps, z0=1.30, before24=9, after24=5, blur_sub=6):
    """Adjustment clip over the cut, Transform zoom: zoomed in on frame 0 (cut - 9 frames at 24 fps), back to 1.0 four or five
    frames after the cut, S curve with the steep part on the cut, motion blur on. Reference check: A holds close, 2 blurred
    frames rush out through the cut, B lands wide and settles in about 3 frames."""
    k = fps / 23.976
    nb, na = round(before24 * k), round(after24 * k)
    frames = list(A) + list(B)
    c = len(A)
    zs = {}
    for i in range(c - nb, c + na + 1):
        t = (i - (c - nb)) / (nb + na)
        zs[i] = 1 + (z0 - 1) * (1 - float(steep_s(t)))
    for i in range(max(0, c - nb), min(len(frames), c + na + 1)):
        z_prev = zs.get(i - 1, zs[i])
        subs = [z_prev + (zs[i] - z_prev) * (j + 1) / blur_sub for j in range(blur_sub)]  # shutter over the frame
        if abs(zs[i] - z_prev) < 0.004:
            frames[i] = _zoom(frames[i], zs[i])
        else:
            frames[i] = sum(_zoom(frames[i], s) for s in subs) / blur_sub
    for i in range(0, max(0, c - nb)):
        frames[i] = _zoom(frames[i], z0)                      # A holds at the start zoom before the move
    return frames


# =================================================================== T05 camera blur (manual focus pull)
def t_focus(A, B, fps, zoom_to=1.06, before24=9, after24=6):
    """Adjustment clip over the cut: a subtle S-curve zoom in, plus Gaussian blur keys: 0, up a little, down, then up right
    before the cut, peak on the cut, down after. Reads like the lens losing and finding focus."""
    from PIL import Image, ImageFilter
    k = fps / 23.976
    nb, na = round(before24 * k), round(after24 * k)
    n = nb + na
    blur_px = fx.key_curve(n + 1, [(0, 0), (round(2 * k), 2), (round(4 * k), 0), (nb - round(2 * k), 0), (nb, 5),
                                   (nb + round(3 * k), 0), (n, 0)])
    zoom = 1 + (zoom_to - 1) * fx.key_curve(n + 1, [(0, 0), (n, 1)])
    frames = list(A) + list(B)
    c = len(A)
    for j in range(n + 1):
        i = c - nb + j
        if not 0 <= i < len(frames):
            continue
        img = _zoom(frames[i], float(zoom[j]))
        if blur_px[j] > 0.3:
            pil = Image.fromarray((img * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(float(blur_px[j]) * img.shape[1] / 1080))
            img = np.asarray(pil, np.float32) / 255
        frames[i] = img
    return frames


# =================================================================== T07 punch-in flash (from a reel breakdown)
def t_punch(A, B, fps, zoom_b=1.15):
    """Measured on a reference edit, every unique frame: the last 2 frames of A wash
    to white from the left (an overlay in Add mode), the first frame of B is white over a red tint, then B holds punched in
    (about 1.15x) with no ease: a hard cut that 'pops' to a tighter framing."""
    H, W = A.shape[1], A.shape[2]
    k = max(1, round(fps / 23.976))
    ramp = np.clip(1.2 - np.linspace(0, 1, W, dtype=np.float32)[None, :, None] * 0.9, 0, 1)   # brighter on the left
    frames = list(A) + [_zoom(f, zoom_b) for f in B]
    c = len(A)
    for j in range(2 * k):                                  # A washes out
        f = c - 2 * k + j
        a = (j + 1) / (2 * k)
        frames[f] = np.clip(frames[f] + ramp * a * 1.3, 0, 1)
    for j in range(k):                                      # one frame: white over red
        red = frames[c + j] * np.array([1.0, 0.15, 0.15], np.float32) + np.array([0.55, 0.05, 0.05], np.float32)
        frames[c + j] = np.clip(red * 0.6 + 0.4 * ramp, 0, 1)
    return frames


# =================================================================== T08 CRT white flash reset
def t_crt(A, B, fps, zoom_a=1.3, n24=4):
    """On a podcast clip the shot punches in on a line, then instead of a plain cut back to normal a CRT flash overlay
    drops in and the shot comes back out wide. Frame check of the reference, every frame (about 1.4 s):
    the punched-in shot, then 4 frames of solid white, then the shot back at normal framing. Ours adds faint CRT scan lines to the
    white so it reads as a screen flash; B returns un-zoomed."""
    H, W = A.shape[1], A.shape[2]
    k = max(1, round(n24 * fps / 23.976))
    lines = (np.arange(H) % 6 < 3).astype(np.float32)[:, None, None] * 0.06
    frames = [_zoom(f, zoom_a) for f in A] + list(B)
    c = len(A)
    for j in range(k):
        if c + j < len(frames):
            tint = np.array([1.0, 0.98, 0.96], np.float32)
            frames[c + j] = np.clip(np.ones((H, W, 3), np.float32) * tint - lines * (1 - j / k), 0, 1)
    return frames


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["leak", "roto", "blink", "zoomout", "focus", "whiteflash", "punch", "crt"])
    ap.add_argument("--text", help="zoomout only: a word in the gradient glow style (TX05) that rides the move")
    ap.add_argument("a"), ap.add_argument("--cut", type=float, required=True)
    ap.add_argument("b"), ap.add_argument("--b-in", type=float, default=0.0)
    ap.add_argument("--pre", type=float, default=1.0), ap.add_argument("--post", type=float, default=1.0)
    ap.add_argument("--look", default="warm", choices=["warm", "prism"])
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    npre, npost = round(a.pre * a.fps), round(a.post * a.fps)
    A = fx.read_frames(a.a, a.cut - a.pre, npre, a.w, a.h, a.fps)
    B = fx.read_frames(a.b, a.b_in, npost, a.w, a.h, a.fps)
    if a.text and a.kind == "zoomout":                      # tip: the text goes UNDER the adjustment clip, so it zooms too
        from text_fx import render
        txt = render("gradglow", a.text, a.w, a.h, a.fps, a.post, 0.5)          # it appears on the cut, with clip B
        B = np.array([t[..., :3] + f * (1 - t[..., 3:4]) for f, t in zip(B, txt)])
    frames = {"leak": lambda: t_leak(A, B, a.look), "roto": lambda: t_roto(A, B), "blink": lambda: t_blink(A, B),
              "zoomout": lambda: t_zoomout(A, B, a.fps), "focus": lambda: t_focus(A, B, a.fps),
              # T06 white flash: same build as roto, 5 frames, lift 1 -> 0 on S keys, warm white
              "punch": lambda: t_punch(A, B, a.fps),
              "crt": lambda: t_crt(A, B, a.fps),
              "whiteflash": lambda: t_roto(A, B, n=round(5 * a.fps / 23.976), lift_keys=((0, 1.0), (round(5 * a.fps / 23.976) - 1, 0.0)), cream=(0.97, 0.93, 0.91))}[a.kind]()
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for f in frames:
        wr.write(f)
    wr.close()
    print(f"{a.kind}: {len(frames)} frames -> {a.out}")


if __name__ == "__main__":
    main()
