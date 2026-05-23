# Wan 2.2: Open and Advanced Large-Scale Video Generative Model by Alibaba Wanxiang

## Model Card Overview

| Field | Description |
| :--- | :--- |
| **Model Name** | Wan 2.2  |
| **Release Date** | July 28, 2025 |
| **Model Type** | Video Generation |
| **Related Links** | **GitHub:** [https://github.com/Wan-Video/Wan2.2](https://github.com/Wan-Video/Wan2.2), **Hugging Face:** [https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B), **Paper (arXiv):** [https://arxiv.org/abs/2503.20314](https://arxiv.org/abs/2503.20314) |

## Introduction

Wan 2.2 is a significant upgrade to the Wan series of foundational video models, designed to push the boundaries of generative AI in video creation. The primary goal of Wan 2.2 is to provide an open and advanced suite of tools for generating high-quality, cinematic videos from various inputs, including text, images, and audio. Its core contribution lies in making state-of-the-art video generation technology accessible to a broader community of researchers and creators through open-sourcing its models and code. The project emphasizes cinematic aesthetics, complex motion generation, and computational efficiency, introducing several key innovations to achieve these aims.

## Key Features & Innovations

Wan 2.2 introduces several groundbreaking features that set it apart from previous models:

*   **Effective MoE Architecture:** Wan 2.2 is the first model to successfully integrate a Mixture-of-Experts (MoE) architecture into a video diffusion model. This design uses specialized expert models for different stages of the denoising process, which significantly increases the model's capacity without raising computational costs. The model has a total of 27B parameters, but only 14B are active during any given step.

*   **Cinematic-Level Aesthetics:** The model was trained on a meticulously curated dataset with detailed labels for cinematic properties like lighting, composition, and color tone. This allows users to generate videos with precise and controllable artistic styles, achieving a professional, cinematic look.

*   **Complex Motion Generation:** By training on a vastly expanded dataset (+65.6% more images and +83.2% more videos compared to Wan 2.1), Wan 2.2 demonstrates a superior ability to generate complex and realistic motion. It shows enhanced generalization across various motions, semantics, and aesthetics.

*   **Efficient High-Definition Video:** The suite includes a highly efficient 5B model (TI2V-5B) that utilizes an advanced VAE for high-compression video generation. It can produce 720p video at 24 fps and is capable of running on consumer-grade GPUs like the NVIDIA RTX 4090, making high-definition AI video generation more accessible.

## Model Architecture & Technical Details

The architecture of Wan 2.2 is built upon the Diffusion Transformer (DiT) paradigm and incorporates several key technical advancements.

### Core Architecture

The primary models in the Wan 2.2 suite, such as the T2V-A14B, employ a **Mixture-of-Experts (MoE)** architecture. This framework consists of two main expert models:

1.  **High-Noise Expert:** Activated during the initial stages of the denoising process, this expert focuses on establishing the overall structure and layout of the video.
2.  **Low-Noise Expert:** Activated in the later stages, this expert is responsible for refining the details, textures, and fine-grained motion of the video.

The transition between these experts is dynamically determined by the signal-to-noise ratio (SNR) during generation. This MoE design allows the model to have a large parameter count (27B total) while keeping the number of active parameters (14B) and computational load comparable to smaller models.

### Key Parameters & Variants

Wan 2.2 is offered in several variants, each tailored for different tasks and computational resources.

| Model Variant | Total Parameters | Key Feature | Supported Tasks |
| :--- | :--- | :--- | :--- |
| **T2V-A14B** | ~27B (14B active) | MoE for Text-to-Video | Text-to-Video |
| **I2V-A14B** | ~27B (14B active) | MoE for Image-to-Video | Image-to-Video |
| **TI2V-5B** | 5B | High-Compression VAE | Text-to-Video, Image-to-Video |
| **S2V-14B** | ~27B (14B active) | MoE for Speech-to-Video | Speech-to-Video |
| **Animate-14B** | ~27B (14B active) | MoE for Animation | Character Animation & Replacement |


## Intended Use & Applications

Wan 2.2 is designed for a wide range of creative and academic applications. Its various models support a comprehensive set of downstream tasks, making it a versatile tool for digital artists, filmmakers, researchers, and developers.

*   **Cinematic Video Production:** Generating high-fidelity video clips with specific artistic styles for short films, advertisements, or social media content.
*   **Storyboarding and Pre-visualization:** Quickly creating video mockups from text descriptions or still images to visualize scenes.
*   **Character Animation:** Animating static character images or replacing characters in existing videos with new ones while preserving motion and expression.
*   **Audio-Driven Content:** Producing videos that are synchronized with speech or other audio tracks, suitable for creating animated avatars or visualizing audio content.
*   **Academic Research:** Serving as a powerful, open-source foundation model for researchers exploring advancements in video generation, AI ethics, and multimodal AI.
*   **Creative Content Generation:** Enabling artists and creators to explore new forms of digital art and storytelling by combining text, images, and audio to produce unique video content.

