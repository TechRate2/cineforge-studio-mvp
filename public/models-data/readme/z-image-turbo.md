# Z-Image-Turbo — 6B-parameter, ultra-fast text-to-image
Z-Image-Turbo is a 6B-parameter text-to-image model from Tongyi-MAI, engineered for production workloads where latency and throughput really matter. It uses only 8 sampling steps to render a full image, achieving sub-second latency on data-center GPUs and running comfortably on many 16 GB VRAM consumer cards.
# Ultra-fast generation with production-ready quality

Where many diffusion models need dozens of steps, Z-Image-Turbo is aggressively optimised around an 8-step sampler. That keeps inference extremely fast while still delivering photorealistic images and reliable on-image text, making it a strong fit for interactive products, dashboards, and large-scale backends—not just offline batch jobs.

### Why it looks so good?
- Photorealistic output at speed Generates high-fidelity, realistic images that work for product photos, hero banners, and UI visuals without multi-second waits.
- Bilingual prompts and text Understands prompts in English and Chinese, and can render multilingual text directly in the image—helpful for cross-market campaigns, posters, and screenshots.
- Low-latency, low-step design Only 8 function evaluations per image deliver extremely low latency, ideal for chatbots, configuration tools, design assistants, and any “click → image” experience.
- Friendly VRAM footprint Runs well in 16 GB VRAM environments, reducing hardware costs and making local or edge deployments more realistic.
- Scales for bulk generation Its efficiency makes large jobs—catalogues, continuous feed images, or auto-generated thumbnails—practical without blowing up compute budgets.
- Reproducible generations A controllable seed parameter lets you recreate a previous image or generate small, controlled variations for brand safety and experimentation.


# How to use
- prompt – natural-language description of the scene, style, and any on-image text (English or Chinese).
- size (width / height) – choose the output resolution; supports square and rectangular images up to high resolutions (for example, 1536 × 1536).
- seed – set to -1 for random results, or use a fixed integer to make outputs reproducible.

# Pricing
Simple per-image billing:
- Without prompt rewriting (prompt_extend=false): $0.015 per generated image
- With prompt rewriting (prompt_extend=true): $0.03 per generated image

# Try more models and see their difference!
- Nano Banana Pro – Text-to-Image – Google’s Nano Banana Pro (Gemini 3.0 Pro Image family) delivers high-quality multi-image generation with extremely low cost per image, ideal for large-scale applications.
- Seedream V4 – Text-to-Image – ByteDance’s high-resolution text-to-image model with rich detail and diverse styles, well suited for creative illustration and commercial visuals.
- FLUX.2 [dev] – Text-to-Image – A lightweight FLUX.2-based base model hosted by AtlasCloud, optimised for efficient inference and LoRA-friendly training.

# Paper

[Tongyi-MAI/Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo?utm_source=chatgpt.com)