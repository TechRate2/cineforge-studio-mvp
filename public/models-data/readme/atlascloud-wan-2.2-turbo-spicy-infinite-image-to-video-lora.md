# Wan 2.2 Turbo Spicy Infinite Image-to-Video — LoRA

## Model Overview

| Field | Description |
| :--- | :--- |
| **Model Name** | `atlascloud/wan-2.2-turbo-spicy/infinite-image-to-video-lora` |
| **Model Type** | Advanced Image-to-Video Generation |
| **Core Architecture** | Mixture-of-Experts (MoE) |
| **Active Parameters** | 14B + LoRA adapter |
| **Variant** | LoRA |
| **Tuning** | Spicy-tuned post-processing pipeline (adult-oriented) |

The **LoRA variant** of Wan 2.2 Turbo Spicy Infinite Image-to-Video. Same `Infinite` segmented-prompt mechanic and acceleration stack as the base model, with **LoRA-grade fidelity and motion stability** for final renders. Built on the Wan 2.2 **Mixture-of-Experts (MoE)** foundation with a spicy-tuned post-processing pipeline for adult-oriented creative work.


---

## Key Features & Innovations

### 1. Ultra-Fast Inference: 4-Step Distillation with RCM
* **RCM (Refined Consistency Model) Sampler** — efficient ODE solver that improves single-step sampling quality.
* **4-Step Distillation** — denoising compressed to **4 steps**, enabling cinematic-grade generation at low latency. LoRA inference is ~10–20 % slower than base but stays well within interactive territory.

### 2. Infinite-Length Generation: Anchor-Frame Autoregressive Architecture
* **Anchor-Frame Evolution** — automatically extracts key "anchor frames" during generation as global temporal references.
* **Dual-Frame Constraint (Anchor + Last Frame)** — combines global structural consistency with motion continuity to construct video sequences autoregressively.
* **Semantic Stability** — LoRA further sharpens identity and detail consistency across multi-minute outputs.

### 3. Cinematic-Level Aesthetics (Inherited + LoRA-Enhanced)
* **Precise Control** — detailed labels for lighting, composition, color tone.
* **Complex Motion** — fluid motion across diverse semantics.
* **Fine-Grained Fidelity** — LoRA adapter delivers sharper textures, more stable identities, and stylistic depth that the base variant cannot match on its own.

---

## Why Infinite?

Output duration equals `prompt_count × duration_per_segment`, up to 6 prompts x 5 s. Direct each segment with its own prompt; the API returns one server-stitched 30 fps MP4.

| Prompts | Per-segment | Total output |
| --- | --- | --- |
| 1 | 5 s | 5 s |
| 3 | 5 s | 15 s |
| 6 | 5 s | 30 s |

---

## When to Pick the LoRA Variant

* **Final renders**, not drafts — the quality margin is worth the +30 % price.
* Subjects with **fine identity details** that must stay consistent across segments.
* Stylized motion or lighting that the base model under-delivers on.

For early iteration / bulk drafts, use the base:
`atlascloud/wan-2.2-turbo-spicy/infinite-image-to-video` (cheaper, faster).

---

## 60-second Quickstart

```bash
curl -X POST https://api.atlascloud.ai/api/v1/model/generateVideo \
  -H "Authorization: Bearer $APIKEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "atlascloud/wan-2.2-turbo-spicy/infinite-image-to-video-lora",
    "image": "https://static.atlascloud.ai/media/images/db548fe3bd5cafa4ef7e0141d69c8566.jpeg",
    "prompt": [
      "She turns slowly toward the camera, golden hour light hitting her face.",
      "She walks forward through the wheat field, hand brushing the tops.",
      "Close-up: a single tear catches the sun as she smiles."
    ],
    "duration": 5,
    "resolution": "720p"
  }'
```

Returns one MP4 — segments are stitched server-side at 30 fps.

---

## Request Fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `model` | string | ✅ | `atlascloud/wan-2.2-turbo-spicy/infinite-image-to-video-lora` |
| `image` | string (URL) | ✅ | Source frame; jpg/png |
| `prompt` | string\[\] | ✅ | **Must be a JSON array.** Plain string is rejected. |
| `duration` | number | ✅ | Fixed at 5 s per segment. |
| `resolution` | string | optional | `480p`, `720p`, or `1080p`. Defaults to `720p`. |
| `seed` | number | optional | `-1` for random |

---

## Pricing — at a glance

```text
price = $0.026 × max(1, prompt_count) × max(5, duration_seconds) × resolution_factor
                                                                     480p → 1
                                                                     720p → 2
                                                                     1080p → 3
```

Common combos:

| Prompts | Duration | Resolution | Total |
| --- | --- | --- | --- |
| 1 | 5 s | 480 p | $0.13 |
| 1 | 5 s | 720 p | $0.26 |
| 1 | 5 s | 1080 p | $0.39 |
| 3 | 5 s | 720 p | **$0.78** |
| 6 | 5 s | 720 p | $1.56 |
| 6 | 5 s | 1080 p | $2.34 |

---

## Output Spec

* Format: MP4 (H.264)
* Frame rate: **30 fps** (post-processed)
* Resolution: 480 p / 720 p / 1080 p tiers, aspect-ratio preserving
* Audio: none

---

## Intended Use & Applications

* **Final cinematic renders** with cross-segment identity stability.
* **High-fidelity advertising / pre-visualization** that depend on stylistic consistency.
* **Identity-critical I2V** where minor drift would break the narrative.

---

## Content Policy

This model is tuned for **adult-oriented (NSFW)** generation. By calling it you confirm:

* All depicted subjects are **18 +**.
* You hold the rights to the source image.
* You will not generate content depicting real, identifiable people without their explicit consent.

Violations may result in account suspension.

---

## Limitations

* `prompt` must be a JSON array, never a plain string.
* LoRA reduces but does not eliminate cross-segment identity drift.
* LoRA generation is ~10–20 % slower per segment than base.

---

## Related

* Base variant: `atlascloud/wan-2.2-turbo-spicy/infinite-image-to-video`
* Non-spicy LoRA alias: `atlascloud/wan-2.2-turbo/infinite-image-to-video-lora`

---

*Note: This model is designed to empower the creative community. Users are expected to follow AI ethical guidelines and copyright regulations.*
