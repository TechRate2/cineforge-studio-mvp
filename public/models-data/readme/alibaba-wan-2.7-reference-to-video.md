## Alibaba WAN 2.7 Reference-to-Video

**Alibaba WAN 2.7 Reference-to-Video** generates character-driven videos from reference images and videos, supporting multi-subject scenes and voice cloning.

## What makes it stand out?

- **Character consistency:** Provide reference images or videos of characters, and the model preserves their appearance across the generated video.
- **Multi-subject scenes:** Include up to 5 reference materials (images + videos combined) to create scenes with multiple characters interacting.
- **Voice cloning:** Attach a voice reference audio to transfer a character's voice into the generated video.
- **Flexible framing:** Five aspect ratios (16:9, 9:16, 1:1, 4:3, 3:4) at 720P or 1080P.

## Designed For

- Creators building character-driven stories that need consistent character identity across clips.
- Teams producing multi-character interaction videos from a set of reference assets.
- Anyone who wants to animate a character from a photo or short clip with a specific voice.

## How to Use

1. Write a prompt using labels like "character1" and "character2" to reference each subject.
2. Provide reference materials in order: the first image or video maps to character1, the second to character2, and so on.
3. Each reference should contain only one subject (person, animal, or object).
4. Optionally add a `reference_voice` audio URL to give a character a specific voice.
5. Set resolution, ratio, and duration for the output video.
