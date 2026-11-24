#!/usr/bin/env python3
"""Text effects, rebuilt frame by frame from a reference edit.

  python3 effects/text_fx.py fade    "The Fade Text Effect"  --bg clip.mov --at 2.0 -o out.mp4
  python3 effects/text_fx.py premium "Premium|Text"           --bg clip.mov --at 2.0 -o out.mp4
  python3 effects/text_fx.py glitch  "Glitch Text Effect"     --bg clip.mov --at 2.0 -o out.mp4

Words are split on spaces (or on | to force lines); each word is its own line, stacked tight like the reference.
--bg can be a video or an image; --alpha out.mov also writes the text alone (ProRes 4444) for Resolve.
--y sets the stack centre (0..1 of the height, default 0.5); --size the font px (default per effect).
"""
import argparse, subprocess, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

HN = "/System/Library/Fonts/HelveticaNeue.ttc"     # 0 Regular, 1 Bold, 3 Bold Italic
GARAMOND = str(Path.home() / "Library/Fonts/AppleGaramond.ttf")      # any Garamond works; falls back to a system serif
SERIF_FALLBACK = [("/System/Library/Fonts/Supplemental/Baskerville.ttc", 0), ("/System/Library/Fonts/Times.ttc", 0)]
SRC_FPS = 23.976                                     # reference frame counts are at 24 fps; converted to the output fps


def out_cubic(t):
    """Spline: ease 'out cubic', handles pulled so it starts very fast and lands slowly (close to out-quint)."""
    t = np.clip(t, 0, 1)
    return 1 - (1 - t) ** 4.2


# ------------------------------------------------------------------ word sprites (RGBA float, premultiplied)
def glyph_alpha(word, font, stroke=0, shear=0.0, pad=40):
    l, t, r, b = font.getbbox(word, stroke_width=stroke)
    w, h = r - l + 2 * pad, b - t + 2 * pad
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((pad - l, pad - t), word, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
    if shear:                                         # synthetic italic (Apple Garamond here has no italic face)
        extra = int(abs(shear) * h)
        im2 = Image.new("L", (w + extra, h), 0)
        im2.paste(im, (0, 0))
        im = im2.transform(im2.size, Image.AFFINE, (1, shear, -shear * h if shear > 0 else 0, 0, 1, 0), Image.BICUBIC)
    return np.asarray(im, np.float32) / 255.0


def sprite_fade(word, size):
    """TX1: Helvetica Neue, white, vertical opacity gradient (Shading > Gradient: black -> opacity, low fade)."""
    a = glyph_alpha(word, ImageFont.truetype(HN, size, index=0))
    h = a.shape[0]
    g = np.linspace(1.0, 0.22, h, dtype=np.float32)[:, None]     # opaque top, mostly gone at the bottom
    a = a * g
    return np.dstack([a, a, a, a])                               # white, premultiplied


def sprite_premium(word, size, color):
    """TX2: Apple Garamond bold italic, Gaussian 0.1, Create Bump Map on red (float32), colour, Merge 'In'."""
    a = glyph_alpha(word, fx.font(GARAMOND, SERIF_FALLBACK, size), stroke=max(2, size // 40), shear=0.22)
    soft = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(size / 26)), np.float32) / 255
    gy, gx = np.gradient(soft * size / 10)                       # height field -> normals
    nz = 1.0 / np.sqrt(gx ** 2 + gy ** 2 + 1)
    light = np.array([-0.55, -0.65, 0.52])                       # from the top left
    light /= np.linalg.norm(light)
    shade = np.clip((-gx * light[0] - gy * light[1] + light[2]) * nz, 0, 1)
    spec = shade ** 18 * 0.8
    base = np.array(color, np.float32)
    rgb = np.clip(base * (0.35 + 0.9 * shade)[..., None] + spec[..., None], 0, 1)
    a = np.clip(a, 0, 1)
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255
    return np.dstack([rgb * a[..., None], a])


def sprite_gradglow(word, size, top=(1.0, 0.55, 0.20), bottom=(0.78, 0.25, 1.0)):
    """TX5: Helvetica bold, Shading > Gradient orange to purple (mapping angle -90, linear), soft glow behind."""
    a = glyph_alpha(word, ImageFont.truetype(HN, size, index=1), pad=size // 2)
    h = a.shape[0]
    rows = np.nonzero(a.max(1) > 0.05)[0]
    y0, y1 = (rows.min(), rows.max()) if len(rows) else (0, h - 1)
    g = np.clip((np.arange(h, dtype=np.float32) - y0) / max(y1 - y0, 1), 0, 1)[:, None, None]   # gradient over the letters
    rgb = np.array(top, np.float32) * (1 - g) + np.array(bottom, np.float32) * g
    rgb = np.broadcast_to(rgb, (h, a.shape[1], 3))
    glow_a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(size / 7)), np.float32) / 255
    glow_a = np.clip(glow_a * 0.85, 0, 1)
    out_a = a + glow_a * (1 - a)
    out_rgb = rgb * a[..., None] + rgb * glow_a[..., None] * (1 - a[..., None])
    return np.dstack([out_rgb, out_a])


def sprite_glitch(word, size):
    """TX3: heavy italic sans with a chrome fill (white top, hard dark band under the middle, light bottom)."""
    a = glyph_alpha(word, ImageFont.truetype(HN, size, index=3))
    h = a.shape[0]
    y = np.linspace(0, 1, h, dtype=np.float32)
    lum = np.interp(y, [0, 0.42, 0.50, 0.56, 0.75, 1.0], [1.0, 0.96, 0.18, 0.35, 0.80, 0.95])
    tint = np.dstack([lum, lum, np.clip(lum * 1.04, 0, 1)])[:, :1, :]
    rgb = np.broadcast_to(tint, (h, a.shape[1], 3))
    return np.dstack([rgb * a[..., None], a])


# ------------------------------------------------------------------ layout + animation
def stack(sprites, size, lead, xoffs):
    """Positions (x, y top-left, in canvas px around a 0,0 centre) for a tight vertical stack of word sprites."""
    pos, y = [], 0.0
    for i, s in enumerate(sprites):
        h, w = s.shape[:2]
        pos.append([-w / 2 + xoffs[i % len(xoffs)] * size, y - h / 2])
        y += size * lead
    total = y - size * lead
    return [(x, yy - total / 2) for x, yy in pos]


def blit(canvas, spr, x, y, alpha=1.0):
    H, W = canvas.shape[:2]
    h, w = spr.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    s = spr[y0 - y:y1 - y, x0 - x:x1 - x] * alpha
    c = canvas[y0:y1, x0:x1]
    canvas[y0:y1, x0:x1] = s + c * (1 - s[..., 3:4])


def glitch_opacity(f24):
    """Opacity keys (24 fps frames): 0 at f0, up f2, a little down f4, up f6, down f7, up f8, down f10, up f11-12."""
    keys = [(0, 0.0), (2, 1.0), (4, 0.65), (6, 1.0), (7, 0.2), (8, 1.0), (10, 0.25), (11, 1.0), (12, 1.0)]
    for (a, va), (b, vb) in zip(keys, keys[1:]):
        if a <= f24 <= b:
            return va if f24 < b else vb                        # stepped: Resolve keys on whole frames
    return 1.0 if f24 > 12 else 0.0


def render(kind, text, W, H, fps, dur, y_c=0.5, size=None, color2=(1.0, 0.36, 0.22)):
    words = [w for w in (text.split("|") if "|" in text else text.split())]
    if kind == "fade":
        size = size or 175
        spr = [sprite_fade(w, size) for w in words]
        pos = stack(spr, size, 0.60, [-0.10, 0.12, -0.05, 0.10])
        stagger, travel, ramp, fade_in = 5, 0.15, 20, 6         # frames at 24 fps
    elif kind == "premium":
        size = size or 170
        spr = [sprite_premium(w, size, (0.72, 0.72, 0.74) if i == 0 else color2) for i, w in enumerate(words)]
        pos = stack(spr, size, 0.62, [-0.10, 0.25])
        stagger, travel, ramp, fade_in = 7, 0.03, 14, 8
    elif kind == "gradglow":
        size = size or 120
        spr = [sprite_gradglow(w, size) for w in words]
        pos = stack(spr, size, 0.9, [0.0])
        stagger, travel, ramp, fade_in = 6, 0.15, dur * SRC_FPS, 0      # Y 0.35 -> 0.5 over the whole clip, out cubic
    else:
        size = size or 150
        spr = [sprite_glitch(w, size) for w in words]
        pos = stack(spr, size, 0.55, [0.0, 0.05, 0.12])
        stagger, travel, ramp, fade_in = 9, 0.15, 35, 0
    n = round(dur * fps)
    frames = []
    for i in range(n):
        canvas = np.zeros((H, W, 4), np.float32)
        t24 = i * SRC_FPS / fps
        for k, (s, (x, y)) in enumerate(zip(spr, pos)):
            local = t24 - k * stagger
            if local < 0:
                continue
            sub = 6 if kind == "glitch" else 1                    # motion blur on the glitch move (reference setting)
            layer = np.zeros_like(canvas)
            for j in range(sub):
                lt = local - j * 0.5 / sub
                p = out_cubic(lt / ramp)
                dy = (1 - p) * travel * H
                blit(layer, s, W / 2 + x, H * y_c + y + dy, 1.0 / sub)
            if kind == "glitch":
                op = glitch_opacity(local)
            else:
                op = float(np.clip(local / fade_in, 0, 1)) if fade_in else 1.0
            canvas = layer * op + canvas * (1 - layer[..., 3:4] * op)
        frames.append(canvas)
    return frames


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["fade", "premium", "glitch", "gradglow"])
    ap.add_argument("text")
    ap.add_argument("--bg", required=True, help="video or image under the text")
    ap.add_argument("--at", type=float, default=0.0, help="start second in --bg")
    ap.add_argument("--dur", type=float, default=2.5)
    ap.add_argument("--y", type=float, default=0.5)
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("--alpha", help="also write the text alone as ProRes 4444 with alpha")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    if Path(a.bg).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        im = Image.open(a.bg).convert("RGB")
        s = max(a.w / im.width, a.h / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        l, t = (im.width - a.w) // 2, (im.height - a.h) // 2
        bg = np.asarray(im.crop((l, t, l + a.w, t + a.h)), np.float32) / 255
        bgs = [bg] * n
    else:
        bgs = fx.read_frames(a.bg, a.at, n, a.w, a.h, a.fps)
    txt = render(a.kind, a.text, a.w, a.h, a.fps, a.dur, a.y, a.size)
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for b, t in zip(bgs, txt):
        wr.write(t[..., :3] + b * (1 - t[..., 3:4]))
    wr.close()
    if a.alpha:
        p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{a.w}x{a.h}",
                              "-r", str(a.fps), "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt",
                              "yuva444p10le", a.alpha], stdin=subprocess.PIPE)
        for t in txt:
            un = np.where(t[..., 3:4] > 1e-4, t[..., :3] / np.maximum(t[..., 3:4], 1e-4), 0)
            p.stdin.write((np.clip(np.dstack([un, t[..., 3]]), 0, 1) * 255).astype(np.uint8).tobytes())
        p.stdin.close()
        p.wait()
    print(f"{a.kind}: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
