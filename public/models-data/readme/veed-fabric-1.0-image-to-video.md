# VEED Fabric 1.0 Image-to-Video

**VEED Fabric 1.0** is a high-speed image-to-video generation model powered by VEED's Fabric technology. It transforms a single still image into a fluid, realistic video clip — optionally driven by an audio track — making it ideal for rapid creative production and prototyping.

## 🌟 Key Features

### ⚡ Generation
Optimized for speed without sacrificing visual quality, delivering results significantly faster than standard-quality pipelines.

### 🖼 Image-to-Video
Animates any still image into a smooth video sequence, preserving the original composition, lighting, and subject identity.

### 🎵 Audio-Driven Animation
Accepts an audio track as a generation driver, enabling lip sync, rhythm-matched motion, or ambient scene animation guided by sound.

### 🎬 Flexible Resolution
Supports 480p for lightweight, cost-efficient output and 720p for higher-fidelity delivery — choose based on your quality and budget requirements.

### 💰 Efficient and Accessible
Per-second billing based on output video duration, so you only pay for what you generate.

## ⚙️ Parameters

| Parameter | Required | Description |
|---|---|---|
| `image_url`* | ✅ | First frame of the video. Accepts a public URL or Base64-encoded image. Supported formats: `png`, `jpeg`, `jpg`, `webp`. The start/end frame aspect ratio must be in the range `0.8–1.25`. Request body must not exceed 20 MB. |
| `audio_url`* | ✅ | Audio URL to drive the video generation. Duration must be between 1–300 seconds. |
| `resolution`* | ✅ | Output resolution: `480p` or `720p`. Default: `720p`. |

## 💲 Pricing

| Resolution | Unit Price |
|---|---|
| 480p | $0.088 / second |
| 720p | $0.165 / second |

Billing is based on the duration of the audio input (1–300 seconds).

## 💡 Example Prompt

> A confident professional walking into a bright modern office, animated from a portrait photo, synchronized to an upbeat background music track.

## 🎯 Use Cases

- **Social Media Content** — Animate product photos or portraits into short-form video clips for platforms like TikTok or Instagram.
- **Lip Sync & Talking Heads** — Drive a face image with a speech audio track to produce realistic talking-head videos.
- **Marketing & Advertising** — Quickly turn static campaign visuals into dynamic video ads.
- **Creative Prototyping** — Rapidly iterate on video concepts from storyboard illustrations or reference images.
- **Music Visualization** — Pair ambient or artistic images with music to produce mood-driven visual content.
