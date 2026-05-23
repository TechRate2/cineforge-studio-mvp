## 1. Introduction

**Grok Imagine Image Quality** is xAI's flagship image generation and editing system, also known as "Quality Mode," designed to deliver photorealistic imagery, legible in-image typography, and tight prompt adherence across diverse visual styles. This README applies to the following API model identifiers:

- `xai/grok-imagine-image-quality/text-to-image`
- `xai/grok-imagine-image-quality/edit`

Developed by xAI and built on the Aurora foundation—an autoregressive Mixture-of-Experts (MoE) architecture that differentiates it from diffusion-based competitors—Grok Imagine Image Quality targets creators, developers, and enterprises who require high-fidelity static imagery alongside natural-language editing. The consumer version launched on April 3, 2026 via grok.com/imagine and the Grok iOS/Android apps, and the API became publicly available on May 6, 2026 through the [official announcement](https://x.ai/news/grok-imagine-quality-mode).

The system is exposed through two API variants that share the same underlying model but are optimized for distinct workflows. The `xai/grok-imagine-image-quality/text-to-image` endpoint produces images from text prompts with approximately 4-second latency, while `xai/grok-imagine-image-quality/edit` applies prompt-driven modifications to existing images—including multi-image reference composition—with approximately 13-second latency.

---

## 2. Key Features & Innovations

- **Aurora MoE Architecture**: Unlike most image generators that rely on diffusion, Grok Imagine Image Quality is powered by Aurora, an autoregressive Mixture-of-Experts model. This approach yields strong facial consistency, accurate textures, and cinematic lighting behavior that reviewers have compared favorably with diffusion competitors on photorealistic sharpness.

- **High-Fidelity Text Rendering**: The model produces legible in-image typography across multiple languages, addressing one of the historically weakest areas of generative image models. While Ideogram and GPT Image 2 still hold the lead in pure text rendering, Quality Mode closes the gap considerably versus prior Grok generations.

- **Prompt-Driven Editing Without Masks**: The `xai/grok-imagine-image-quality/edit` variant supports object addition, removal, swapping, style transfer, and multi-image reference composition entirely through natural-language prompts. No mask-based inpainting is required, and multi-turn iterative refinement is supported for progressive edits.

- **Multi-Resolution and Multi-Format Output**: Outputs are available at 1K (1024×1024) or 2K (2048×2048) resolution, across 13 aspect ratios ranging from 2:1 to 1:2. JPEG, PNG, and WebP formats are supported, with alpha channel available on PNG and WebP.

- **Batch Generation**: Both variants accept a `num_images` parameter (1–4) to generate multiple candidates per request, useful for creative exploration and A/B selection in production pipelines.

- **Broad Stylistic Range**: The model demonstrates competent prompt adherence across photorealistic, anime, oil painting, 3D-rendered, and abstract styles, making it suitable for varied creative and commercial briefs from a single endpoint.

- **Integrated Image-to-Video Pipeline**: Grok Imagine Image Quality feeds directly into xAI's image-to-video capabilities, which currently rank #1 on the Artificial Analysis Image-to-Video Arena (Elo 1,336) and Multi-Image-to-Video Arena (Elo 1,342).

---

## 3. Model Architecture & Technical Details

Grok Imagine Image Quality uses the **Aurora** architecture—an autoregressive Mixture-of-Experts design. Rather than iteratively denoising latent representations as diffusion models do, autoregressive image models generate tokens sequentially, which contributes to the system's strong consistency across faces, fine textures, and typography. The MoE routing allows expert specialization across visual domains (portraiture, text, lighting, stylization) while keeping inference latency competitive.

Both API identifiers (`xai/grok-imagine-image-quality/text-to-image` and `xai/grok-imagine-image-quality/edit`) are served by the same underlying weights; the distinction lies in the input schema and conditioning path. The editing variant accepts a `prompt` plus one or more `image_urls`, enabling single-image edits as well as multi-image composition in which reference imagery informs the generated output.

**API specifications:**

| Parameter | Text-to-Image | Edit |
|---|---|---|
| Required inputs | `prompt` | `prompt`, `image_urls` |
| `num_images` | 1–4 | 1–4 |
| `aspect_ratio` | 13 options (2:1 to 1:2) | Defaults to `auto` |
| `resolution` | 1k / 2k | 1k / 2k |
| Typical latency | ~4 s | ~13 s |

The model is positioned within xAI's tiered product line—**Speed → Quality → Pro**—where Quality Mode represents the balanced tier and Pro Mode adds 2K output with iterative editing workflows.

---

## 4. Performance Highlights

On the [Artificial Analysis Text-to-Image Arena](https://artificialanalysis.ai/image/models/grok-imagine-image), Grok Imagine Image Quality sits within the top five models but trails the current leaders. Its strongest competitive results come from the image-to-video pipeline it feeds, where xAI's system ranks first overall.

**Text-to-Image Arena (indicative rankings):**

| Rank | Model | Developer | Elo Score |
|---|---|---|---|
| 1 | GPT Image 2 | OpenAI | 1338 |
| 2 | GPT Image 1.5 | OpenAI | 1273 |
| 3 | Nano Banana Pro | Google | 1219 |
| Top 5 | **Grok Imagine Image Quality** | **xAI** | **Top-5 tier** |

**Image-to-Video / Multi-Image-to-Video Arena (pipeline context):**

| Arena | Rank | Elo |
|---|---|---|
| Image-to-Video | #1 | 1,336 |
| Multi-Image-to-Video | #1 | 1,342 |

**Qualitative strengths:**

- Photoreal sharpness rated above Nano Banana by independent reviewers
- Strong facial consistency and cinematic lighting
- Competitive price-performance and fast inference
- Permissive content handling with an integrated video pipeline

**Known limitations:**

- In-image text rendering trails Ideogram, GPT Image 2, and FLUX
- Editing fidelity trails GPT Image 1.5 on complex structural edits
- Artistic stylization trails Midjourney V7 on illustrative aesthetics
- Moderation behavior has been reported as inconsistent by some users

---

## 5. Intended Use & Applications

- **Portrait and Character Art**: The Aurora architecture's facial consistency and texture accuracy make `xai/grok-imagine-image-quality/text-to-image` well suited for portrait generation, concept characters, and hero imagery where identity fidelity matters.

- **Product and Commercial Marketing**: Produce product advertisements, UGC-style marketing visuals, and product-film mockups at 2K resolution with cinematic lighting. The fast inference and per-image pricing support high-volume creative iteration.

- **Prompt-Driven Image Editing**: Use `xai/grok-imagine-image-quality/edit` for object addition, removal, swapping, and style transfer without requiring masks. Multi-turn refinement supports iterative polish workflows typical of design review cycles.

- **Multi-Image Composition**: The editing variant accepts multiple reference images, enabling workflows such as combining a subject with a new background, transferring wardrobe across references, or blending compositional cues from several inputs.

- **Social and Short-Form Content**: Generate social-first imagery and stills that feed into the Grok Imagine image-to-video pipeline—currently ranked #1 on Artificial Analysis's video arenas—for an end-to-end static-to-motion workflow.

- **Concept Art and Creative Exploration**: With batch sizes up to four images and broad stylistic range across photorealistic, anime, oil painting, 3D, and abstract styles, the model serves concept artists and creative directors exploring visual directions quickly.

- **Enterprise Creative Agencies and Media**: The combination of 2K output, permissive content policy, and integrated video pipeline positions Grok Imagine Image Quality for creative agencies, entertainment and media production, and social-first consumer brands.