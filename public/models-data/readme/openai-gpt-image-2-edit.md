# OpenAI GPT Image 2 Edit

**GPT Image 2 Edit** is a cost-efficient image editing model powered by OpenAI's GPT image technology. It enables users to refine, modify, or transform existing images using natural language instructions, while maintaining the original style, composition, and visual integrity.

## 🌟 Key Features

### 🧠 Strong Visual Understanding
Understands complex textual instructions and applies targeted edits that match intent and context.

### 🎨 Intelligent Image Editing
Add, remove, or modify elements in an image with precision — from subtle adjustments to full stylistic transformations.

### 🖼 Multi-Image Support
Accepts one or more image inputs to guide the edit or style reference process.

### 💡 Context-Aware Refinement
Preserves the key artistic or photographic features, such as lighting, tone, and pose, while applying changes only where needed.

### 💰 Efficient and Accessible
Professional-quality visual editing at low cost, ideal for rapid prototyping, design iteration, or creative workflows.

## ⚙️ Parameters

| Parameter | Description |
|---|---|
| `prompt`* | Describe how you want to edit or modify the image (e.g. "change outfit colors to pastel tones, add neon city lights in the background") |
| `images`* | Upload one or more reference images (`JPG` / `PNG`) to be edited or used as visual input |
| `quality` | Output quality tier: `low`, `medium`, or `high` |
| `size` | Output size: `1024×1024`, `1024×1536`, or `1536×1024` |

## 💳 Pricing

Billing is token-based. The total cost per image is:

**Total = (Input cost + Output cost) × n**

### Output tokens
Calculated from the requested output `size` and `quality`:

```
tokens = ceil( base × round(base × short_side / long_side) × (2,000,000 + W×H) / 4,000,000 )
```

**Output cost = output\_tokens × $0.00003**

### Input tokens
Calculated from the actual pixel dimensions of the uploaded input image (probed automatically):

**Input cost = image\_tokens × $0.000008 + prompt\_tokens × $0.000005**

## 🎯 Use Cases

- **Product & Fashion Editing** — Adjust outfits, lighting, or background for catalog or campaign visuals.
- **UI/UX & Brand Design** — Apply aesthetic refinements to mockups or visual assets.
- **Creative Direction** — Evolve photo concepts while preserving original mood and framing.
- **Photography & Illustration** — Fix, enhance, or restyle images using natural text prompts.
