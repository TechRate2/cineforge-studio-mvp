# Nano Banana Pro : A state-of-the-art, multimodal reasoning and image generation model by Google DeepMind


## Model Card Overview

| Field | Description |
| :--- | :--- |
| **Model Name** | Nano Banana Pro (also known as Gemini 3 Pro Image) |
| **Developer** | Google DeepMind  |
| **Release Date** | November 20, 2025 |
| **Model Type** | Multimodal Reasoning and Image Generation|
| **Related Links** |  [Official Product Page](https://deepmind.google/models/gemini-image/pro/), [Model Card (PDF)](https://storage.googleapis.com/deepmind-media/Model-Cards/Gemini-3-Pro-Image-Model-Card.pdf)  |

## Introduction

Nano Banana Pro, officially designated as Gemini 3 Pro Image, represents the next generation in Google's series of highly-capable, natively multimodal models. It is designed for professional asset production, integrating the advanced reasoning capabilities of the Gemini 3 Pro foundation model with a sophisticated image generation engine. The primary goal of Nano Banana Pro is to provide users with studio-quality precision and control, enabling the creation of complex, high-fidelity visuals from textual and image-based prompts. Its core contribution lies in its ability to understand and execute intricate instructions, maintain character and scene consistency, and render legible text directly within generated images, setting a new standard for professional creative workflows. 

## Key Features & Innovations

Nano Banana Pro introduces several technical breakthroughs that distinguish it from prior models:

*   **Superior Text Rendering**: The model excels at generating images that contain clear, accurate, and stylistically coherent text, making it ideal for creating posters, diagrams, and marketing materials.
*   **Advanced Creative Controls**: Users can exercise fine-grained control over image outputs, including camera angles, lighting transformations (e.g., day to night), color grading, depth of field, and localized editing.
*   **High-Fidelity Consistency**: It can maintain the consistency of up to 14 input images and blend up to 5 distinct characters seamlessly into complex compositions, ensuring visual coherence across a series of generated images.
*   **Deep Real-World Knowledge**: Built on Gemini 3 Pro, the model leverages a vast understanding of the world to generate contextually rich and factually grounded visuals, from detailed infographics to historically accurate scenes.
*   **Multilingual Capabilities**: The model can accurately render and translate text across multiple languages within an image, facilitating the localization of visual content.
*   **Complex Composition from Multiple Inputs**: Nano Banana Pro can synthesize elements from multiple source images and text prompts to create a single, cohesive scene, enabling complex creative concepts.

## Model Architecture & Technical Details

Nano Banana Pro's architecture is fundamentally based on the Gemini 3 Pro model. While specific architectural details are not fully disclosed, the following technical information is available:

*   **Foundation Model**: Gemini 3 Pro
*   **Inputs**: The model accepts text strings and images as input, with a large context window of up to 1 million tokens.
*   **Outputs**: It generates high-resolution images (up to 4K) with a 64K token output capacity for handling complex generation tasks.
*   **Training Infrastructure**:
    *   **Hardware**: The model was trained on Google's custom-designed Tensor Processing Units (TPUs), which are optimized for large-scale machine learning computations and high-bandwidth memory access.
    *   **Software**: The training process utilized JAX and ML Pathways, Google's high-performance frameworks for machine learning research.
*   **Knowledge Cutoff**: The model's internal knowledge base has a cutoff date of January 2025.

## Intended Use & Applications

Nano Banana Pro is intended for professional and creative applications that require a high degree of precision, control, and visual fidelity. It is well-suited for a variety of downstream tasks and application scenarios:

*   **Professional Content Creation**: Generating production-ready assets for marketing campaigns, advertising, and branding.
*   **Design and Prototyping**: Creating detailed product mockups, storyboards for film and animation, and architectural visualizations.
*   **Informational Graphics**: Designing complex and accurate infographics, educational diagrams, and data visualizations.
*   **Artistic and Creative Expression**: Enabling artists and designers to explore novel visual styles and create complex, multi-element compositions.

## Performance

Nano Banana Pro's performance has been evaluated through extensive human evaluations and benchmarked against other leading image generation models. The results, measured in Elo scores, demonstrate its strong capabilities across a wide range of tasks.

A technical report also notes a performance dichotomy: while the model produces subjectively superior visual quality by hallucinating plausible details, it can lag behind specialist models in traditional quantitative metrics due to the stochastic nature of generative models.

### Existing Capabilities (Elo Score Comparison)

| Capability | **Gemini 3 Pro Image** | Gemini 2.5 Flash Image | GPT-Image 1 | Seedream v4 4k | Flux Pro Kontext Max |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Text Rendering | **1198 ± 18** | 997 ± 10 | 1150 ± 14 | 1019 ± 13 | 854 ± 13 |
| Stylization | **1098 ± 11** | 933 ± 7 | 1069 ± 9 | 991 ± 9 | 908 ± 11 |
| Multi-Turn | **1186 ± 19** | 1045 ± 24 | 1079 ± 32 | 990 ± 32 | 889 ± 37 |
| General Image Editing | **1127 ± 13** | 996 ± 8 | 1011 ± 13 | 965 ± 12 | 902 ± 13 |
| Character Editing | **1176 ± 16** | 1075 ± 8 | 1016 ± 10 | 889 ± 10 | 843 ± 10 |
| Object/Env. Editing | **1102 ± 19** | 1025 ± 9 | 930 ± 12 | 983 ± 13 | 961 ± 10 |
| General Text-to-Image | **1094 ± 16** | 1037 ± 8 | 1025 ± 9 | 1011 ± 9 | 907 ± 9 |

### New Capabilities (Elo Score Comparison)

| Capability | **Gemini 3 Pro Image** | Gemini 2.5 Flash Image | GPT-Image 1 | Seedream v4 4k | Flux Pro Kontext Max |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Multi-character Editing | **1213 ± 16** | 950 ± 10 | 997 ± 13 | 840 ± 19 | - |
| Chart Editing | **1209 ± 18** | 971 ± 10 | 994 ± 16 | 934 ± 16 | 893 ± 15 |
| Text Editing | **1202 ± 23** | 1001 ± 10 | 996 ± 14 | 860 ± 15 | 943 ± 12 |
| Factuality - Edu | **1169 ± 25** | 1050 ± 11 | 1084 ± 25 | 969 ± 22 | 884 ± 26 |
| Infographics | **1268 ± 17** | 1162 ± 11 | 1087 ± 12 | 1049 ± 12 | 824 ± 15 |
| Visual Design | **1104 ± 16** | 1083 ± 7 | 1028 ± 11 | 1038 ± 12 | 907 ± 11 |

