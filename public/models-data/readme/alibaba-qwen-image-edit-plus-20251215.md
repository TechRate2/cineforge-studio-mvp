# Alibaba Qwen-Image Edit Plus (20251215)

An advanced image editing model from Alibaba Cloud, offering precise control and high-quality results. This is a specific snapshot version of the Qwen-Image Edit Plus model, designed to handle complex editing tasks with consistent performance. It supports multi-image input and output, enabling complex tasks such as precise text modification, object addition/deletion/movement, action change, style transfer, and detail enhancement.

## Overview
- **Purpose:** Perform precise image edits using text instructions.
- **Core Capability:** Supports single-image editing and multi-image blending.
- **Foundation:** Powered by Alibaba's advanced multi-modal generative AI technology.
- **Typical Output:** High-quality edited images (1-6 per request) that seamlessly blend changes with the original content.
- **Use Cases:** E-commerce product photography, professional photo retouching, creative design adjustments, and marketing asset generation.

## Key Features

- **Multi-image Blending:**
    - Example: Combine a girl from Image 1, wearing a skirt from Image 2, sitting in a pose from Image 3.
    - Example: Combine a girl from Image 1, a necklace from Image 2, and a bag from Image 3.
- **Single-image Editing:**
    - Generate depth-compliant images.
    - Replace text (e.g., "HEALTH INSURANCE" -> "明天会更好").
    - Replace shirt color.
    - Change background (e.g., to Antarctica).
- **High Fidelity:** Preserves the quality, lighting, and texture of the original image while applying edits.
- **Precise Editing:** Capable of modifying text within images, adding/deleting/moving objects, changing subject actions, transferring styles, and enhancing details.
- **Custom Resolution:** Supports specifying output image resolution (512-2048px).
- **Prompt Optimization:** Supports intelligent prompt rewriting (`prompt_extend`) for better results.

## Designed For

- **Designers:** Quickly iterate on visual concepts and make adjustments.
- **Photographers:** Streamline retouching workflows.
- **E-commerce Merchants:** Modify product images for different contexts or variations.
- **Developers:** Build powerful image editing applications.

## Input Requirements

To achieve the best results, follow these guidelines:

### Inputs
- **Structure:**
    - `messages` array with `role: user`.
    - `content` array: 1-3 images (`{"image": "..."}`) + 1 text instruction (`{"text": "..."}`).
- **Image Format:** JPG, JPEG, PNG, BMP, TIFF, WEBP, GIF (first frame).
- **Resolution:** Recommended 384px - 3072px.
- **Size Limit:** Max 10MB per image.
- **Text Limit:** Max 800 characters.

## Pricing

- **Billing Logic:** Pay-as-you-go based on the number of successful output images.
- **Tier:** "Plus" tier offers enhanced capabilities and higher precision compared to the standard version.

## How to Use

1.  **Prepare Inputs:** Collect 1-3 reference images and define your text instruction.
2.  **Configure Parameters:** Set output count (`n`), resolution (`size`), and other options.
3.  **Call API:** Submit the request with the `messages` structure containing images and text.
4.  **Review:** Receive 1-6 edited images based on your specifications.

## Limitations & FAQ

- **Conversation:** Does not support multi-turn conversation (single turn only).
- **Languages:** Chinese and English are supported; other languages are unverified.
- **Aspect Ratio:** Output follows the aspect ratio of the input image (or the last image if multiple are provided).

## Version

- **Model:** Alibaba Qwen-Image Edit Plus (20251215)
- **Family:** Qwen-Image
- **Technical Context:** A specific snapshot version of the Plus model.