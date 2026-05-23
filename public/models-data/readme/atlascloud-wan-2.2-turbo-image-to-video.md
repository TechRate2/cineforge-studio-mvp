# Wan 2.2 Turbo Image-to-Video

Wan 2.2 Turbo Image-to-Video turns a reference image into a short, smooth video clip with fast generation and 30 fps post-processing. It is designed for single-clip motion, quick iteration, and final outputs at 480p, 720p, or 1080p.

## Highlights

- **Fast single-clip generation:** Create a 5 second image-to-video clip from one prompt and one source image.
- **Selectable output resolution:** Choose 480p, 720p, or 1080p output. 720p and 1080p are produced through the video super-resolution workflow.
- **30 fps output:** The workflow applies 30 fps post-processing for smoother playback.
- **Prompt-faithful motion:** Works best when the prompt describes motion, camera movement, and temporal changes rather than repeating static image details.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `model` | Yes | Use `atlascloud/wan-2.2-turbo/image-to-video`. |
| `image` | Yes | First-frame image URL or Base64 image. |
| `prompt` | Yes | Text prompt describing the desired motion. |
| `resolution` | No | Output resolution: `480p`, `720p`, or `1080p`. Default: `720p`. |
| `duration` | No | Video duration in seconds. Fixed at `5`. |
| `negative_prompt` | No | Optional negative prompt. |
| `seed` | No | Random seed for reproducibility; `-1` means random. |

## Example Request

```json
{
  "model": "atlascloud/wan-2.2-turbo/image-to-video",
  "prompt": "A classic golden Cadillac speeds through a desert road, kicking up dust as the camera tracks alongside it.",
  "image": "https://static.atlascloud.ai/media/images/db548fe3bd5cafa4ef7e0141d69c8566.jpeg",
  "duration": 5,
  "resolution": "1080p",
  "seed": -1
}
```

## Pricing

Billing is per generated second with a 5 second minimum.

| Resolution | Formula | 5s price |
|------------|---------|----------|
| 480p | `$0.0200 x 5 x 1` | `$0.10` |
| 720p | `$0.0200 x 5 x 2` | `$0.20` |
| 1080p | `$0.0200 x 5 x 3` | `$0.30` |

No model-level discount is applied.

## Prompt Tips

- Describe movement: subject motion, camera movement, speed, and timing.
- Keep prompts concise and action-focused.
- Use a clear, well-composed input image with the main subject visible.
- Match the requested motion to what the source image can plausibly support.
