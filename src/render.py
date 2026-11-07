
import os
import sys
import subprocess
from pathlib import Path

import requests

# ==============================
# VGC AUTO EDITOR V1
# ElevenLabs + FFmpeg
# ==============================

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"

VIDEO = INPUT / "video.mp4"
SCRIPT = INPUT / "script.txt"
VOICE = OUTPUT / "voice.mp3"
FINAL = OUTPUT / "final_video.mp4"

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID")

OUTPUT.mkdir(parents=True, exist_ok=True)


def check_requirements():
    if not API_KEY:
        raise RuntimeError(
            "ELEVENLABS_API_KEY missing"
        )

    if not VOICE_ID:
        raise RuntimeError(
            "ELEVENLABS_VOICE_ID missing"
        )

    if not VIDEO.is_file():
        raise FileNotFoundError(
            f"Video not found: {VIDEO}"
        )

    if not SCRIPT.is_file():
        raise FileNotFoundError(
            f"Script not found: {SCRIPT}"
        )

    for program in ["ffmpeg", "ffprobe"]:
        subprocess.run(
            [program, "-version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def generate_voice():
    print("Generating ElevenLabs voice...")

    text = SCRIPT.read_text(
        encoding="utf-8"
    ).strip()

    if not text:
        raise ValueError("Script is empty")

    url = (
        "https://api.elevenlabs.io/v1/"
        f"text-to-speech/{VOICE_ID}"
    )

    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.75,
            "style": 0.25,
            "use_speaker_boost": True,
        },
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=180,
    )

    if response.status_code != 200:
        # Avoid printing API response or secrets.
        raise RuntimeError(
            "ElevenLabs TTS failed. "
            f"HTTP status: {response.status_code}"
        )

    VOICE.write_bytes(response.content)

    if VOICE.stat().st_size == 0:
        raise RuntimeError("Empty voice output")

    print("Voice generated successfully")


def get_duration(path):
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )

    return float(result.stdout.strip())


def render_video():
    print("Rendering final MP4...")

    video_duration = get_duration(VIDEO)
    voice_duration = get_duration(VOICE)

    if video_duration <= 0 or voice_duration <= 0:
        raise RuntimeError("Invalid media duration")

    print(f"Video: {video_duration:.1f}s")
    print(f"Voice: {voice_duration:.1f}s")

    # Keep original video duration.
    # Longer narration will be truncated.
    # Shorter narration leaves remaining video silent.

    filter_video = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,"
        "fps=30,"
        "format=yuv420p"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i", str(VIDEO),
        "-i", str(VOICE),
        "-filter_complex",
        (
            f"[0:v]{filter_video}[v];"
            "[1:a]"
            "apad,"
            "atrim=duration="
            f"{video_duration:.3f}"
            "[a]"
        ),
        "-map", "[v]",
        "-map", "[a]",
        "-t", f"{video_duration:.3f}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-movflags", "+faststart",
        str(FINAL),
    ]

    subprocess.run(command, check=True)

    if not FINAL.is_file():
        raise RuntimeError("MP4 not generated")

    print("Render completed")
    print(f"Output: {FINAL}")


def main():
    try:
        check_requirements()
        generate_voice()
        render_video()
        print("VGC AUTO EDITOR SUCCESS")

    except Exception as error:
        print(
            f"VGC FAILED: {error.__class__.__name__}: {error}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
