# Alibaba Wan 2.2 Animate Move

**Wan2.2-animate-move** is an image-to-animation model that generates a video of a moving person based on a character image and a reference video. It transfers actions and facial expressions from the reference video to the character in the image, offering a low‑cost alternative to motion capture.

## Key Features

- **Motion Transfer:** Effectively captures motion from a reference video and applies it to a static character image.
- **Dual Modes:**
    - **Standard Mode (wan-std):** Optimized for speed and cost-effectiveness, ideal for quick previews and basic animation needs.
    - **Professional Mode (wan-pro):** Delivers smoother animation and higher overall quality, suitable for production-grade outputs (processing time and cost are higher).
- **Flexible Input Support:** Handles a wide range of resolutions (200px to 4096px for images, up to 2048px for videos) and aspect ratios (1:3 to 3:1).
- **Long Duration:** Supports reference videos ranging from 2 to 30 seconds.

## Designed For

- **Content Creators:** Quickly animate avatars or characters for social media content.
- **Game Developers:** Prototype character animations using video references.
- **Marketing & Advertising:** Create dynamic character videos from static assets for campaigns.
- **Animation Enthusiasts:** Experiment with motion transfer and character animation.

## Input Requirements

To ensure the best results, please adhere to the following guidelines:

### Character Image
- **Content:** Should contain only one person, facing the camera directly, with the face fully visible and unobstructed. The person should occupy a moderate portion of the frame.
- **Format:** JPG, JPEG, PNG, BMP, WEBP.
- **Dimensions:** Width and height between 200 and 4096 pixels.
- **Aspect Ratio:** Between 1:3 and 3:1.
- **File Size:** Max 5 MB.

### Reference Video
- **Content:** Should contain only one person, facing the camera directly, with the face fully visible and unobstructed.
- **Format:** MP4, AVI, MOV.
- **Duration:** 2 to 30 seconds.
- **Dimensions:** Width and height between 200 and 2048 pixels.
- **Aspect Ratio:** Between 1:3 and 3:1.
- **File Size:** Max 200 MB.
- **Recommendation:** Higher resolution and frame rate in the reference video lead to better output quality.

## Pricing

Pricing is based on the duration of the generated video and the selected mode.

- **Billing Logic:** Cost is calculated based on the video duration.
- **Mode Multiplier:**
    - **Standard Mode:** 1.0x base rate.
    - **Professional Mode:** 1.5x base rate.

## How to Use

1. **Upload Character Image:** Select a clear image of the character you want to animate.
2. **Upload Reference Video:** Choose a video containing the desired movements.
3. **Select Mode:** Choose between "Standard" (wan-std) for speed or "Professional" (wan-pro) for quality.
4. **Generate:** Submit the request to generate your animated video.