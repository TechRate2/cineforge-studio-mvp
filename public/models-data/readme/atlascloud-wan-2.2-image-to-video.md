# Wan 2.2: Open and Advanced Large-Scale Video Generative Model by Alibaba Wanxiang

## Model Card Overview

| Field | Description |
| :--- | :--- |
| **Model Name** | Wan 2.2 Image-to-Video |
| **Developed by** | Alibaba Tongyi Wanxiang Lab |
| **Model Type** | Image-to-Video Generation |
| **Resolution** | 480p, 720p (via VSR upscaling) |
| **Frame Rate** | 30 fps |
| **Duration** | 3–10 seconds |
| **Related Links** | **GitHub:** [https://github.com/Wan-Video/Wan2.2](https://github.com/Wan-Video/Wan2.2), **Hugging Face:** [https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B), **Paper (arXiv):** [https://arxiv.org/abs/2503.20314](https://arxiv.org/abs/2503.20314) |

## Introduction

Wan 2.2 is a significant upgrade to the Wan series of foundational video models, designed to push the boundaries of generative AI in video creation. This image-to-video variant takes a reference image as the first frame and generates a high-quality video that extends the scene with natural motion and cinematic aesthetics.

The model generates videos at 480p natively and supports 720p output via Video Super Resolution (VSR) upscaling, delivering smooth 30 fps playback at both resolutions.

## Key Features & Innovations

*   **Effective MoE Architecture:** Wan 2.2 integrates a Mixture-of-Experts (MoE) architecture into the video diffusion model. Specialized expert models handle different stages of the denoising process, increasing model capacity without raising computational costs. The model has 27B total parameters with only 14B active during any given step.

*   **Cinematic-Level Aesthetics:** Trained on a meticulously curated dataset with detailed labels for cinematic properties like lighting, composition, and color tone. This allows generation of videos with precise and controllable artistic styles, achieving a professional, cinematic look.

*   **Complex Motion Generation:** Trained on a vastly expanded dataset (+65.6% more images and +83.2% more videos compared to Wan 2.1), Wan 2.2 demonstrates superior ability to generate complex and realistic motion with enhanced generalization across motions, semantics, and aesthetics.

*   **VSR-Enhanced Output:** All output videos are delivered at 30 fps. When 720p resolution is selected, the model leverages Video Super Resolution to upscale from a 480p base generation, preserving fine details while achieving higher resolution output.

## Model Architecture

The architecture is built upon the Diffusion Transformer (DiT) paradigm with a **Mixture-of-Experts (MoE)** framework:

1.  **High-Noise Expert:** Activated during initial denoising stages, establishing overall structure and layout.
2.  **Low-Noise Expert:** Activated in later stages, refining details, textures, and fine-grained motion.

The transition between experts is dynamically determined by the signal-to-noise ratio (SNR) during generation.

## Intended Use & Applications

*   **Cinematic Video Production:** Generating high-fidelity video clips from reference images for short films, advertisements, or social media content.
*   **Storyboarding and Pre-visualization:** Quickly creating video mockups from still images to visualize scenes.
*   **Creative Content Generation:** Enabling artists and creators to animate still images into dynamic video content with natural motion.
*   **Academic Research:** Serving as a powerful foundation model for researchers exploring advancements in video generation and multimodal AI.
