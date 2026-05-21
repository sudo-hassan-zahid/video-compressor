# Dockerized Video Compressor

Simple interactive video compression utility built with Python, FFmpeg, Docker, and Docker Compose.

The script allows users to:

- Select a video file from the `input/` folder
- Enter a target size in MB
- Compress the video automatically
- Generate an optimized MP4 output with `_final` suffix

FFmpeg runs completely inside Docker, avoiding local Windows FFmpeg installation headaches. Civilization peaked when developers started containerizing their dependency trauma.

---

# Features

- Interactive CLI workflow
- Automatic bitrate calculation
- Target-size-based compression
- Two-pass FFmpeg encoding
- AAC audio encoding
- MP4 output generation
- Dockerized setup
- Windows-friendly
- Clean input/output workflow

---

# Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| Compression Engine | FFmpeg |
| Containerization | Docker |
| Orchestration | Docker Compose |
| Video Codec | H.264 (libx264) |
| Audio Codec | AAC |
| Output Format | MP4 |

---

# Project Structure

```txt
video-compressor/
│
├── Dockerfile
├── docker-compose.yml
├── compress_video.py
│
├── input/
│   └── sample.mp4
│
└── output/
    └── sample_final.mp4
```

---

# Supported Input Formats

```txt
.mp4
.mov
.mkv
.avi
.webm
```

---

# Output Format

```txt
.mp4
```

Example:

```txt
sample.mp4
→
sample_final.mp4
```

---

# Prerequisites

Install:

- Docker Desktop
- Docker Compose

Verify installation:

```bash
docker --version
docker compose version
```

---

# Setup

## 1. Clone Project

```bash
mkdir video-compressor
cd video-compressor
```

---

## 2. Create Required Directories

```bash
mkdir input output
```

---


## 3. Add Video File

Place video files inside:

```txt
input/
```

Example:

```txt
input/sample.mp4
```

---

# Build

Build the Docker image:

```bash
docker compose build
```

---

# Run

Start the interactive compressor:

```bash
docker compose run --rm video-compressor
```

---

# Usage

After starting the container:

```txt
Videos found:
1. sample.mp4
```

Select video:

```txt
Select video number: 1
```

Enter target size:

```txt
Enter target size in MB, e.g. 1.9: 1.9
```

Compression process will begin automatically.

---

# Verify Output

Compressed files are generated inside:

```txt
output/
```

Example:

```txt
sample_final.mp4
```

---

# Verify File Size

## Linux / Git Bash

```bash
ls -lh input output
```

---

## Windows CMD

```cmd
dir input
dir output
```

---

## PowerShell

```powershell
Get-ChildItem input, output
```

---

# Rebuild Container

Rebuild after changing Dockerfile or dependencies:

```bash
docker compose build --no-cache
```

---

# Stop / Clean Containers

Remove stopped containers:

```bash
docker container prune
```

---

# Remove Built Image

```bash
docker image rm video-compressor-video-compressor
```

---

# Notes

- Smaller target sizes reduce quality
- Longer videos require larger target sizes
- Two-pass encoding improves compression accuracy
- FFmpeg runs entirely inside Docker
- No direct Windows FFmpeg installation required