# Google Veo 3.1 Lite — Text-to-Video

**Veo 3.1 Lite Preview** ([`veo-3.1-lite-generate-preview`](https://ai.google.dev/gemini-api/docs/models/veo-3.1-lite-generate-preview)) is a high-efficiency, developer-oriented video model from Google. It targets **high-volume** applications with **strong price efficiency** while still delivering **high-fidelity** generation, editing, and cinematic control derived from the Veo 3.1 family. Outputs are **video with audio**. Per the [official model page](https://ai.google.dev/gemini-api/docs/models/veo-3.1-lite-generate-preview), **Veo 3.1 Lite Preview does not support 4K outputs or Extension**; see the broader [Video generation](https://ai.google.dev/gemini-api/docs/video) documentation for full platform capabilities.

---

## Overview

Generate videos using Google's **Veo 3.1 Lite** model.

A **lightweight, cost-effective** variant of Veo 3.1 that **always generates video with audio**.

---

## Prompting for best results

For best results, prompts should be **descriptive and clear**. Include:

- **Subject:** What you want in the video (object, person, animal, scenery)
- **Context:** The background / setting
- **Action:** What the subject is doing
- **Style:** Film style keywords (horror, noir, cartoon, etc.)
- **Camera motion (optional):** Aerial view, tracking shot, etc.
- **Composition (optional):** Wide shot, close-up, etc.
- **Ambiance (optional):** Color and lighting details

---

## Supported options

The model supports:

- **720p** or **1080p** resolution
- **4, 6, or 8** second duration (**1080p requires 8s**)
- **16:9** and **9:16** aspect ratios
- **Audio is always generated**
- **Safety filters** prevent generation of inappropriate content

---

## Reference

- [Veo 3.1 Lite Preview — Gemini API](https://ai.google.dev/gemini-api/docs/models/veo-3.1-lite-generate-preview)
