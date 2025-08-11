# Assets

Project assets including demos, recordings, and diagrams.

## Structure

```
assets/
├── recordings/
│   ├── raw/           # Original recordings (gitignored)
│   │   └── *.mp4      # Source videos
│   └── processed/     # Optimized versions
│       └── *.gif      # GIF animations (GitHub native)
└── images/            # Static images, diagrams
```

## Recording Workflow

1. **Record demo**: Use GNOME screen recorder with area selection
2. **Save to raw/**: Copy original to `recordings/raw/`
3. **Process**: Convert to optimized GIF in `recordings/processed/`
4. **Track**: Commit GIF files to git (typically 50-100KB)

## Standard Format

All demo recordings use optimized GIF format with these settings:
- **Width**: 640px (full quality, readable)
- **FPS**: 3 frames per second (smooth for terminal demos)
- **Colors**: 16 colors (4-bit palette, clean terminal look)

## Conversion Command

```bash
# Terminal-optimized GIF (simple and effective)
ffmpeg -i raw/demo.mp4 \
  -vf "fps=3,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=16:stats_mode=diff[p];[s1][p]paletteuse=dither=none:diff_mode=rectangle" \
  processed/demo.gif
```

This creates a clean, readable GIF perfect for terminal recordings.

## Current Recordings

- `tmux-popup-demo.mp4` - Original recording (101KB, raw)
- `tmux-popup-demo.gif` - Optimized demo (58KB, processed)