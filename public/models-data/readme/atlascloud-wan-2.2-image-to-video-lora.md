# Wan 2.2: Open and Advanced Large-Scale Video Generative Model by Alibaba Wanxiang

## Model Card Overview

| Field | Description |
| :--- | :--- |
| **Model Name** | Wan 2.2 Image-to-Video LoRA |
| **Developed by** | Alibaba Tongyi Wanxiang Lab |
| **Model Type** | Image-to-Video Generation with LoRA Support |
| **Resolution** | 480p, 720p (via VSR upscaling) |
| **Frame Rate** | 30 fps |
| **Duration** | 3–10 seconds |
| **Related Links** | **GitHub:** [https://github.com/Wan-Video/Wan2.2](https://github.com/Wan-Video/Wan2.2), **Hugging Face:** [https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B), **Paper (arXiv):** [https://arxiv.org/abs/2503.20314](https://arxiv.org/abs/2503.20314) |

## Introduction

Wan 2.2 is a significant upgrade to the Wan series of foundational video models, designed to push the boundaries of generative AI in video creation. This image-to-video LoRA variant takes a reference image as the first frame and generates a high-quality video, with full support for custom LoRA weights to fine-tune the generation style, motion characteristics, or subject identity.

The model generates videos at 480p natively and supports 720p output via Video Super Resolution (VSR) upscaling, delivering smooth 30 fps playback at both resolutions.

## Key Features & Innovations

*   **Effective MoE Architecture:** Wan 2.2 integrates a Mixture-of-Experts (MoE) architecture into the video diffusion model. Specialized expert models handle different stages of the denoising process, increasing model capacity without raising computational costs. The model has 27B total parameters with only 14B active during any given step.

*   **Cinematic-Level Aesthetics:** Trained on a meticulously curated dataset with detailed labels for cinematic properties like lighting, composition, and color tone. This allows generation of videos with precise and controllable artistic styles, achieving a professional, cinematic look.

*   **Complex Motion Generation:** Trained on a vastly expanded dataset (+65.6% more images and +83.2% more videos compared to Wan 2.1), Wan 2.2 demonstrates superior ability to generate complex and realistic motion with enhanced generalization across motions, semantics, and aesthetics.

*   **Custom LoRA Support:** This variant supports user-provided LoRA weights for fine-grained style and motion control. Three separate LoRA input channels are available:
    *   `high_noise_loras` — Applied to the high-noise expert (transformer stage), influencing overall structure and layout.
    *   `low_noise_loras` — Applied to the low-noise expert (transformer_2 stage), influencing fine details and textures.
    *   `loras` — General-purpose LoRA input where the module is auto-inferred from the safetensors filename.

*   **VSR-Enhanced Output:** All output videos are delivered at 30 fps. When 720p resolution is selected, the model leverages Video Super Resolution to upscale from a 480p base generation, preserving fine details while achieving higher resolution output.

## Model Architecture

The architecture is built upon the Diffusion Transformer (DiT) paradigm with a **Mixture-of-Experts (MoE)** framework:

1.  **High-Noise Expert:** Activated during initial denoising stages, establishing overall structure and layout.
2.  **Low-Noise Expert:** Activated in later stages, refining details, textures, and fine-grained motion.

The transition between experts is dynamically determined by the signal-to-noise ratio (SNR) during generation. Custom LoRA weights can be applied to each expert independently, enabling precise control over different aspects of the generation pipeline.

## Intended Use & Applications

*   **Stylized Video Production:** Generating videos with custom visual styles by applying LoRA weights trained on specific aesthetic data.
*   **Character & Subject Consistency:** Using identity-preserving LoRAs to maintain consistent characters across multiple video generations.
*   **Cinematic Video Production:** Generating high-fidelity video clips from reference images for short films, advertisements, or social media content.
*   **Creative Experimentation:** Combining multiple LoRAs to explore novel visual effects and motion styles.
*   **Academic Research:** Serving as a powerful foundation model for researchers exploring LoRA-based fine-tuning techniques in video generation.
