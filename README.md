# Useful tools (at least for me)

Small scripts I wrote to solve everyday problems.

## Tools

### 🎬 Video Trimmer

Pick a start and end point in a video and save only that part, with audio.

- Video preview that fits the window
- Timeline with draggable start (green) and end (red) markers
- Step by frame or by second, play/pause
- Frame-accurate cut, exported as `.mp4` (H.264 + AAC)
- Saves in the background, so the window stays responsive

**Requirements:** Python 3.9+ and:

```bash
pip install opencv-python pillow imageio-ffmpeg
```

No separate ffmpeg install is needed; `imageio-ffmpeg` ships its own.

**Run:**

- Windows: double-click `video_trimmer.bat`, or drag a video onto it.
- Any OS: `python video_trimmer.py [video]`

**Shortcuts:**

| Key | Action |
|-----|--------|
| `Space` | Play / pause |
| `←` / `→` | Back / forward 1 frame |
| `Shift` + `←` / `→` | Back / forward 1 second |
| `I` | Set start at current frame |
| `O` | Set end at current frame |
| `Ctrl` + `S` | Save clip |

**Note:** the preview plays without sound; the saved clip keeps the audio.
