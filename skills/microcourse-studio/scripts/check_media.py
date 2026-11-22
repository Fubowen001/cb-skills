"""Read video headers and fully decode the export. Needs ffmpeg on PATH or FFMPEG."""
import argparse
import json
import os
import subprocess
from fractions import Fraction

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    with open(args.manifest, encoding="utf8") as stream:
        spec = json.load(stream)
    decoder = [os.environ.get("FFMPEG", "ffmpeg"), "-hide_banner", "-v", "error",
               "-xerror", "-i", args.video]
    first = subprocess.check_output(decoder + ["-map", "0:v:0", "-an", "-frames:v", "1",
                                  "-pix_fmt", "yuv420p", "-f", "yuv4mpegpipe", "-"])
    fields = {t[0]: t[1:] for t in first.split(b"\n", 1)[0].decode().split()[1:]}
    fps = Fraction(fields["F"].replace(":", "/"))
    progress = subprocess.check_output(decoder + ["-map", "0:v:0", "-map", "0:a?",
                "-vsync", "0", "-progress", "pipe:1", "-nostats", "-f", "null", "-"], text=True)
    summary = dict(line.split("=", 1) for line in progress.splitlines() if "=" in line)
    actual = (int(fields["W"]), int(fields["H"]), fps, int(summary["frame"]))
    expected = tuple(spec[k] for k in ("width", "height", "fps", "duration_frames"))
    if actual != expected or summary["progress"] != "end":
        raise ValueError(f"expected {expected}; found {actual}")
    print(json.dumps({"check":"pass","width":actual[0],"height":actual[1],"fps":str(fps),
                      "frames":actual[3],"scope":"declared frame rate, dimensions, decode and frame count"}))

if __name__ == "__main__":
    try:
        main()
    except (KeyError, IndexError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"check":"blocked","reason":str(exc)}))
        raise SystemExit(2)
