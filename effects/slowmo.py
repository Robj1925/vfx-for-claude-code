#!/usr/bin/env python3
"""FX04 Super slow motion b-roll (optical flow). The equivalent in Resolve:
Retime and Scaling, Retime Process = Optical Flow, Motion Estimation = Speed Warp (AI) or Enhanced Better.
Typical use: slow 24 fps b-roll to about 300 fps worth of frames and talk over it so the viewer has time to read the shot.
Ours: ffmpeg minterpolate (motion-compensated, overlapped blocks) builds the in-between frames.

  python3 effects/slowmo.py clip.mov --at 2 --src-dur 0.33 --factor 12 -o out.mp4      # 0.33 s of source -> 4 s of smooth slow motion
"""
import argparse, subprocess

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("clip"), ap.add_argument("--at", type=float, default=0.0), ap.add_argument("--src-dur", type=float, default=1.0)
ap.add_argument("--factor", type=float, default=12.0), ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--w", type=int, default=1080), ap.add_argument("--h", type=int, default=1920), ap.add_argument("-o", "--out", required=True)
a = ap.parse_args()
vf = (f"scale={a.w}:{a.h}:force_original_aspect_ratio=increase,crop={a.w}:{a.h},setpts={a.factor}*PTS,"
      f"minterpolate=fps={a.fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a.at}", "-t", f"{a.src_dur}", "-i", a.clip, "-an", "-vf", vf,
                "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", a.out], check=True)
n = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", a.out], capture_output=True, text=True).stdout.strip() or 0)
print(f"slow motion x{a.factor}: {n} frames ({n / a.fps:.2f} s) -> {a.out}")
