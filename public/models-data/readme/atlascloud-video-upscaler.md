# Video Upscaler

Video Upscaler improves an existing video to a higher output resolution. Upload or provide a video URL, then choose 1080p or 2K output.

## Highlights

- **Video-to-video upscaling:** Improve an existing clip without changing the source content.
- **Two output tiers:** Choose `1080p` for standard high definition or `2k` for the 2560x1440 pixel tier. 4K is planned for a later release.
- **Source timing preserved:** The workflow does not request a new target frame rate.
- **Input caps:** Maximum input duration is 53s for 1080p and 23s for 2K. Input fps must be 30 or lower.
- **Workflow-backed output:** Results are returned as playable video URLs.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `model` | Yes | Use `atlascloud/video-upscaler`. |
| `video` | Yes | Input video URL. |
| `target_resolution` | No | Output resolution: `1080p` or `2k` (2560x1440 pixel tier). Default: `1080p`. |

## Limits

The input video metadata is probed server-side before billing and processing. Requests over the duration, fps, or frame-count limit are rejected for the selected target resolution.

| Target resolution | Pixel tier | Maximum input duration | Maximum input frames |
|-------------------|------------|------------------------|----------------------|
| 1080p | 1920x1080 | 53 seconds | 1590 |
| 2K | 2560x1440 | 23 seconds | 690 |

Input fps must be 30 or lower. The workflow preserves source timing and does not request a new target fps.

## Example Request

```json
{
  "model": "atlascloud/video-upscaler",
  "video": "https://static.atlascloud.ai/media/videos/af3ce4416487e61f8b299c5dc42642e3.mp4",
  "target_resolution": "1080p"
}
```

## Pricing

Billing matches the WaveSpeed FlashVSR public pricing model: billable seconds are the input video duration rounded up to whole seconds, with a 5 second minimum. Frame count and fps are validation limits only; they do not change the price.

| Target resolution | Unit price | 5s minimum |
|-------------------|------------|------------|
| 1080p | `$0.0180 / second` | `$0.09` |
| 2K | `$0.0240 / second` | `$0.12` |
