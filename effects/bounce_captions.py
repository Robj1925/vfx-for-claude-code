#!/usr/bin/env python3
"""TX04 Bounce captions: one or two words per card, white heavy caps, each card pops in with an elastic size bounce.
Rebuilt from a reference edit, checked every frame. Build: Text+ size > Modify with > Anim Curves, easing Elastic, then
Snap Captions copies it onto Resolve's auto subtitles (4 to 8 characters per line).

Measured scale per frame of a new card (24 fps): f0 0.80, f1 1.06, f2 1.00 (an elastic overshoot that settles by f2).

  python3 effects/bounce_captions.py --bg clip.mov --at 2 --text "this is how captions should look" -o out.mp4
  python3 effects/bounce_captions.py --bg clip.mov --at 2 --words words.json -o out.mp4   # [{"w":"yeah","t":0.0}, ...] times in s
"""
import argparse, json, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fx  # noqa: E402

FONT = ("/System/Library/Fonts/Avenir Next.ttc", 8)       # Avenir Next Heavy: close to the reference wide heavy caps
SCALE_24 = [0.80, 1.06, 1.00]                             # per 24 fps frame from the card start


def cards_from_text(text, per=0.27, max_chars=8):
    words, cards, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            cards.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        cards.append(cur)
    return [{"w": c, "t": i * per} for i, c in enumerate(cards)]


def sprite(word, size):
    f = ImageFont.truetype(FONT[0], size, index=FONT[1])
    word = word.upper()
    l, t, r, b = f.getbbox(word)
    pad = 30
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", im.size, 0)
    ImageDraw.Draw(sh).text((pad - l + 3, pad - t + 4), word, font=f, fill=150)
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    im.paste((0, 0, 0, 255), (0, 0), sh)
    ImageDraw.Draw(im).text((pad - l, pad - t), word, font=f, fill=(255, 255, 255, 255))
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bg", required=True), ap.add_argument("--at", type=float, default=0.0)
    ap.add_argument("--text"), ap.add_argument("--words")
    ap.add_argument("--y", type=float, default=0.55), ap.add_argument("--size", type=int, default=82)
    ap.add_argument("--fps", type=int, default=30), ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    cards = json.loads(Path(a.words).read_text()) if a.words else cards_from_text(a.text)
    dur = cards[-1]["t"] + 0.6
    n = round(dur * a.fps)
    bgs = fx.read_frames(a.bg, a.at, n, a.w, a.h, a.fps)
    sprites = [sprite(c["w"], a.size) for c in cards]
    wr = fx.Writer(a.out, a.w, a.h, a.fps)
    for i in range(n):
        t = i / a.fps
        k = max([j for j, c in enumerate(cards) if c["t"] <= t], default=None)
        img = Image.fromarray((bgs[i] * 255).astype(np.uint8)).convert("RGBA")
        if k is not None:
            f24 = (t - cards[k]["t"]) * 23.976
            s = SCALE_24[min(int(f24), len(SCALE_24) - 1)] if f24 < len(SCALE_24) else 1.0
            sp = sprites[k]
            sp2 = sp.resize((max(1, round(sp.width * s)), max(1, round(sp.height * s))), Image.BICUBIC)
            img.alpha_composite(sp2, (round(a.w / 2 - sp2.width / 2), round(a.h * a.y - sp2.height / 2)))
        wr.write(np.asarray(img.convert("RGB"), np.float32) / 255)
    wr.close()
    print(f"bounce captions: {len(cards)} cards, {n} frames -> {a.out}")


if __name__ == "__main__":
    main()
