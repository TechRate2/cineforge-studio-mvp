"""Demo: trace input bundle the Director Agent receives, plus validator outputs.

Runs WITHOUT calling LLM — so it's free + instant. Use to understand what
the agent sees before/after each layer.

Run from project root:
    cd backend && python ../_design_refs/demo_pipeline.py
"""
import sys
import json
from pathlib import Path

# Make backend imports work from _design_refs/
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")


def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


# ============================================================
# 1. SAMPLE USER INPUT — what the Studio UI sends
# ============================================================
USER_INPUT = {
    "product_input": {
        "url": None,
        "text_description": "Son li matte 89k, dưỡng ẩm 8h, không chì",
        "image_urls": [],
    },
    "reference_images": [
        "https://example.com/character_linh.jpg",
        "https://example.com/lipstick_product.jpg",
    ],
    "reference_role_hints": ["character_anchor", "product_hero"],
    "reference_videos": [],
    "user_brief": (
        "Video TikTok 15 giây cho nữ Gen Z thử son lì matte 89k tại bàn make-up. "
        "Cảm giác golden hour soft, confident, vibe UGC review thật. "
        "Hook đầu phải mạnh để giữ chân scroll."
    ),
    "context_injection": {
        "pain_points": "Son hay bị khô môi sau 2-3h, dễ trôi khi ăn",
        "usps": "Dưỡng ẩm 8h liên tục, vegan, giá 89k cực hợp Gen Z VN",
        "real_reviews": "\"Mình lì cả buổi đi học không cần dặm lại\"",
        "forbidden_to_say": "Không nói chữa nẻ môi, không so sánh đối thủ",
        "mood_hint": "Chill confident, hơi flex một chút",
    },
    "tech_config": {
        "model": "seedance_2_0",
        "duration_s": 15,
        "aspect_ratio": "9:16",
        "resolution": "720p",
        "audio_mode": "dialogue_vo",
        "num_shots": None,
    },
    "niche_hint": "beauty",
}


# ============================================================
# 2. BUILD INPUT BUNDLE — what Director Agent actually gets
# ============================================================
section("LAYER 1A · USER INPUT (raw from UI)")
print(json.dumps(USER_INPUT, ensure_ascii=False, indent=2))


from agent.director_agent import DirectorAgent  # noqa: E402

agent = DirectorAgent()

director_input = agent._build_director_input(
    product_input=USER_INPUT["product_input"],
    reference_images=USER_INPUT["reference_images"],
    reference_videos=USER_INPUT["reference_videos"],
    user_brief=USER_INPUT["user_brief"],
    context_injection=USER_INPUT["context_injection"],
    tech_config=USER_INPUT["tech_config"],
    niche_hint=USER_INPUT["niche_hint"],
    ref_hints=[
        {"index": 0, "role": "character_anchor", "notes": "user-tagged"},
        {"index": 1, "role": "product_hero", "notes": "user-tagged"},
    ],
)

section("LAYER 1B · DIRECTOR INPUT BUNDLE (built by _build_director_input)")
print(json.dumps(director_input, ensure_ascii=False, indent=2))

section("LAYER 1C · STORYTELLING_CONTEXT BLOCK (V4 injection — the new layer)")
print("This is the structural skeleton the LLM is forced to follow.")
print("Excerpt from the bundle's 'storytelling_context' field:\n")
sc = director_input["storytelling_context"]
print(">>> hook_patterns (LLM picks EXACTLY ONE):")
print(sc["hook_patterns"][:800] + "...\n")
print(">>> beat_sheet (for duration=15s):")
print(sc["beat_sheet"])
print("\n>>> hard_rules:")
print(sc["hard_rules"])
print("\n>>> niche_slots:")
print(sc["niche_slots"])


# ============================================================
# 3. SHOW WHAT director.md (system prompt) tells the LLM
# ============================================================
section("LAYER 1D · system_prompts/director.md HEAD (first 30 lines)")
from system_prompts import load  # noqa: E402
load.cache_clear()
dprompt = load("director")
print("\n".join(dprompt.splitlines()[:30]))
print(f"\n... ({len(dprompt.splitlines())} lines total, {len(dprompt)} chars)")


# ============================================================
# 4. EXAMPLE: what a GOOD plan looks like + validator runs CLEAN
# ============================================================
section("LAYER 1E · EXAMPLE DirectorPlan output (realistic LLM result)")
sample_plan = {
    "plan_id": "dp_abc123def",
    "continuity_bible": {
        "title": "Son lì 89k thử thách 8 tiếng",
        "logline": "Linh thử son lì matte cả ngày — review thật không filter",
        "intent": "viral_short",
        "duration_s": 15,
        "aspect_ratio": "9:16",
        "characters": [{
            "id": "char_linh",
            "name": "Linh",
            "role": "protagonist",
            "face_signature": (
                "Vietnamese woman, late 20s, shoulder-length straight black hair "
                "with subtle layers, warm fair skin, calm intelligent eyes"
            ),
            "outfit": "Cream knit cardigan over white silk camisole",
            "personality": ["confident", "casual", "self-aware"],
        }],
        "products": [{
            "id": "prod_son",
            "name": "Son lì matte 89k",
            "hero_features": ["Lì 8h", "Dưỡng ẩm", "Vegan"],
            "packaging_description": "Tube matte black, gold accent ring",
            "color_palette": ["#3D1A1A", "#C9A961"],
            "forbidden_claims": ["chữa nẻ", "so sánh đối thủ"],
        }],
        "visual_style": {
            "cinematography": "handheld UGC iPhone with cinematic grading",
            "color_grading": "warm filmic teal-and-orange",
            "lighting_design": "golden hour soft window light",
            "camera_language": "handheld follow + push-in reveal",
            "film_grain": "subtle 35mm grain",
            "aspect_ratio": "9:16",
        },
        "audio_design": {
            "mood": "chill confident",
            "tempo": "mid",
            "music_genre": "VN indie pop lo-fi",
            "sfx_emphasis": ["soft clink", "lip pop"],
            "dialogue_style": "conversational",
        },
        "setting": {
            "location": "bàn make-up cửa sổ buổi chiều",
            "time_of_day": "golden hour 4PM",
            "atmosphere": "ấm, intimate, chill",
        },
        "constraints": {
            "must_have": ["dưỡng ẩm 8h", "vegan", "89k"],
            "must_avoid": ["chữa nẻ", "so sánh đối thủ"],
            "brand_safety": ["no medical claim", "VN platform safe"],
        },
        "reference_assets": [
            {"index": 0, "url": USER_INPUT["reference_images"][0],
             "role": "character_anchor",
             "apply_to_shots": ["S1", "S2", "S4", "S5"], "notes": "Face anchor"},
            {"index": 1, "url": USER_INPUT["reference_images"][1],
             "role": "product_hero",
             "apply_to_shots": ["S3", "S4", "S5"], "notes": "Product hero"},
        ],
        "director_notes": (
            "Hook bằng POV reaction confession — viewer tin tưởng ngay. "
            "Lighting golden hour làm 'casual lifestyle' không trông như ads. "
            "Product chỉ xuất hiện ở 6s (40% runtime) khi đã setup pain."
        ),
        "storytelling_meta": {
            "hook_pattern": "pov_confession",
            "beat_coverage": ["HOOK", "PAIN", "REVEAL", "PROOF", "CTA"],
            "product_first_appearance_s": 6.0,
            "primary_emotion_arc": "curiosity → recognition → relief → trust → action",
        },
    },
    "shot_list": [
        {
            "shot_id": "S1", "index": 0, "start_s": 0.0, "end_s": 2.0,
            "duration_s": 2, "purpose": "hook", "emotion_beat": "pov_confession",
            "visual": {
                "subject": "Linh side profile half-smile, looking down",
                "action": "tay đưa lên môi như chuẩn bị nói gì",
                "camera_shot": "MCU", "camera_movement": "handheld",
                "composition": "rule-of-thirds", "lighting_override": None,
                "background": "blurred warm window backlight",
            },
            "audio": {
                "dialogue_vn": "Ok mình thử cái này 8 tiếng nha...",
                "caption_on_screen": "8 tiếng cùng son lì 89k", "sfx": [],
            },
            "continuity": {
                "character_ids": ["char_linh"], "product_ids": [],
                "reference_indices": [0],
                "previous_shot_id": None,
                "style_anchor": "warm 35mm grain, golden hour, shallow DOF",
            },
            "model_routing": {"preferred_model": "seedance_2_0",
                              "reasoning": "Multi-shot native + dialogue audio"},
            "dynamic_description": (
                "0:00-0:02 Handheld MCU side profile, Linh half-smile, "
                "warm rim light from window right, slight head turn"
            ),
        },
        {
            "shot_id": "S2", "index": 1, "start_s": 2.0, "end_s": 6.0,
            "duration_s": 4, "purpose": "pain", "emotion_beat": "recognition",
            "visual": {
                "subject": "Linh ở bàn make-up nhìn vào gương vẻ ngán",
                "action": "dùng giấy chậm chậm lau môi son cũ",
                "camera_shot": "WS", "camera_movement": "push-in",
                "composition": "centered", "lighting_override": None,
                "background": "bàn make-up đầy son cũ scattered",
            },
            "audio": {
                "dialogue_vn": "Mỗi 2 tiếng lại phải dặm... mệt thiệt sự.",
                "caption_on_screen": None, "sfx": ["paper tissue"],
            },
            "continuity": {
                "character_ids": ["char_linh"], "product_ids": [],
                "reference_indices": [0],
                "previous_shot_id": "S1",
                "style_anchor": "warm 35mm grain, golden hour",
            },
            "model_routing": {"preferred_model": "seedance_2_0",
                              "reasoning": "Chain from S1, same character"},
            "dynamic_description": (
                "0:00-0:04 WS push-in từ door, Linh tại bàn lau son cũ, "
                "shallow DOF tập trung mặt"
            ),
        },
        {
            "shot_id": "S3", "index": 2, "start_s": 6.0, "end_s": 10.0,
            "duration_s": 4, "purpose": "reveal", "emotion_beat": "relief",
            "visual": {
                "subject": "son lì matte 89k trên bàn dưới ánh nắng",
                "action": "tay Linh chậm rãi cầm son lên",
                "camera_shot": "ECU", "camera_movement": "pull-out",
                "composition": "rule-of-thirds", "lighting_override": None,
                "background": "warm wood desk + lens flare",
            },
            "audio": {
                "dialogue_vn": "Cho đến khi tìm được em này.",
                "caption_on_screen": "Lì 8h · Vegan · 89k", "sfx": ["soft pickup"],
            },
            "continuity": {
                "character_ids": ["char_linh"], "product_ids": ["prod_son"],
                "reference_indices": [1],
                "previous_shot_id": None,
                "style_anchor": "warm filmic, anamorphic flare",
            },
            "model_routing": {"preferred_model": "seedance_2_0",
                              "reasoning": "Product hero reveal — need refs"},
            "dynamic_description": (
                "0:00-0:04 ECU pull-out, son trên bàn → tay Linh enter frame, "
                "warm key bloom"
            ),
        },
        {
            "shot_id": "S4", "index": 3, "start_s": 10.0, "end_s": 13.0,
            "duration_s": 3, "purpose": "proof", "emotion_beat": "validation",
            "visual": {
                "subject": "Linh apply son, môi căng matte",
                "action": "swipe son một lần, mỉm cười nhẹ",
                "camera_shot": "MCU", "camera_movement": "static",
                "composition": "centered", "lighting_override": None,
                "background": "soft bokeh warm",
            },
            "audio": {
                "dialogue_vn": "Lì cả buổi đi học, không cần dặm.",
                "caption_on_screen": None, "sfx": [],
            },
            "continuity": {
                "character_ids": ["char_linh"], "product_ids": ["prod_son"],
                "reference_indices": [0, 1],
                "previous_shot_id": "S3",
                "style_anchor": "warm 35mm, soft window",
            },
            "model_routing": {"preferred_model": "seedance_2_0",
                              "reasoning": "Chain from product reveal"},
            "dynamic_description": (
                "0:00-0:03 MCU static, Linh swipe son confidence, "
                "matte texture catches light"
            ),
        },
        {
            "shot_id": "S5", "index": 4, "start_s": 13.0, "end_s": 15.0,
            "duration_s": 2, "purpose": "cta", "emotion_beat": "action",
            "visual": {
                "subject": "son lì + tag giá 89k overlay",
                "action": "son đặt xuống bàn, tag price slide in",
                "camera_shot": "MS", "camera_movement": "push-in",
                "composition": "centered", "lighting_override": None,
                "background": "warm wood gradient",
            },
            "audio": {
                "dialogue_vn": "Link giỏ hàng bio. Thử đi.",
                "caption_on_screen": "Shop ngay · 89k", "sfx": ["product set down"],
            },
            "continuity": {
                "character_ids": [], "product_ids": ["prod_son"],
                "reference_indices": [1],
                "previous_shot_id": "S4",
                "style_anchor": "warm filmic, brand color highlight",
            },
            "model_routing": {"preferred_model": "seedance_2_0",
                              "reasoning": "Product CTA frame"},
            "dynamic_description": (
                "0:00-0:02 MS push-in slow, son center frame, "
                "price tag fade in, brand back-light"
            ),
        },
    ],
    "storyboard_grid": [],
}

print(f"Bible characters: {len(sample_plan['continuity_bible']['characters'])}")
print(f"Bible products:   {len(sample_plan['continuity_bible']['products'])}")
print(f"Shot list:        {len(sample_plan['shot_list'])} shots")
print(f"Hook pattern:     {sample_plan['continuity_bible']['storytelling_meta']['hook_pattern']}")
print(f"Beat coverage:    {sample_plan['continuity_bible']['storytelling_meta']['beat_coverage']}")
print(f"Product first appears @ {sample_plan['continuity_bible']['storytelling_meta']['product_first_appearance_s']}s")


# ============================================================
# 5. STORYTELLING VALIDATOR — run on the good plan
# ============================================================
section("LAYER 1F · STORYTELLING VALIDATOR (storytelling.validate_plan)")
from agent.storytelling import validate_plan  # noqa: E402

issues = validate_plan(sample_plan)
print(f"Result: {len(issues)} issue(s)")
for i in issues:
    print(f"  [{i.severity}] {i.code}: {i.message}")
if not issues:
    print("  CLEAN — plan obeys all storytelling rules.")


# ============================================================
# 6. SCENE GEN INPUT — what scene.md LLM gets per shot
# ============================================================
section("LAYER 2 · SCENE GEN INPUT (built per shot, lazy)")
shot1 = sample_plan["shot_list"][0]
scene_payload_example = {
    "bible": "(full bible passed — omitted for brevity)",
    "shot": {
        "shot_id": shot1["shot_id"], "purpose": shot1["purpose"],
        "emotion_beat": shot1["emotion_beat"],
        "visual": shot1["visual"], "audio": shot1["audio"],
        "continuity": shot1["continuity"],
        "dynamic_description": shot1["dynamic_description"],
    },
    "model_key": "seedance_2_0_ref",
    "model_format_hint": "multi_shot_inline",
    "last_frame_url": None,
    "reference_images": USER_INPUT["reference_images"],
    "reference_videos": [],
    "beat_intent": (
        "PATTERN INTERRUPT beat — extreme/anomaly camera, high contrast cut, "
        "NO product, max scroll-stop impact."
    ),
}
print(json.dumps(scene_payload_example, ensure_ascii=False, indent=2))


# ============================================================
# 7. EXAMPLE SCENE OUTPUT (what scene.md LLM returns)
# ============================================================
section("LAYER 2 · SCENE GEN OUTPUT for shot S1 (expected LLM result)")
scene_output_s1 = {
    "prompt": (
        "[STYLE & MOOD]\n"
        "Photorealistic cinematic UGC, warm filmic 35mm grain, "
        "shallow depth of field, anamorphic subtle flare. "
        "Palette: warm amber + soft window backlight.\n\n"
        "[DYNAMIC DESCRIPTION]\n"
        "[Shot 1 | 2s | handheld | @image_1 as primary character (exact face, "
        "hair, outfit from reference)]\n"
        "0:00-0:02 Handheld MCU side profile, Linh @image_1 half-smile, "
        "tay đưa lên môi như sắp nói, warm rim light from window right, "
        "slight head turn toward camera. Character speaks: "
        "\"Ok mình thử cái này 8 tiếng nha...\"\n\n"
        "[STATIC DESCRIPTION]\n"
        "Same character across all shots: Vietnamese woman, late 20s, "
        "shoulder-length straight black hair with subtle layers, warm fair "
        "skin, calm intelligent eyes. Outfit: cream knit cardigan over "
        "white silk camisole. Location: bàn make-up cửa sổ chiều, "
        "golden hour 4PM, warm intimate atmosphere."
    ),
    "negative_prompt": (
        "chữa nẻ, so sánh đối thủ, no product close-up, no logo, "
        "no brand watermark in opening frame, extra fingers, warped face, "
        "low quality, watermark, text overlay duplication, "
        "lens distortion, sudden shake, age indicators"
    ),
    "reference_image_indices": [0],
    "render_mode": "ref_to_video",
    "chain_input_url": None,
    "model_params": {
        "duration_s": 2, "resolution": "720p", "aspect_ratio": "9:16",
        "generate_audio": True, "movement_amplitude": "auto",
        "return_last_frame": True,
    },
}
print(json.dumps(scene_output_s1, ensure_ascii=False, indent=2))


# ============================================================
# 8. ATLAS CLOUD PAYLOAD (what hits the GPU API)
# ============================================================
section("LAYER 3 · ATLAS PAYLOAD for shot S1 (what hits AtlasCloud GPU)")
atlas_payload = {
    "model": "bytedance/seedance-v2.0/reference-to-video",
    "prompt": scene_output_s1["prompt"],
    "negative_prompt": scene_output_s1["negative_prompt"],
    "reference_images": [USER_INPUT["reference_images"][0]],
    "ratio": "9:16",
    "resolution": "720p",
    "duration": 2,
    "generate_audio": True,
    "return_last_frame": True,
    "seed": 0,
}
print(json.dumps(atlas_payload, ensure_ascii=False, indent=2))


# ============================================================
# 9. CHAINING — S2 reuses S1's last_frame_url
# ============================================================
section("LAYER 3 · CHAIN — S2 receives last_frame_url from S1")
print("AtlasCloud returns S1 result:")
s1_atlas_response = {
    "video_url": "https://r2.example.com/clip_S1.mp4",
    "last_frame_url": "https://r2.example.com/clip_S1_last_frame.jpg",
    "duration": 2.0,
}
print(json.dumps(s1_atlas_response, ensure_ascii=False, indent=2))

print("\nFor S2 (purpose=pain, previous_shot_id=S1), Scene Gen swaps to i2v:")
s2_scene_output = {
    "render_mode": "i2v_chain",
    "chain_input_url": s1_atlas_response["last_frame_url"],
    "prompt_prefix": (
        "Continue from previous frame: same character, same wardrobe, "
        "same lighting, same color grade. Now: "
    ),
    "prompt_body": (
        "WS push-in through doorway, Linh seated at make-up desk, "
        "wiping old lipstick off with tissue, scattered old products on desk, "
        "warm golden hour light from left window. Character speaks: "
        "\"Mỗi 2 tiếng lại phải dặm... mệt thiệt sự.\""
    ),
    "model_key": "seedance_2_0_i2v",  # AUTO-SWAPPED from _ref to _i2v
}
print(json.dumps(s2_scene_output, ensure_ascii=False, indent=2))


section("✅ END OF WALKTHROUGH — Real input → real output structure")
print("All JSON shown above is the EXACT shape passed between agents.")
print("The only thing not real here is the LLM-generated text content")
print("(we'd need to spend ~$0.04 to get a real DeepSeek/Claude response).")
