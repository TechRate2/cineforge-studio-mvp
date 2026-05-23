# Alibaba Qwen-Image Edit

An advanced image editing model from Alibaba Cloud, offering precise control and high-quality results. Qwen-Image Edit is designed to handle common editing tasks, allowing users to modify images with natural language prompts. It supports single-image editing and multi-image blending.

## Overview
- **Purpose:** Perform image edits using text instructions.
- **Core Capability:** Supports single-image editing and multi-image blending.
- **Foundation:** Powered by Alibaba's advanced multi-modal generative AI technology.
- **Typical Output:** High-quality edited image (1 per request) that blends changes with the original content.
- **Use Cases:** Social media content adjustment, basic photo retouching, and creative experimentation.

## Key Features

- **Multi-image Blending:**
    - Example: Combine a girl from Image 1, wearing a skirt from Image 2, sitting in a pose from Image 3.
    - Example: Combine a girl from Image 1, a necklace from Image 2, and a bag from Image 3.
- **Single-image Editing:**
    - Generate depth-compliant images.
    - Replace text (e.g., "HEALTH INSURANCE" -> "明天会更好").
    - Replace shirt color.
    - Change background (e.g., to Antarctica).
- **High Fidelity:** Preserves the quality of the original image while applying edits.
- **Smart Inpainting:** Fills gaps or replaces objects based on the surrounding context.

## Designed For

- **Content Creators:** Quickly adjust visuals for social platforms.
- **General Users:** Easily modify personal photos or creative projects.
- **Developers:** Integrate image editing capabilities into applications.

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

### Parameters
- **n:** Number of output images. Fixed at 1.
- **negative_prompt:** Description of content to exclude (max 500 characters).
- **size:** Not customizable. Output resolution maintains the aspect ratio of the input (or last input image), typically around 1024x1024.
- **watermark:** Boolean to add "Qwen-Image" watermark. Default is false.
- **seed:** Integer for reproducibility.

## Pricing

- **Billing Logic:** Pay-as-you-go based on the number of successful output images.
- **Tier:** Standard tier offering a balance of performance and cost.

## Limitations & FAQ

- **Conversation:** Does not support multi-turn conversation (single turn only).
- **Languages:** Chinese and English are supported; other languages are unverified.
- **Aspect Ratio:** Output follows the aspect ratio of the input image (or the last image if multiple are provided).
- **Resolution:** Does not support custom output resolution.
- **Output Quantity:** Only supports generating 1 image per request.

## Version

- **Model:** Alibaba Qwen-Image Edit
- **Family:** Qwen-Image
- **Technical Context:** Standard version with essential editing capabilities.