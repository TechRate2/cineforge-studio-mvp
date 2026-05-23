# Qwen Image 2.0 Text-to-Image

Qwen Image 2.0 is Alibaba's advanced text-to-image model that generates high-quality images from detailed text descriptions. With exceptional prompt following, flexible aspect ratios, and custom resolution support, it excels at rendering complex scenes with fine details like hair, accessories, and textures.

---

## Why Choose This?

- **Strong prompt adherence**  
  Excels at following detailed, complex prompts with multiple elements and attributes.

- **Fine detail rendering**  
  Excellent at rendering intricate details like hair textures, jewelry, and clothing accessories.

- **Flexible aspect ratios**  
  Multiple presets including `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, and `2:3`.

- **Custom resolution**  
  Adjustable width and height from `512` to `2048` pixels.

- **Prompt Enhancer**  
  Built-in tool to automatically improve your descriptions.

---

## Parameters

| Parameter | Required | Description |
|----------|----------|-------------|
| prompt   | Yes      | Text description of the desired image |
| size     | No       | Aspect ratio preset: 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3 |
| width    | No       | Custom width in pixels (range: 512–2048) |
| height   | No       | Custom height in pixels (range: 512–2048) |
| seed     | No       | Random seed for reproducibility (-1 for random) |

---

## How to Use

1. **Write your prompt**  
   Describe the image in detail, including specific attributes, styles, and elements.

2. **Choose size**  
   Select a preset aspect ratio or customize width/height.

3. **Use Prompt Enhancer (optional)**  
   Click to automatically refine your description.

4. **Set seed (optional)**  
   Use a seed for reproducible results.

5. **Run**  
   Submit and download your generated image.

---

## Best Use Cases

- **Detailed Character Art** — Generate characters with specific attributes like hair styles, clothing, and accessories  
- **Portrait Photography** — Create photorealistic portraits with fine details  
- **Fashion & Style** — Visualize outfits, hairstyles, and jewelry with precision  
- **Concept Art** — Render complex scenes with multiple elements  
- **Cultural & Artistic** — Generate images with specific cultural elements and decorations  

---

## Pro Tips

- Use **highly detailed prompts** — the model excels at following complex descriptions with multiple attributes  
- Describe specific details like *"waist-length loc'd hair," "gold thread," "cowrie shells," or "blue beads"* for precise rendering  
- Include **motion and pose descriptions** for dynamic images (e.g., *"caught mid-spin in a dance"*)  
- Match aspect ratio to your content:  
  - `1:1` for portraits  
  - `16:9` for landscapes  
  - `9:16` for full-body shots  
- Use the same **seed** to reproduce or iterate on specific results  

---

## Notes

- `prompt` is the only required field  
- Resolution range: **512–2048 pixels** for both width and height  
- Default size is **1:1**  
- Ensure your prompts comply with content guidelines  

---

## Related Models

- Qwen Image 2.0 Pro Text-to-Image — Pro tier with enhanced quality  
- Qwen Image Edit Plus — Image editing with text instructions  
- Seedream V5.0 Lite — ByteDance's lightweight text-to-image model  