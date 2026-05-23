## Kling Video O3 Pro Video Edit

Kling Video O3 Pro Video Edit is Kuaishou's most advanced video editing model, enabling natural-language-driven edits on existing video footage. Upload a video, describe the change you want — swap objects, alter scenes, shift styles — and get high-quality edited results with preserved motion and structure. Supports up to 4 reference images for precise visual guidance and optional original audio retention.

## Why Choose This?

Prompt-driven editing Describe your edits in plain language — no timeline, no masks, no manual keyframing required.

Reference image support Attach up to 4 reference images to guide the target element, scene, or style in the output.

Audio preservation Keep the original soundtrack intact with the keep_original_sound option.

Scene-level understanding The model recognizes objects, backgrounds, and context within the video to apply accurate, context-aware edits.

Motion-consistent output Edits blend naturally across frames with strong temporal coherence — minimal flicker or ghosting.

## Parameters

| Parameter | Required | Description |
| --- | --- | --- |
| prompt | Yes | Text description of the desired edit |
| video | Yes | Input video to edit (URL or upload) |
| images | No | Up to 4 reference images for element, scene, or style guidance |
| keep_original_sound | No | Whether to keep the original sound from the video (default: enabled) |

## How to Use

1. Run — submit and download the edited video.
2. Set audio preference — toggle keep_original_sound to preserve or remove original audio.
3. Add reference images (optional) — attach up to 4 images to steer the look of elements or styles.
4. Write your prompt — describe exactly what should change (e.g., "Change the beer to Cola.").
5. Upload your video — drag-and-drop, file upload, or paste a public URL.

## Best Use Cases

- Storytelling & Film — Adjust scene details, atmosphere, or objects to refine narrative visuals in post-production.
- Creative Exploration — Experiment with style changes, scene swaps, and visual concepts on existing footage.
- E-commerce — Edit product videos to showcase different variants, colors, or settings from a single source clip.
- Brand & Marketing — Replace or update branded elements across video assets without reshooting.
- Social Media Campaigns — Quickly swap products, backgrounds, or props in short-form videos.

## Pro Tips

- Ensure video URLs are publicly accessible — a preview thumbnail in the interface confirms the link works.
- Test edits on shorter clips first, then apply to longer footage once satisfied.
- Keep keep_original_sound enabled when audio continuity matters for your project.
- Reference images work best when they clearly represent the target element or style.
- Use clear, specific prompts describing exactly what should change for best results.

## Notes

- If using a URL, make sure it is publicly accessible.
- Billed duration is clamped between 3 and 10 seconds regardless of actual video length.
- Both prompt and video are required fields.

## Related Models

- Kling Video O3 Pro Reference-to-Video — Create videos guided by reference images for consistent character and style control.
- Kling Video O3 Std Image-to-Video — Animate still images into video with the cost-efficient O3 Standard model.
- Kling Video O3 Pro Text-to-Video — Generate videos from text prompts with O3 Pro's highest quality output.
