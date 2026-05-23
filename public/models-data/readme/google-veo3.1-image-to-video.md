# Google Veo 3.1 — Image-to-Video (I2V) Model

**Veo 3.1 I2V** is Google DeepMind’s latest **image-to-video** generation model — an evolution of Veo’s cinematic foundation. It transforms **a single still image** or **a pair of start & end frames** into a **high-fidelity 1080p motion sequence** with natural movement, realistic lighting, and synchronized contextual audio.

Perfect for **storyboarding**, **concept animation**, and **creative scene development**, Veo 3.1 I2V captures the feeling of camera motion and environmental change while preserving your image’s style and composition.

---

## Why it stands out

* ** Cinematic Motion Generation**

  Animates still images with realistic subject and camera movement — from subtle pans to sweeping transitions.

* ** Frame Interpolation**

  Supports **single-frame animation** and **two-frame transitions** — letting you morph from one image to another with fluid continuity.

* ** Native Audio Support**

  Adds synchronized ambient sound, dialogue, or music automatically aligned with visual motion.

* ** Contextual Understanding**

  Interprets both image content and prompt text to guide scene flow and atmosphere.

* ** High-Resolution Output**

  Generates at **720p or 1080p**, **24 FPS**, and supports **landscape (16:9)** or **portrait (9:16)** aspect ratios.

---

## Key Parameters

* **prompt** — Describe motion or story context (e.g., “Slow dolly zoom on a city skyline as sunset light fades”).

* **image** — Provide a **starting frame** (JPEG / PNG / WEBP).

* **lastFrame** *(optional)* — Provide an **ending frame** to create an interpolation-style transition.

* **durationSeconds** — Choose video length: **4s**, **6s**, or **8s**.

* **resolution** — 720p or 1080p.

* **aspectRatio** — Landscape (16:9) or Portrait (9:16).

---

## Pricing (Preview Stage)

| Model                        | Description                             | Input Type         | Output        |           Price |
| ---------------------------- | --------------------------------------- | ------------------ | ------------- | --------------: |
| Veo 3.1 (Video + Audio)      | Generate videos with synchronized sound | Image / Image Pair | Video + Audio | **$0.40 / sec** |
| Veo 3.1 (Video only)         | Generate silent motion sequences        | Image / Image Pair | Video         | **$0.20 / sec** |

**Typical cost:** ~$3.20 for an 8-second 1080p video (standard mode).

---

## How to Use

1. **Upload your starting image**

   Use a clear, well-lit frame.

2. *(Optional)* **Add a last frame**

   Provide an ending image if you want a smooth transition.

3. **Write your prompt**

   Describe the motion or transformation (e.g., “camera slowly zooms out as night falls”).

4. **Set parameters**

   Choose duration (4s / 6s / 8s), resolution (720p / 1080p), and aspect ratio (16:9 or 9:16).

5. **Generate video**

   Submit your request — Veo 3.1 I2V will produce motion, lighting, and audio automatically.

---

## Pro Tips

* Use consistent framing between start and end images for smoother interpolation.

* Add camera verbs like *“pan,” “tilt,” “dolly,”* for cinematic control.

* Keep prompts concise and clear — focus on movement and lighting.

* For realistic transitions, limit drastic composition or color shifts between frames.

* To ensure repeatability, use the same random **seed** value.

---

## Notes & Limitations

* Supported durations: **4, 6, or 8 seconds**.

* Frame rate: **24 FPS** (fixed).

* Generation time: ~2–3 minutes for 8s @1080p.