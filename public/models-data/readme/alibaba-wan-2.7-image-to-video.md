## Alibaba WAN 2.7 Image-to-Video

**Alibaba WAN 2.7 Image-to-Video** animates images into videos with multiple generation modes: first-frame, first-and-last-frame, video continuation, and audio-driven animation.

## What makes it stand out?

- **Multiple animation modes:** Start from a single image, control both start and end frames, or extend an existing video clip.
- **Audio-driven generation:** Provide a driving audio file to generate lip-synced or action-matched video content.
- **Multi-shot support:** Generate multi-shot narratives with natural transitions and scene variety.
- **Up to 15 seconds:** Generate videos from 2 to 15 seconds at 720P or 1080P resolution.

## Designed For

- Creators who want to bring still images to life with motion and sound.
- Teams building video content from existing image assets or storyboard frames.
- Anyone who needs controlled video generation with specific start and end states.

## How to Use

1. **First-frame mode:** Provide an `image` URL. The model animates it into a video.
2. **First-and-last-frame mode:** Provide both `image` (start) and `last_image` (end). The model generates a transition between them.
3. **Video continuation:** Provide a `video` clip URL. The model extends the content.
4. **Audio-driven:** Add an `audio` URL to any mode. The model matches the video to the audio.
5. Add a text prompt to guide the video content and style.
