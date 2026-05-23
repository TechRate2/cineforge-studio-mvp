# Alibaba Wan 2.2 Animate Mix

An advanced, unified character animation and replacement model that transfers motion, expressions, and timing from a source clip while preserving the identity of a target character from a single reference image. Animate Mix is part of the Wan 2.2 Animate family and focuses on blending the target identity with source motion for coherent, high-quality video generation.

## Overview
- Purpose: Motion transfer and identity preservation from one image to a full video
- Core capability: Mix mode fuses target appearance with source motion dynamics
- Foundation: Built atop Wan2.2 innovations (e.g., MoE-driven diffusion, improved data, high-compression video)
- Typical output: Smooth 24 fps video at up to 720p with holistic movement and expression replication
- Use cases: Character animation, avatar replacement, lip-sync, dynamic explainer clips, social content

## Key Features

- One-image-to-video: Animate a character from a single, high-quality portrait or full-body image
- Motion mix-in: Transfer pose, body motion, facial expressions, and timing from a source video
- Identity retention: Preserve clothing, face, and hair of the target character while adopting motion
- Holistic dynamics: Handles subtle micro-expressions, head motion, and body kinematics
- Robustness: Works across varied camera motions and moderate occlusions with careful input selection
- **Motion + Identity Transfer:** Applies actions and facial expressions from a reference video while preserving the target character’s face, hair, and clothing.
- **Dual Modes:**
    - **Standard Mode (wan-std):** Optimized for speed and cost; ideal for previews and basic outputs.
    - **Professional Mode (wan-pro):** Smoother motion and higher fidelity for production use (higher time/cost).
- **Flexible Input Support:** Handles wide image/video resolutions and aspect ratios for diverse pipelines.
- **Long Duration:** Supports reference videos from 2 to 30 seconds.
- **Holistic Dynamics:** Captures pose, micro‑expressions, head motion, and timing for coherent results.

## Designed For

- **Content Creators:** Identity-preserving avatar animation for social content.
- **Game Developers:** Rapid prototyping of character motion with reference clips.
- **Marketing & Advertising:** Transform static assets into dynamic character videos.
- **Animation Enthusiasts:** Experiment with motion transfer and identity mixing.

## Input Requirements

To achieve the best results, follow these guidelines:

### Character Image
- **Content:** One person, facing the camera, face fully visible and unobstructed; the subject should occupy a moderate portion of the frame.
- **Format:** JPG, JPEG, PNG, BMP, WEBP.
- **Dimensions:** Width and height between 200 and 4096 pixels.
- **Aspect Ratio:** Between 1:3 and 3:1.
- **File Size:** Max 5 MB.

### Reference Video (Motion Source)
- **Content:** One person with clearly visible face; stable framing improves motion transfer.
- **Format:** MP4, AVI, MOV.
- **Duration:** 2 to 30 seconds.
- **Dimensions:** Width and height between 200 and 2048 pixels.
- **Aspect Ratio:** Between 1:3 and 3:1.
- **File Size:** Max 200 MB.
- **Recommendation:** Higher resolution and frame rate yield better identity preservation and smoother motion.

## Pricing

Billing is based on generated video duration and selected mode.

- **Billing Logic:** Cost scales with video duration.
- **Mode Multiplier:**
    - **Standard Mode:** 1.0x base rate.
    - **Professional Mode:** 1.5x base rate.
- Service transitions to paid billing once the free quota is used; set up a payment method early to avoid interruptions.

## How to Use

1. **Upload Character Image:** Provide a clear identity reference for the target character.
2. **Upload Reference Video:** Select a clip containing the desired motion and expressions.
3. **Select Mode:** Choose "Standard" (wan‑std) for speed or "Professional" (wan‑pro) for quality.
4. **Generate:** Submit to produce the identity‑preserving animated video.

## Best Practices

- Use high‑resolution, well‑lit images; avoid occlusions and heavy motion blur.
- Choose a motion source with matching vibe (tempo, style, emotion) to your target.
- Keep backgrounds simple to reduce artifacts and improve identity retention.
- Prefer moderate motion complexity; extreme spins or strong occlusions may degrade quality.

## Limitations

- Identity drift may occur with occlusions, extreme camera motion, or low‑quality inputs.
- Fast‑moving props or complex interactions can introduce artifacts and temporal instability.
- Lip‑sync quality depends on clarity of the source clip and face visibility in the reference image.

## Safety and Content

- Respect privacy and consent when using identity transfer.
- Follow platform policies and local regulations.
- Avoid generating harmful or restricted content.

## Version

- Model: Alibaba Wan 2.2 Animate Mix
- Family: Wan2.2 Animate (Move/Mix)
- Technical context: Wan 2.2 with MoE‑driven video diffusion and improved training data
