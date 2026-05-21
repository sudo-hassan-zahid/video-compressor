import os
import subprocess

INPUT_DIR = "/app/input"
OUTPUT_DIR = "/app/output"

def get_video_files():
    return [
        f for f in os.listdir(INPUT_DIR)
        if f.lower().endswith((".mp4", ".mov", ".mkv", ".avi", ".webm"))
    ]

def get_duration_seconds(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())

def compress_video(input_path, target_mb):
    duration = get_duration_seconds(input_path)

    audio_bitrate_kbps = 96
    target_bits = target_mb * 1024 * 1024 * 8
    video_bitrate_kbps = int((target_bits / duration / 1000) - audio_bitrate_kbps)

    if video_bitrate_kbps < 100:
        raise ValueError("Target size too small. The video would look like it was filmed on a potato.")

    filename = os.path.basename(input_path)
    name, _ = os.path.splitext(filename)
    output_path = os.path.join(OUTPUT_DIR, f"{name}_final.mp4")

    passlog = f"/tmp/{name}_ffmpeg_pass"

    print(f"\nDuration: {duration:.2f}s")
    print(f"Target size: {target_mb} MB")
    print(f"Video bitrate: {video_bitrate_kbps}k")
    print(f"Audio bitrate: {audio_bitrate_kbps}k")

    subprocess.run([
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-b:v", f"{video_bitrate_kbps}k",
        "-pass", "1",
        "-passlogfile", passlog,
        "-an",
        "-f", "null",
        "/dev/null"
    ], check=True)

    subprocess.run([
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-b:v", f"{video_bitrate_kbps}k",
        "-pass", "2",
        "-passlogfile", passlog,
        "-c:a", "aac",
        "-b:a", f"{audio_bitrate_kbps}k",
        "-movflags", "+faststart",
        output_path
    ], check=True)

    print(f"\nDone: {output_path}")

if __name__ == "__main__":
    files = get_video_files()

    if not files:
        print("No video files found in input folder.")
        exit(1)

    print("\nVideos found:")
    for i, file in enumerate(files, start=1):
        print(f"{i}. {file}")

    choice = int(input("\nSelect video number: "))
    target_mb = float(input("Enter target size in MB, e.g. 1.9: "))

    selected_file = files[choice - 1]
    input_path = os.path.join(INPUT_DIR, selected_file)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    compress_video(input_path, target_mb)