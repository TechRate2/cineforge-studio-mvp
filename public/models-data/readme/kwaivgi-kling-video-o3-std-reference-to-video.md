## Kling Video O3 Std Reference-to-Video

Kling Video O3 Standard Reference-to-Video generates new videos guided by reference images and an optional reference video, maintaining consistent characters, styles, and scenes. Describe a scenario involving the people or elements in your reference images — the model brings them together in a coherent, natural video. Supports flexible duration, aspect ratio control, and optional sound generation.

## Why Choose This?

Character-consistent generation Upload reference images of specific people or elements, and the model preserves their identity throughout the generated video.

Multi-reference support Provide multiple reference images to combine different characters, styles, or elements in one scene.

Optional reference video Supply a reference video for motion guidance, style transfer, or scene continuity.

Sound options Keep original audio from a reference video, or generate new synchronized sound effects.

Flexible output Multiple aspect ratios (16:9, 9:16, 1:1, etc.) and duration from 3 to 15 seconds.

## Parameters

| Parameter | Required | Description |
| --- | --- | --- |
| prompt | Yes | Text description of the desired scene and action |
| video | No | Reference video for motion or style guidance |
| images | No | Reference images of characters, elements, or styles |
| keep_original_sound | No | Keep the original sound from the reference video (default: enabled) |
| sound | No | Generate synchronized audio for the video (default: disabled) |
| aspect_ratio | No | Video aspect ratio (default: 16:9) |
| duration | No | Video length: 3–15 seconds (default: 5) |

## How to Use

1. Run — submit and download your video.
2. Set sound preference — keep original audio from the reference video, or enable generated sound.
3. Set duration — choose any length from 3 to 15 seconds.
4. Choose aspect ratio — select the format that fits your platform.
5. Add reference video (optional) — provide a video for motion or style guidance.
6. Add reference images — upload images of the characters, objects, or styles you want in the video.
7. Write your prompt — describe the scene, referencing the characters or elements in your images (e.g., "The man in Figure 2 is walking with the woman in Figure 1 in the park.").

## Best Use Cases

- Style Transfer — Use a reference video to guide the motion and visual style of new content.
- Creative Concepting — Combine multiple characters or elements into new scenarios for rapid ideation.
- Marketing & Ads — Generate brand ambassador or spokesperson videos from still photos.
- Social Media Content — Produce personalized short-form videos with consistent character identity.
- Character-Driven Storytelling — Create scenes starring specific characters from your reference images.

## Pro Tips

- Match aspect ratio to your target platform: 16:9 for YouTube, 9:16 for TikTok/Reels.
- Use shorter durations (3–5 s) for testing character consistency before generating longer clips.
- Adding a reference video significantly enhances motion quality.
- Use "Figure 1", "Figure 2" etc. in your prompt to refer to specific reference images in order.
- Reference images with clear faces and distinct features produce the best character consistency.

## Notes

- Ensure uploaded URLs are publicly accessible.
- Duration supports any value from 3 to 15 seconds.
- Prompt is the only required field, but reference images are recommended for best results.

## Related Models

- Kling Video O3 Std Video Edit — Edit existing videos with natural-language instructions.
- Kling Video O3 Std Text-to-Video — Generate videos from text prompts at Standard pricing.
- Kling Video O3 Std Image-to-Video — Animate a single image into video at Standard pricing.
- Kling Video O3 Pro Reference-to-Video — Maximum quality reference-to-video with O3 Pro tier.
