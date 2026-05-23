# Wan 2.2 Turbo Spicy Infinite Image-to-Video

## Model Overview

| Field | Description |
| :--- | :--- |
| **Model Name** | `atlascloud/wan-2.2-turbo-spicy/infinite-image-to-video` |
| **Model Type** | Advanced Image-to-Video Generation |
| **Core Architecture** | Mixture-of-Experts (MoE) |
| **Active Parameters** | 14B |
| **Variant** | Base |
| **Tuning** | Spicy-tuned post-processing pipeline (adult-oriented) |

**Wan 2.2 Turbo Spicy Infinite Image-to-Video** is an enhanced image-to-video model built on the Wan 2.2 foundation. Inheriting the **Mixture-of-Experts (MoE)** architecture and cinematic-level aesthetics of the original Wan series, this variant introduces two breakthroughs — **inference acceleration** and **infinite-length generation** — and ships with a spicy-tuned post-processing pipeline for adult-oriented creative work.


---

## Key Features & Innovations

### 1. Ultra-Fast Inference: 4-Step Distillation with RCM
To address the high latency typical of large-scale models, we apply specialized sampling optimization and knowledge distillation:

* **RCM (Refined Consistency Model) Sampler** — a more efficient ODE solver that significantly improves single-step sampling quality.
* **4-Step Distillation** — denoising steps are compressed to **4 steps** through multi-stage distillation, enabling cinematic-grade generation at a fraction of the original cost and unlocking low-latency interaction.

### 2. Infinite-Length Generation: Anchor-Frame Autoregressive Architecture
A targeted retraining gives the model an advanced temporal extension mechanism that breaks the duration limits of traditional video models:

* **Anchor-Frame Evolution** — automatically extracts key "anchor frames" during generation as global temporal references.
* **Dual-Frame Constraint (Anchor + Last Frame)** — combines the structural consistency of the global anchor frame with the motion continuity of the previous frame to construct video sequences autoregressively.
* **Semantic Stability** — subject identity, scene details, and lighting stay consistent across multi-minute outputs, suppressing semantic drift and logical collapse.

### 3. Cinematic-Level Aesthetics (Inherited)
The model retains the curated training foundation of Wan 2.2:

* **Precise Control** — detailed labels for lighting, composition, and color tone.
* **Complex Motion** — superior generation of realistic, fluid motion across diverse semantics.

---

## Why Infinite?

Most image-to-video models lock you into a single short clip (5–10 s). **`Infinite` extends that into a controlled multi-segment clip** — output duration equals `prompt_count × duration_per_segment`, up to 6 prompts x 5 s. Direct each segment with its own prompt; the API returns one server-stitched 30 fps MP4.

| Prompts | Per-segment | Total output |
| --- | --- | --- |
| 1 | 5 s | 5 s |
| 3 | 5 s | 15 s |
| 6 | 5 s | 30 s |

---

## 60-second Quickstart

```bash
curl -X POST https://api.atlascloud.ai/api/v1/model/generateVideo \
  -H "Authorization: Bearer $APIKEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "atlascloud/wan-2.2-turbo-spicy/infinite-image-to-video",
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

## Base vs LoRA — which one?

| | **Base** (this model) | **LoRA** variant |
| --- | --- | --- |
| Model name | `atlascloud/wan-2.2-turbo-spicy/infinite-image-to-video` | `…/infinite-image-to-video-lora` |
| Price (480 p, per second) | **$0.020** | $0.026 (+30 %) |
| Best for | Standard runs, fast iteration, bulk drafts | Higher fidelity, fine-grained control |
| Recommended for | Pre-production, A/B prompts | Final renders |

> Switch the variant by changing `model` only — all other fields are identical.

---

## Request Fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `model` | string | ✅ | `atlascloud/wan-2.2-turbo-spicy/infinite-image-to-video` |
| `image` | string (URL) | ✅ | Source frame; jpg/png |
| `prompt` | string\[\] | ✅ | **Must be a JSON array.** Plain string is rejected. |
| `duration` | number | ✅ | Fixed at 5 s per segment. |
| `resolution` | string | optional | `480p`, `720p`, or `1080p`. Defaults to `720p`. |
| `seed` | number | optional | `-1` for random |

---

## Pricing — at a glance

```text
price = $0.020 × max(1, prompt_count) × max(5, duration_seconds) × resolution_factor
                                                                     480p → 1
                                                                     720p → 2
                                                                     1080p → 3
```

Common combos:

| Prompts | Duration | Resolution | Total |
| --- | --- | --- | --- |
| 1 | 5 s | 480 p | $0.10 |
| 1 | 5 s | 720 p | $0.20 |
| 1 | 5 s | 1080 p | $0.30 |
| 3 | 5 s | 720 p | **$0.60** |
| 6 | 5 s | 720 p | $1.20 |
| 6 | 5 s | 1080 p | $1.80 |

---

## Output Spec

* Format: MP4 (H.264)
* Frame rate: **30 fps** (post-processed)
* Resolution: 480 p / 720 p / 1080 p tiers, aspect-ratio preserving
* Audio: none

---

## Intended Use & Applications

* **Cinematic Long-Take Production** — high-fidelity, consistent long-duration shots without manual stitching.
* **Low-Latency Interactive Content** — leverage 4-step distillation for live broadcasts and AI-driven interactive installations.
* **Advanced Image-to-Video (I2V)** — transform a static image into infinite, naturally moving visual scrolls via anchor-frame technology.
* **Professional Pre-visualization** — minutes-long dynamic storyboards that compress pre-production time.

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
* While anchor-frame technology suppresses cross-segment drift, it does not fully eliminate it — long prompts sharing fine identity details across many segments may still show minor variation.
* 480 p generates ~2× faster than 720 p; use 480 p for drafts.

---

## Related

* LoRA variant: `atlascloud/wan-2.2-turbo-spicy/infinite-image-to-video-lora`
* Non-spicy alias: `atlascloud/wan-2.2-turbo/infinite-image-to-video`

---

*Note: This model is designed to empower the creative community. Users are expected to follow AI ethical guidelines and copyright regulations.*
