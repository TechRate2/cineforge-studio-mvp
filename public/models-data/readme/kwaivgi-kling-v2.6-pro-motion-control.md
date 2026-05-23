
## Kling v2.6 Pro Motion Control


**Kling v2.6 Pro Motion Control** is Kuaishou's advanced **motion transfer model** that animates a reference image by applying the movement from a reference video. Upload a character image and a motion clip (like a dance or action sequence), and the model extracts the motion path to generate smooth, realistic video where your subject performs those exact movements.


## Key capabilities


* Motion extraction and transfer
Upload a 3 to 30-second reference video showing any movement (dance, walk cycle, martial arts, gestures), and the model captures the full motion sequence frame-by-frame to apply it to your image.
* Full-body motion accuracy
The system captures detailed movements including posture, limb positions, and complex actions, ensuring smooth and natural-looking animation even for fast or intricate sequences.
* Flexible character orientation control
Choose whether the final video follows the reference image's aspect ratio and composition ("image" mode) or the reference video's framing ("video" mode), with duration limits adjusted accordingly.
* Audio preservation option
Retain the original audio from your reference video or generate silent output, giving you control over the final soundscape.
* Prompt-guided refinement
Use text prompts to adjust scene details, styling, lighting, and atmosphere while maintaining the core motion transfer from the reference video.


## Parameters and how to use


* image: (required) The reference image showing the subject you want to animate
* video: (required) The reference video containing the motion sequence to transfer
* character_orientation: (required) Controls output framing and duration limits
* prompt: Text description to refine scene details, style, and atmosphere
* keep_original_sound: Whether to preserve audio from the reference video
* negative_prompt: Elements to avoid in the generated video


### How to use


* **Prompt**

 Describe the scene setting, visual style, lighting, and atmosphere you want while the motion is being transferred. The model will apply your reference video's movement to your reference image, so focus your prompt on environmental details rather than the action itself.


Example: *"cinematic lighting, shallow depth of field, urban street background, golden hour, film grain"*


**Media requirements**


### Images


* Max file size: 10 MB
* Tip: Use clear, well-lit images showing the full subject for best motion transfer results


### Videos


* Duration limits depend on character_orientation setting (see below)


**Other parameters**


* character_orientation – (required) Choose one:

image – Output matches the reference image's framing and composition.
video – Output matches the reference video's framing and composition. Reference video can be up to 30 seconds.
* keep_original_sound – Boolean, defaults to true

true – Preserve audio from the reference video
false – Generate silent video output
* negative_prompt – Optional text to specify unwanted elements like "blurry, distorted, watermark, low quality, flickering". Max 2,500 characters.


After you finish configuring the parameters, click **Run**, preview the result, and iterate if needed.


## Pricing



| Duration (s) | Billed Duration (s) | Total Price (USD) |
| :--- | :--- | :--- |
| 5 | 5 | $0.560 |
| 10 | 10 | $1.120 |
| 15 | 15 | $1.680 |
| 30 | 30 | $3.360 |


## Notes


**Best practices:**


* For complex movements like dance or martial arts, use reference videos between 3 and 10 seconds showing clear, unobstructed motion
* Ensure your reference image shows the subject in good lighting with minimal occlusion
* Start with the default settings and use prompts primarily for scene styling rather than motion instructions
* The model works best when the reference image subject and reference video subject are similar in type (e.g., both human characters)


**Use cases:**


* Animate character illustrations with real dance choreography or action sequences
* Create product demonstration videos by transferring human gestures to animated mascots
* Generate character performance clips for storyboarding and concept work
* Produce social media content by applying trending motion clips to custom characters


## Related Models


* Kling v2.6 Pro Image-to-Video – Generate videos from a single image with prompt-driven motion and optional native audio.
* Kling v2.6 Pro Text-to-Video – Create videos entirely from text prompts with cinematic visuals and audio–video co-generation.
* Kling Omni Video O1 Reference-to-Video – Maintain subject identity across frames using multi-reference inputs for character-consistent video generation.
