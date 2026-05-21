import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


INPUT_DIR = Path(os.getenv("INPUT_DIR", "/app/input"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/app/output"))
SUPPORTED_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm")

# Conservative space reserved for MP4 metadata/container overhead so the final
# output stays under the user-requested limit instead of merely near it.
SIZE_SAFETY_FACTOR = 0.965

MIN_VIDEO_BITRATE_KBPS = 120
MIN_AUDIO_BITRATE_KBPS = 32
DEFAULT_AUDIO_BITRATE_KBPS = 96


@dataclass(frozen=True)
class MediaInfo:
    duration_seconds: float
    width: int
    height: int
    has_audio: bool


@dataclass(frozen=True)
class EncodePlan:
    codec: str
    video_bitrate_kbps: int
    audio_bitrate_kbps: int
    max_height: int


def get_video_files():
    return sorted(
        f for f in os.listdir(INPUT_DIR)
        if f.lower().endswith(SUPPORTED_EXTENSIONS)
    )


def run_command(cmd):
    subprocess.run(cmd, check=True)


def probe_media(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    duration = float(data["format"]["duration"])
    video_stream = next(
        stream for stream in data["streams"]
        if stream.get("codec_type") == "video"
    )
    audio_stream = next(
        (
            stream for stream in data["streams"]
            if stream.get("codec_type") == "audio"
        ),
        None,
    )

    return MediaInfo(
        duration_seconds=duration,
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        has_audio=audio_stream is not None,
    )


def choose_audio_bitrate(total_bitrate_kbps, has_audio):
    if not has_audio:
        return 0

    if total_bitrate_kbps < MIN_VIDEO_BITRATE_KBPS + MIN_AUDIO_BITRATE_KBPS:
        return MIN_AUDIO_BITRATE_KBPS

    # Use better audio when the target allows it, but tiny files need most of
    # the budget for video or they turn into blur.
    max_audio_that_leaves_video = total_bitrate_kbps - MIN_VIDEO_BITRATE_KBPS
    if total_bitrate_kbps >= 1_200 and max_audio_that_leaves_video >= 128:
        return 128
    if total_bitrate_kbps >= 700 and max_audio_that_leaves_video >= DEFAULT_AUDIO_BITRATE_KBPS:
        return DEFAULT_AUDIO_BITRATE_KBPS
    if total_bitrate_kbps >= 450 and max_audio_that_leaves_video >= 64:
        return 64
    if max_audio_that_leaves_video >= 48:
        return 48
    return MIN_AUDIO_BITRATE_KBPS


def choose_max_height(video_bitrate_kbps, source_height):
    # Lower resolution usually looks sharper than full-resolution mush when the
    # bitrate budget is tiny.
    if video_bitrate_kbps < 220:
        max_height = 240
    elif video_bitrate_kbps < 420:
        max_height = 360
    elif video_bitrate_kbps < 850:
        max_height = 480
    elif video_bitrate_kbps < 1_800:
        max_height = 720
    elif video_bitrate_kbps < 3_500:
        max_height = 1080
    else:
        max_height = source_height

    return min(source_height, max_height)


def build_encode_plan(media, target_mb, prefer_h265):
    usable_bits = target_mb * 1024 * 1024 * 8 * SIZE_SAFETY_FACTOR
    total_bitrate_kbps = int(usable_bits / media.duration_seconds / 1000)

    audio_bitrate_kbps = choose_audio_bitrate(
        total_bitrate_kbps,
        media.has_audio,
    )
    video_bitrate_kbps = total_bitrate_kbps - audio_bitrate_kbps

    if video_bitrate_kbps < MIN_VIDEO_BITRATE_KBPS:
        required_kbps = MIN_VIDEO_BITRATE_KBPS + audio_bitrate_kbps
        required_mb = (
            required_kbps
            * 1000
            * media.duration_seconds
            / 8
            / 1024
            / 1024
            / SIZE_SAFETY_FACTOR
        )
        raise ValueError(
            f"Target is too small for usable video. Try at least "
            f"{required_mb:.2f} MB for this duration."
        )

    return EncodePlan(
        codec="libx265" if prefer_h265 else "libx264",
        video_bitrate_kbps=video_bitrate_kbps,
        audio_bitrate_kbps=audio_bitrate_kbps,
        max_height=choose_max_height(video_bitrate_kbps, media.height),
    )


def scale_filter(max_height):
    return (
        "scale='if(gt(ih,{h}),-2,iw)':'if(gt(ih,{h}),{h},ih)'"
        .format(h=max_height)
    )


def codec_options(plan):
    if plan.codec == "libx265":
        return [
            "-c:v", "libx265",
            "-preset", "slow",
            "-tag:v", "hvc1",
        ]

    return [
        "-c:v", "libx264",
        "-preset", "veryslow",
        "-profile:v", "high",
    ]


def first_pass_options(plan, passlog):
    if plan.codec == "libx265":
        return [
            *codec_options(plan),
            "-x265-params", f"pass=1:stats={passlog}:log-level=error",
        ]

    return [
        *codec_options(plan),
        "-pass", "1",
        "-passlogfile", passlog,
    ]


def second_pass_options(plan, passlog):
    if plan.codec == "libx265":
        return [
            *codec_options(plan),
            "-x265-params", f"pass=2:stats={passlog}:log-level=error",
        ]

    return [
        *codec_options(plan),
        "-pass", "2",
        "-passlogfile", passlog,
    ]


def cleanup_pass_files(passlog):
    for suffix in ("", ".log", ".log.mbtree", "-0.log", "-0.log.cutree"):
        path = Path(f"{passlog}{suffix}")
        if path.exists():
            path.unlink()


def compress_video(input_path, target_mb, prefer_h265=True):
    media = probe_media(input_path)
    plan = build_encode_plan(media, target_mb, prefer_h265)

    filename = input_path.name
    name = input_path.stem
    output_path = OUTPUT_DIR / f"{name}_final.mp4"
    passlog = f"/tmp/{name}_ffmpeg_pass"
    null_output = "NUL" if os.name == "nt" else "/dev/null"
    target_bytes = int(target_mb * 1024 * 1024)

    print(f"\nInput: {filename}")
    print(f"Duration: {media.duration_seconds:.2f}s")
    print(f"Source: {media.width}x{media.height}")
    print(f"Target size: {target_mb:.2f} MB")
    print(f"Codec: {plan.codec}")
    print(f"Video bitrate: {plan.video_bitrate_kbps}k")
    if plan.audio_bitrate_kbps:
        print(f"Audio bitrate: {plan.audio_bitrate_kbps}k")
    else:
        print("Audio: none")
    print(f"Max output height: {plan.max_height}p")

    filter_args = ["-vf", scale_filter(plan.max_height), "-pix_fmt", "yuv420p"]
    audio_args = ["-an"]
    if plan.audio_bitrate_kbps:
        audio_args = [
            "-map", "0:a:0?",
            "-c:a", "aac",
            "-b:a", f"{plan.audio_bitrate_kbps}k",
            "-ac", "2",
        ]

    try:
        run_command([
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-map", "0:v:0",
            *filter_args,
            "-b:v", f"{plan.video_bitrate_kbps}k",
            *first_pass_options(plan, passlog),
            "-an",
            "-sn",
            "-f", "null",
            null_output,
        ])

        run_command([
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-map", "0:v:0",
            *audio_args,
            "-map_metadata", "0",
            *filter_args,
            "-b:v", f"{plan.video_bitrate_kbps}k",
            *second_pass_options(plan, passlog),
            "-sn",
            "-movflags", "+faststart",
            str(output_path),
        ])
    finally:
        cleanup_pass_files(passlog)

    output_bytes = output_path.stat().st_size
    output_mb = output_bytes / 1024 / 1024
    print(f"\nDone: {output_path}")
    print(f"Output size: {output_mb:.2f} MB")

    if output_bytes > target_bytes:
        output_path.unlink()
        raise RuntimeError(
            "FFmpeg exceeded the requested limit even with the safety margin. "
            "Try a slightly smaller target or use H.265 if you selected H.264."
        )


def ask_video_choice(files):
    while True:
        try:
            choice = int(input("\nSelect video number: "))
            if 1 <= choice <= len(files):
                return files[choice - 1]
        except ValueError:
            pass
        print("Please enter a valid video number.")


def ask_target_mb():
    while True:
        try:
            target_mb = float(input("Enter target size in MB, e.g. 10: "))
            if target_mb > 0:
                return target_mb
        except ValueError:
            pass
        print("Please enter a positive number.")


def ask_prefer_h265():
    if not shutil.which("ffmpeg"):
        return True

    answer = input(
        "Use H.265/HEVC for better quality at small sizes? [Y/n]: "
    ).strip().lower()
    return answer not in {"n", "no"}


if __name__ == "__main__":
    files = get_video_files()

    if not files:
        print("No video files found in input folder.")
        raise SystemExit(1)

    print("\nVideos found:")
    for i, file in enumerate(files, start=1):
        print(f"{i}. {file}")

    selected_file = ask_video_choice(files)
    target_mb = ask_target_mb()
    prefer_h265 = ask_prefer_h265()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    compress_video(INPUT_DIR / selected_file, target_mb, prefer_h265)
