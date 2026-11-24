#!/usr/bin/env python3
"""FX12 3D parallax collage pan.
Build (Resolve Fusion): every collage asset (paper background, city drawing, a cut-out figure, cross, clouds, poster) on its own ImagePlane3D,
pushed to different depths; Camera3D (focal length about 84) starts at the left edge of the background and trucks right, S keys;
text planes sit in front, so they slide past fastest. Frame check of a reference edit, 2.8 s to 6 s at 8 fps: the camera trucks right,
the near figure and cross slide out of frame faster than the paper behind them, two near text planes slide in from the right
one after the other and settle, clouds pass in front.

  python3 effects/parallax_collage.py --layers layers.json --dur 3 -o out.mp4
layers.json: [{"img": "paper.jpg", "z": 10}, {"img": "person.png", "z": 4, "x": 0.3, "y": 0.55, "h": 0.6},
              {"text": "Big Title", "z": 2.5, "x": 1.3, "y": 0.35, "size": 120}]
x, y = position on the background (0..1 of the frame at z 1), h = height as a fraction of the frame. Far = big z.
"""
import argparse, json, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

HN = "/System/Library/Fonts/HelveticaNeue.ttc"
F24 = 23.976


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def load(layer, W, H):
    if "text" in layer:
        f = ImageFont.truetype(HN, int(layer.get("size", 120) * 2), index=1)
        l, t, r, b = f.getbbox(layer["text"])
        im = Image.new("RGBA", (r - l + 40, b - t + 40), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((20 - l, 20 - t), layer["text"], font=f, fill=tuple(layer.get("color", (40, 40, 40))) + (255,))
        return im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
    im = Image.open(Path(layer["img"]) if Path(layer["img"]).is_absolute() else LAYERS_DIR / layer["img"]).convert("RGBA")
    if "h" in layer:
        s = layer["h"] * H / im.height
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    return im


LAYERS_DIR = Path(".")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--layers", required=True), ap.add_argument("--dur", type=float, default=3.0)
    ap.add_argument("--truck", type=float, default=0.9, help="camera move to the right, in frame widths at z 1")
    ap.add_argument("--push", type=float, default=0.6, help="camera move forward (z units)")
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    W, H = a.w, a.h
    global LAYERS_DIR
    LAYERS_DIR = Path(a.layers).resolve().parent              # image paths are relative to the JSON file
    layers = json.loads(Path(a.layers).read_text())
    sprites = [load(l, W, H) for l in layers]
    n = round(a.dur * a.fps)
    zref = max(l["z"] for l in layers)
    wr = fx.Writer(a.out, W, H, a.fps)
    for i in range(n):
        p = float(smooth(i / max(n - 1, 1)))
        camx, camz = a.truck * W * p, a.push * p
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        for lay, sp in sorted(zip(layers, sprites), key=lambda q: -q[0]["z"]):
            d = lay["z"] - camz
            s = lay["z"] / d                                   # each plane is sized for its own depth at rest
            if "img" in lay and "x" not in lay:              # background: fill the frame plus the truck travel
                k = max((W + a.truck * W * (1 / lay["z"]) * zref) / sp.width, H / sp.height) * s
                im = sp.resize((round(sp.width * k), round(sp.height * k)), Image.BICUBIC)
                off = camx / d
                canvas.alpha_composite(im, (round(-off), round((H - im.height) / 2)))
                continue
            im = sp.resize((max(1, round(sp.width * s)), max(1, round(sp.height * s))), Image.BICUBIC)
            cx = lay.get("x", 0.5) * W * s - camx / d * (zref / lay["z"]) * 0 - camx * (1 / d)
            cx = W / 2 + (lay.get("x", 0.5) * W - W / 2) * s - camx / d
            cy = H / 2 + (lay.get("y", 0.5) * H - H / 2) * s
            canvas.alpha_composite(im, (round(cx - im.width / 2), round(cy - im.height / 2))) if -im.width < cx < W + im.width else None
        wr.write(np.asarray(canvas.convert("RGB"), np.float32) / 255)
    wr.close()
    print(f"parallax collage: {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
