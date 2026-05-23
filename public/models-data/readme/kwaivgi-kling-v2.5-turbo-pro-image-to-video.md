# Kling 2.5 Turbo Pro (Image-to-Video)

**Kling 2.5 Turbo Pro** turns a single image and a text prompt into cinematic video with fluid motion and accurate intent. A new text-timing engine, improved dynamics, and faster inference enable high-speed action and complex camera moves with stable frames, while refined conditioning preserves palette, lighting, and mood.

This version additionally supports **first–last frame control**: you can specify both a starting image and an ending image, and the model will animate a smooth transformation between them.

## What makes it stand out?

*   **Better prompt understanding**
    Precisely parses multi-step, causal instructions and turns a single image and prompt into coherent, well-paced shots that stay true to your creative idea.

*   **More realistic look and greater stability**
    Improved dynamics and balanced training data closely mimic real-world motion, even at high speeds and with complex camera moves. Playback is smooth with fewer jitters, tears, and dropped details.

*   **Detail and style consistency**
    Refined image conditioning maintains color, lighting, brushwork, and mood, keeping frames visually unified even during aggressive motion or transitions.

*   **First–last frame animation**
    When you provide both an initial image and a `last_image`, Kling 2.5 Turbo Pro treats them as keyframes and generates a video that naturally evolves from the first to the last frame.

## Inputs

*   **`image`** (required)
    The starting frame of your video. Composition, style, and subject are primarily taken from this image.

*   **`last_image`** (optional)
    An optional target frame. If provided, the model interpolates between `image` and `last_image`, creating a smooth visual evolution from start to end.

*   **`prompt`** (required)
    Text description of the scene, actions, camera movement, and style.

*   **`negative_prompt`** (optional)
    Things you want the model to avoid (for example, blur, text overlays, distortions).

*   **`guidance_scale`**
    Controls how strongly the model follows the prompt versus being more free-form.
    *   Lower values = more creative variation.
    *   Higher values = stricter adherence to the prompt.

*   **`duration`**
    Length of the generated video:
    *   5 seconds
    *   10 seconds

## Output

A single video clip of the chosen duration, animated from the initial image (and optionally toward the `last_image`) according to your prompt.

## Designed For

*   **Marketing and brand teams** – Consistent, on-brand motion spots, feature demos, and campaign assets.
*   **Creators / YouTubers / Shorts teams** – Strong narrative motion that boosts watch-through and engagement.
*   **Film / animation studios** – Previz, style tests, and technique exploration with reliable dynamics.
*   **Education and training** – Turn static diagrams or slides into clear, animated explainers.

## How to Use

1.  Upload or paste the URL of your **`image`** as the starting frame.
2.  (Optional) Upload a **`last_image`** if you want the video to end on a specific frame or design.
3.  Write your **`prompt`**, specifying subject, scene, motion, and style.
4.  (Optional) Add a **`negative_prompt`** to filter out unwanted artifacts or styles.
5.  Adjust **`guidance_scale`** to balance between strict prompt following and looser creativity.
6.  Choose the **`duration`** (5 s or 10 s).
7.  Run the model, preview the result, then iterate by tweaking the prompt, images, or `guidance_scale` until you reach the desired look.

---

## Notes

**Pricing Information**

| Duration | Price |
| :--- | :--- |
| 5 s | $0.2800 |
| 10 s | $0.5600 |