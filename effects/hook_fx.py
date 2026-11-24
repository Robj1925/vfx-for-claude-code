#!/usr/bin/env python3
"""Hook and word effects rebuilt from reference edits (seven modes).
The references play only in a small viewer, so the numbers below are the stated settings, not frame measurements.

  hookzoom   FX06  Hook zoom-out: adjustment clip over the hook, Transform size 2.5 on frame 0 -> 1.0 on frame 60,
                     ease out cubic with the handles pulled (very fast start, long soft landing). A common hook opener.
  behind     FX07  Text behind the subject: the clip, the title, then the person cut out on top (Magic Mask, mode Better),
                     so the title sits behind the subject. Ours: Apple Vision person matte on every frame.
  wordslide  TX06  Word slide-up title: SF Pro Display, Follower per word, offset Y -0.2 -> 0 over 25 frames, out cubic,
                     delay 0.46 between words, opacity 0 -> 1 over the first 7 frames.

  hookzoomlens  FX06 variant: hookzoom plus a barrel lens bulge (Lens Distortion 0.24 to 0 over 8 frames).
  blurslide     TX11  Blur up slide: each word rises out of focus and sharpens as it fades in.
  continuous    TX12  Continuous slide through: a word whips in, drifts through the middle, eases off right.
  continuousblur TX12 variant: the same, entering from the right with motion blur.

  python3 effects/hook_fx.py hookzoom  clip.mov --at 0 --dur 3 -o out.mp4
  python3 effects/hook_fx.py blurslide clip.mov --at 0 --dur 2.4 --text "Your words" -o out.mp4
  python3 effects/hook_fx.py continuous clip.mov --at 0 --dur 2.4 --text "Continuous" -o out.mp4
  python3 effects/hook_fx.py behind    clip.mov --at 0 --dur 3 --text "Big|Title" -o out.mp4 [--y 0.42] [--size 150]   (needs a shot with space around the person)
  python3 effects/hook_fx.py wordslide clip.mov --at 0 --dur 3 --text "Your words here" -o out.mp4 [--y 0.5]
"""
import argparse, subprocess, sys, tempfile, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

SF = "/System/Library/Fonts/SFNS.ttf"
HN = "/System/Library/Fonts/HelveticaNeue.ttc"
F24 = 23.976


def out_cubic_pulled(t):
    t = np.clip(t, 0, 1)
    return 1 - (1 - t) ** 4.5


def zoom(img, s):
    h, w = img.shape[:2]
    if abs(s - 1) < 1e-4:
        return img
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    sw, sh = round(w * s), round(h * s)
    big = im.resize((sw, sh), Image.BICUBIC)
    x0, y0 = (sw - w) // 2, (sh - h) // 2
    return np.asarray(big.crop((x0, y0, x0 + w, y0 + h)), np.float32) / 255


def hook_curve(f24, n24=60, k=0.45):
    """Measured on a reference edit (every unique frame): about 60 % of the zoom is gone after 2 frames,
    80 % after 4, 90 % after 6, then a long soft tail to frame 60 (handle pulled straight down)."""
    rem = np.exp(-k * f24) * (1 - np.clip(f24 / n24, 0, 1) ** 2)
    return 1 - rem


def hookzoom(frames, fps, start=2.5, n24=60, lens=0.0, lens24=8):
    n = round(n24 * fps / F24)
    out = []
    for i, f in enumerate(frames):
        if lens:                                          # Lens Distortion 0.24 -> 0 by about frame 8, S keys
            t = min(i * F24 / fps / lens24, 1.0)
            k = lens * (1 - t * t * (3 - 2 * t))
            if k > 1e-3:
                f = fx.lens_distort(f, k, scale=1 + k * 0.5)
        p = float(hook_curve(i * F24 / fps, n24))
        s = start + (1 - start) * p
        if i < n:                                        # motion blur on the fast first frames
            s2 = start + (1 - start) * float(hook_curve((i - 0.5) * F24 / fps, n24))
            f = (zoom(f, s) + zoom(f, (s + s2) / 2) + zoom(f, s2)) / 3 if i else zoom(f, s)
        out.append(f)
    return out


def mattes(frames):
    seg = fx.segment_bin()
    H, W = frames[0].shape[:2]
    sw, sh = 540, 960
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "s.mp4"
        p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{sw}x{sh}", "-r", "30",
                              "-i", "-", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(clip)], stdin=subprocess.PIPE)
        for f in frames:
            p.stdin.write(np.asarray(Image.fromarray((f * 255).astype(np.uint8)).resize((sw, sh)), np.uint8).tobytes())
        p.stdin.close()
        p.wait()
        raw = subprocess.run([str(seg), str(clip), "accurate"], capture_output=True).stdout
    m = np.frombuffer(raw, np.uint8)[: (len(raw) // (sw * sh)) * sw * sh].reshape(-1, sh, sw)
    return [np.asarray(Image.fromarray(m[min(i, len(m) - 1)]).resize((W, H), Image.BILINEAR), np.float32)[..., None] / 255
            for i in range(len(frames))]


def title_layer(text, W, H, y, size, font=(HN, 1), color=(255, 255, 255)):
    f = ImageFont.truetype(font[0], size, index=font[1])
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    d.text(((W - (r - l)) / 2 - l, H * y - (b - t) / 2 - t), text, font=f, fill=color + (255,))
    a = np.asarray(im, np.float32) / 255
    return a[..., :3] * a[..., 3:4], a[..., 3:4]


def behind(frames, text, y, size, front=""):
    """Measured on a reference edit (every unique frame): the behind text is bold italic white, two lines,
    mid frame; a separate small title sits on top in front of the subject ("Watch This:" with the last word in lime)."""
    H, W = frames[0].shape[:2]
    lines = text.split("|")
    rgb = np.zeros((H, W, 3), np.float32); al = np.zeros((H, W, 1), np.float32)
    for k, line in enumerate(lines):
        r_, a_ = title_layer(line, W, H, y + (k - (len(lines) - 1) / 2) * size * 0.95 / H, size, font=(HN, 3))
        rgb = r_ + rgb * (1 - a_); al = a_ + al * (1 - a_)
    frt = None
    if front:
        words = front.split()
        f = ImageFont.truetype(HN, int(size * 0.55), index=1)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        tw = f.getlength(front); x = (W - tw) / 2
        for j, w in enumerate(words):
            d.text((x, H * 0.10), w, font=f, fill=(198, 244, 50, 255) if j == len(words) - 1 else (255, 255, 255, 255))
            x += f.getlength(w + " ")
        frt = np.asarray(im, np.float32) / 255
    out = []
    for f, m in zip(frames, mattes(frames)):
        img = rgb + f * (1 - al)                          # title over the plate
        img = f * m + img * (1 - m)                       # person back on top
        if frt is not None:
            img = frt[..., :3] * frt[..., 3:4] + img * (1 - frt[..., 3:4])
        out.append(img)
    return out


def wordslide(frames, fps, text, y, size=120, n24=25, delay=0.46, fade24=7, offset=0.2, blur24=0, blur_px=0.0):
    H, W = frames[0].shape[:2]
    f = ImageFont.truetype(SF, size)
    words = text.split()
    space = f.getlength(" ")
    widths = [f.getlength(w) for w in words]
    total = sum(widths) + space * (len(words) - 1)
    x = (W - total) / 2
    sprites = []
    for w, wd in zip(words, widths):
        im = Image.new("RGBA", (int(wd) + 20, int(size * 1.4)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10, int(size * 0.1)), w, font=f, fill=(255, 255, 255, 255))
        sprites.append((im, x - 10))
        x += wd + space
    out = []
    for i, fr in enumerate(frames):
        img = Image.fromarray((fr * 255).astype(np.uint8)).convert("RGBA")
        t24 = i * F24 / fps
        for k, (sp, sx) in enumerate(sprites):
            local = t24 - k * delay * n24                  # Follower delay: a share of the animation per word
            if local <= 0:
                continue
            # measured on a reference edit (every unique frame): 45 % of the move done after
            # 2 frames, 70 % after 4, 83 % after 6, 95 % after 10, settled by 25
            p = 1 - float(np.exp(-0.29 * local) * (1 - min(local / n24, 1.0) ** 2))
            op = min(local / fade24, 1.0)
            dy = (1 - p) * offset * H
            s = sp.copy()
            if blur24:                                     # TX11: Gaussian blur keyed down over 8 frames, keeps 0.1
                bl = blur_px * (1 - min(local / blur24, 1.0)) + blur_px * 0.06
                s = s.filter(ImageFilter.GaussianBlur(bl))
            s.putalpha(s.getchannel("A").point(lambda v: int(v * op)))
            img.alpha_composite(s, (round(sx), round(H * y - size * 0.7 + dy)))
        out.append(np.asarray(img.convert("RGB"), np.float32) / 255)
    return out


def continuous(frames, fps, text, y, size=110, n_in24=25, n_out24=50, from_right=False, blur=0.0):
    """TX12: Transform X from off the left edge to the centre by frame 25, then on to off the right edge by frame 50;
    spline: comes in really fast, a little breaking point in the middle, then eases away (never fully stops)."""
    H, W = frames[0].shape[:2]
    f = ImageFont.truetype(SF, size)
    tw = f.getlength(text)
    sp = Image.new("RGBA", (int(tw) + 40, int(size * 1.4)), (0, 0, 0, 0))
    ImageDraw.Draw(sp).text((20, int(size * 0.1)), text, font=f, fill=(255, 255, 255, 255))
    x_left, x_mid, x_right = -sp.width, W / 2 - sp.width / 2, W
    out = []
    for i, fr in enumerate(frames):
        t24 = i * F24 / fps
        stop = x_left + (x_mid - x_left) * 0.92
        if t24 <= n_in24:
            p = 1 - (1 - t24 / n_in24) ** 3                  # fast in, slows into the middle
            x = x_left + (stop - x_left) * p
        else:
            q = min((t24 - n_in24) / (n_out24 - n_in24), 1.0)
            if q < 0.35:                                     # the "breaking point": a slow drift through the centre
                x = stop + (x_mid - stop) * (q / 0.35)
            else:                                            # then it eases away off the right edge
                x = x_mid + (x_right - x_mid) * ((q - 0.35) / 0.65) ** 2.4
        if from_right:                                       # variant: enters from the right, exits left
            x = W - sp.width - x
        spx = sp
        if blur:                                             # blur keyed: strong on entry and exit, sharp through the middle
            if t24 <= n_in24:
                b = blur * (1 - t24 / n_in24) ** 1.5
            else:
                q = min((t24 - n_in24) / (n_out24 - n_in24), 1.0)
                b = blur * max(0.0, (q - 0.35) / 0.65) ** 1.5
            if b > 0.3:
                spx = sp.filter(ImageFilter.GaussianBlur(b))
        img = Image.fromarray((fr * 255).astype(np.uint8)).convert("RGBA")
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.paste(spx, (round(x), round(H * y - size * 0.7)))
        img.alpha_composite(layer)
        out.append(np.asarray(img.convert("RGB"), np.float32) / 255)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["hookzoom", "hookzoomlens", "behind", "wordslide", "blurslide", "continuous", "continuousblur"]), ap.add_argument("clip")
    ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--dur", type=float, default=3.0)
    ap.add_argument("--text", default=""), ap.add_argument("--front", default=""), ap.add_argument("--y", type=float, default=0.3), ap.add_argument("--size", type=int, default=150)
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    n = round(a.dur * a.fps)
    frames = fx.read_frames(a.clip, a.at, n, a.w, a.h, a.fps)
    if a.kind == "hookzoom":
        out = hookzoom(frames, a.fps)
    elif a.kind == "hookzoomlens":
        out = hookzoom(frames, a.fps, lens=0.24)
    elif a.kind == "behind":
        out = behind(frames, a.text, a.y, a.size, a.front)
    elif a.kind == "wordslide":
        out = wordslide(frames, a.fps, a.text, a.y, min(a.size, 120))
    elif a.kind == "blurslide":                             # TX11: offset -0.2, delay 0.45, opacity to frame ~12
        out = wordslide(frames, a.fps, a.text, a.y, min(a.size, 120), n24=22, delay=0.45, fade24=12, offset=0.03,
                        blur24=8, blur_px=14.0)
    elif a.kind == "continuousblur":                       # TX12 variant: from the right, blur 28 on entry and exit
        out = continuous(frames, a.fps, a.text, a.y, min(a.size, 120), n_in24=20, n_out24=65, from_right=True, blur=28.3)
    else:
        out = continuous(frames, a.fps, a.text, a.y, min(a.size, 120))
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for f in out:
        wr.write(f)
    wr.close()
    print(f"{a.kind}: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
