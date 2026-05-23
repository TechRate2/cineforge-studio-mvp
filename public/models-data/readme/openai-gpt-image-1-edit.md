# OpenAI GPT-Image-1-Edit

Edit and transform images with natural language using **OpenAI's GPT-Image-1-Edit**. This versatile model understands your instructions to apply style changes, modifications, and creative transformations — with optional mask support for precise regional editing and multiple quality tiers to match your needs and budget.

## Why It Looks Great

- **Natural language editing**: Describe transformations in plain text — style changes, modifications, enhancements.
- **Mask support**: Use mask images for precise control over which areas to edit.
- **Quality tiers**: Choose from `low`, `medium`, or `high` quality based on your needs.
- **Multiple sizes**: Output in square (`1024x1024`) or rectangular (`1024x1536`, `1536x1024`) formats.
- **Style transformation**: Excels at converting images to different artistic styles.
- **OpenAI quality**: Powered by advanced vision-language understanding.

## Parameters

| Parameter | Required | Description |
|---|---|---|
| `prompt` | Yes | Text instruction describing the edit or transformation you want. |
| `image` | Yes | Source image to edit (upload or public URL). |
| `quality` | No | Output quality: `low`, `medium`, or `high`. Default: `medium`. |
| `mask_image` | No | Optional mask to specify edit regions (upload or URL). |
| `size` | No | Output dimensions: `1024x1024`, `1024x1536`, or `1536x1024`. |
| `enable_sync_mode` | No | API only: Waits for result and returns it directly. |
| `enable_base64_output` | No | API only: Returns base64 string instead of URL. |

## How to Use

1. **Write your edit instruction** — describe the transformation you want (e.g. `"Become a comic style"`).
2. **Upload your image** — drag and drop or paste a public URL.
3. **Choose quality** — select `low`, `medium`, or `high` based on your needs.
4. **Add mask (optional)** — upload a mask image to limit edits to specific areas.
5. **Select size** — choose your desired output dimensions.
6. **Run** — click the button to apply the edit.
7. **Download** — preview and save your transformed image.

## Quick Reference

| Quality | 1024x1024 | 1024x1536 / 1536x1024 |
|---|---:|---:|
| Low | $0.011 | $0.016 |
| Medium | $0.042 | $0.063 |
| High | $0.167 | $0.250 |

## Best Use Cases

- **Style Transfer** — Convert photos to comic, cartoon, painting, or other artistic styles.
- **Creative Transformation** — Reimagine images with different aesthetics or themes.
- **Regional Editing** — Use masks to edit specific areas while preserving the rest.
- **Content Enhancement** — Improve or modify specific aspects of images.
- **Artistic Interpretation** — Transform photos into various art forms.

## Example Prompts

> "Become a comic style"  
> "Transform into a watercolor painting"  
> "Make it look like a vintage photograph from the 1950s"  
> "Convert to anime style illustration"  
> "Apply a cyberpunk neon aesthetic"  
> "Turn into a pencil sketch"

## Quality Guide

| Quality | Best For | Trade-off |
|---|---|---|
| Low | Quick previews, testing concepts, high-volume processing | Fastest, most affordable, lower detail |
| Medium | General use, social media, balanced needs | Good quality/cost balance |
| High | Professional work, final deliverables, maximum detail | Highest quality, premium price |

## Pro Tips for Best Results

- Start with `medium` quality to test your prompt, then upgrade to `high` for final output.
- Use masks when you want to preserve specific areas untouched.
- Be specific about the target style — `"comic style"`, `"oil painting"`, `"anime"`.
- For style transfers, simpler source images often produce cleaner results.
- Rectangular sizes work well for portraits (`1024x1536`) or landscapes (`1536x1024`).
- The model interprets style instructions creatively — embrace the artistic interpretation.

## Notes

- If using URLs for images or masks, ensure they are publicly accessible.
- The `enable_sync_mode` and `enable_base64_output` options are only available through the API.
- Mask images should be black and white, where white indicates areas to edit.
- Processing time varies by quality level — higher quality takes longer.