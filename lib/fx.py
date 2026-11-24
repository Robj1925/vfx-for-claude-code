"""Shared helpers for vfx-for-claude-code: frame I/O through ffmpeg pipes, easing, masks.

Every template works on frames as float32 RGB arrays in 0..1, at the output size and fps.
"""
import json, subprocess, numpy as np
from pathlib import Path

W, H, FPS = 1080, 1920, 30


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    n, m = s["r_frame_rate"].split("/")
    return {"w": s["width"], "h": s["height"], "fps": float(n) / float(m), "dur": float(d["format"]["duration"])}


def read_frames(path, start, count, w=W, h=H, fps=FPS):
    """`count` frames from `start` seconds, scaled and centre-cropped to w x h (cover)."""
    vf = f"fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.4f}", "-i", str(path), "-frames:v", str(count),
                          "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32) / 255.0
    if len(f) == 0:
        raise SystemExit(f"{path}: no frames at {start:.2f} s (the clip is {probe(path)['dur']:.2f} s long)")
    if len(f) < count:                                   # hold the last frame if the clip runs short
        f = np.concatenate([f, np.repeat(f[-1:], count - len(f), 0)])
    return f


class Writer:
    def __init__(self, out, w=W, h=H, fps=FPS, audio=None, audio_start=0.0):
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
        if audio:
            cmd += ["-ss", f"{audio_start:.4f}", "-i", str(audio), "-map", "0:v", "-map", "1:a", "-shortest", "-c:a", "aac", "-b:a", "256k"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p", str(out)]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, frame):
        self.p.stdin.write((np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())

    def close(self):
        self.p.stdin.close()
        self.p.wait()


# ---------------------------------------------------------------- easing
def smooth(t):
    """Resolve spline 'S' (smooth) between two keys: smoothstep."""
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def key_curve(n, keys):
    """Value per frame 0..n-1 from keyframes [(frame, value), ...], smoothed like Resolve's S key."""
    keys = sorted(keys)
    out = np.zeros(n, np.float32)
    for i in range(n):
        if i <= keys[0][0]:
            out[i] = keys[0][1]
        elif i >= keys[-1][0]:
            out[i] = keys[-1][1]
        else:
            for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
                if f0 <= i <= f1:
                    out[i] = v0 + (v1 - v0) * smooth((i - f0) / max(f1 - f0, 1e-6))
                    break
    return out


# ---------------------------------------------------------------- shapes
def ellipse_mask(w, h, cx=0.5, cy=0.5, rx=0.55, ry=0.45, soft=0.35):
    """1 inside the ellipse, 0 outside, with a soft edge (fraction of the radius)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((x / w - cx) / rx) ** 2 + ((y / h - cy) / ry) ** 2)
    return np.clip((1 + soft - d) / (2 * soft), 0, 1)


def zoom_blur(img, amount, samples=16, cx=0.5, cy=0.5):
    """Radial (zoom) blur like Resolve's Radial Blur: average of copies scaled up to 1 + amount about the centre."""
    if amount <= 1e-4:
        return img
    from PIL import Image
    h, w = img.shape[:2]
    src = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    acc = np.zeros_like(img)
    for k in range(samples):
        s = 1 + amount * k / (samples - 1)
        sw, sh = round(w * s), round(h * s)
        big = src.resize((sw, sh), Image.BILINEAR)
        x0, y0 = round((sw - w) * cx), round((sh - h) * cy)
        acc += np.asarray(big.crop((x0, y0, x0 + w, y0 + h)), np.float32) / 255.0
    return acc / samples


def segment_bin():
    """Path of the Apple Vision person segmenter. Built once from lib/segment.swift with swiftc (Xcode Command Line Tools)."""
    here = Path(__file__).resolve().parent
    out = here / ".bin" / "segment"
    src = here / "segment.swift"
    if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        out.parent.mkdir(exist_ok=True)
        subprocess.run(["swiftc", "-O", "-suppress-warnings", str(src), "-o", str(out)], check=True)
    return out


def font(path, fallbacks=(), size=64, index=0):
    """PIL font from `path`, or the first fallback that exists (list of (path, index))."""
    from PIL import ImageFont
    for p, i in [(path, index)] + list(fallbacks):
        if Path(p).exists():
            return ImageFont.truetype(str(p), size, index=i)
    return ImageFont.load_default(size)


def person_matte(frame_rgb):
    """Person matte (0..1, h x w) of one frame with Apple Vision (lib/segment.swift)."""
    import tempfile
    seg = segment_bin()
    h, w = frame_rgb.shape[:2]
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "f.mp4"
        p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                              "-r", "30", "-i", "-", "-frames:v", "2", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
                              str(clip)], stdin=subprocess.PIPE)
        b = (np.clip(frame_rgb, 0, 1) * 255).astype(np.uint8).tobytes()
        p.stdin.write(b + b)
        p.stdin.close()
        p.wait()
        raw = subprocess.run([str(seg), str(clip), "accurate"], capture_output=True).stdout
    m = np.frombuffer(raw, np.uint8)
    n = len(m) // (w * h)
    if n:
        return m[: w * h].reshape(h, w).astype(np.float32) / 255.0
    raise RuntimeError("segmenter returned no matte")


def remap(img, sx, sy):
    """Bilinear sample img (h, w, c) at float coords sx, sy (h, w); edges clamped."""
    h, w = img.shape[:2]
    sx = np.clip(sx, 0, w - 1.001); sy = np.clip(sy, 0, h - 1.001)
    x0 = sx.astype(np.int32); y0 = sy.astype(np.int32)
    fx_ = (sx - x0)[..., None]; fy_ = (sy - y0)[..., None]
    a = img[y0, x0]; b = img[y0, x0 + 1]; c = img[y0 + 1, x0]; d = img[y0 + 1, x0 + 1]
    return (a * (1 - fx_) + b * fx_) * (1 - fy_) + (c * (1 - fx_) + d * fx_) * fy_


def lens_distort(img, k, scale=1.0):
    """Resolve-style Lens Distortion: k > 0 barrel (bulges out), sampled from the centre; scale > 1 crops in."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (xx - w / 2) / (w / 2), (yy - h / 2) / (w / 2)
    r2 = nx * nx + ny * ny
    f = (1 - k * r2 * 0.5) / scale
    return remap(img, w / 2 + nx * f * (w / 2), h / 2 + ny * f * (w / 2))


def chromatic(img, amount=0.006):
    """Split-channel lens distortion: red scaled out, blue scaled in, so edges get red/cyan fringes toward the corners."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    out = np.empty_like(img)
    for ch, s in ((0, 1 + amount), (1, 1.0), (2, 1 - amount)):
        sx = w / 2 + (xx - w / 2) / s; sy = h / 2 + (yy - h / 2) / s
        out[..., ch] = remap(img[..., ch:ch + 1], sx, sy)[..., 0]
    return out
