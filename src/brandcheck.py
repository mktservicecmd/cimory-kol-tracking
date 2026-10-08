"""Brand check helper for Instagram posts (frames + speech transcript).

Usage:
    python src/brandcheck.py <video_url> <audio_url_or_-> <out_prefix>

Writes <out_prefix>.jpg (8 frames from the first 10 seconds, 4x2 grid) for a
visual check and prints JSON with the speech-transcript hits for "Cimory".
Requires: pip install faster-whisper imageio-ffmpeg
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
# Also matches common mis-transcriptions such as "Simori", "Chimora", "Cermori", "Hemoree".
CIMORY = re.compile(r"\b(c|ch|s|sh|h)[iey]+r?m+[oa]u?r+[iyea]e?\w*|cimory|cimori|simori", re.I)
FRAMES = [0.3, 1.6, 2.9, 4.2, 5.5, 6.8, 8.1, 9.6]
_model = None


def frame_grid(video: str, out: str) -> str | None:
    tmp = []
    for i, t in enumerate(FRAMES):
        f = f"{out}.{i}.jpg"
        subprocess.run([FF, "-v", "error", "-y", "-ss", str(t), "-i", video, "-frames:v", "1", "-vf", "scale=240:-2", f], check=False)
        if os.path.exists(f):
            tmp.append(f)
    if not tmp:
        return None
    args = [FF, "-v", "error", "-y"]
    for f in tmp:
        args += ["-i", f]
    n = len(tmp)
    if n > 1:
        layout = "|".join(f"{(i % 4) * 240}_{'0' if i < 4 else 'h0'}" for i in range(n))
        graph = "".join(f"[{i}:v]" for i in range(n)) + f"xstack=inputs={n}:layout={layout}[o]"
    else:
        graph = "[0:v]copy[o]"
    subprocess.run(args + ["-filter_complex", graph, "-map", "[o]", out], check=False)
    for f in tmp:
        os.remove(f)
    return out if os.path.exists(out) else None


def transcribe(audio: str, language: str | None = None):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
    segs, info = _model.transcribe(audio, language=language, vad_filter=True, beam_size=1)
    segs = list(segs)
    # Whisper sometimes guesses a foreign language for Indonesian speech; retry in Indonesian.
    if language is None and info.language not in ("id", "en", "ms", "jw", "su"):
        return transcribe(audio, "id")
    hits = [(round(s.start, 1), s.text.strip()) for s in segs if CIMORY.search(s.text)]
    return info.language, hits, " ".join(s.text.strip() for s in segs)


def main(video_url: str, audio_url: str, out_prefix: str) -> None:
    with tempfile.TemporaryDirectory() as d:
        v = os.path.join(d, "v.mp4")
        subprocess.run(["curl", "-sS", "-L", "-m", "120", "-o", v, video_url], check=True)
        grid = frame_grid(v, out_prefix + ".jpg")
        res = {"grid": grid}
        if audio_url and audio_url != "-":
            a = os.path.join(d, "a.m4a")
            subprocess.run(["curl", "-sS", "-L", "-m", "120", "-o", a, audio_url], check=True)
            lang, hits, text = transcribe(a)
            res.update(language=lang, hits=hits, text=text[:3000])
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:4])
