---
name: vfx-for-claude-code
description: A library of 40 video effects as Python code (transitions like light leak glow, roto step-in, blur blink, punch-in flash; titles like glitch flicker, fade-up, word drop, bounce captions; looks like film grade, box flash, text behind subject, chromatic aberration, light rays). Use when the user asks to add an effect, transition, title animation, caption style or look to a video clip, names an effect ID like T01, TX03 or FX15, or asks which effects are available.
---

# VFX for Claude Code

## Find the library

The library root is the folder two levels above this SKILL.md after resolving links:
`LIB="$(cd "$(dirname "$(realpath <path of this SKILL.md>)")/../.." && pwd)"`. `install.sh` also writes it to `LIBRARY_PATH` next to this file.
Run every command from `$LIB` (the commands in the catalog use paths relative to it).

## Use an effect

1. Find it from the user's words: `python3 find.py <words>` (searches IDs, names, other names, look, use, mood). `python3 find.py --all` lists all 40.
   If several fit, name the 2 or 3 closest with one line each and pick the best one, or ask if the choice really matters.
   If nothing fits, say so. Do not invent an effect that is not in the catalog.
2. Read the effect file's top notes and `--help` for its options (`python3 effects/<file>.py --help`).
3. Get the inputs: clip paths, and the time in seconds where it should happen (`--at`, or `--cut` and `--b-in` for transitions). Check the clip length with `ffprobe` first.
4. Render a short preview (2 to 3 s around the moment) to a new file name, open it (`open <file>`), and tell the user what to look for. Render the full version after the user is happy.
5. Defaults are 1080x1920 at 30 fps. For landscape pass `--w 1920 --h 1080`; match `--fps` to the user's project.
6. Tell the user the output path and how to place it in their edit (it replaces the picture of that stretch, the original audio stays; a `--alpha` title goes on a track above).

## Notes

- Requires macOS, Python 3 with numpy and Pillow, and ffmpeg. Effects that cut out a person (T02, T06, FX01, FX03, FX07) build `lib/segment.swift` with `swiftc` on first use, which needs the Xcode Command Line Tools.
- Renders are CPU-only and take about 0.1 to 1 s per frame. Keep previews short.
- Fonts are macOS system fonts (Helvetica Neue, SF Pro, Avenir Next). TX02 prefers Apple Garamond and falls back to Baskerville.
- Outputs are video only, with no audio. Keep the original audio track under the rendered stretch in the user's editor, or mux it back with ffmpeg if they want one file.

## Add an effect

Follow "Add your own effect" in the library README: the code in `effects/`, a `catalog.json` entry with 6 to 10 other names, a GIF in `docs/gifs/`, then `python3 make_gallery.py`.
