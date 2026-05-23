"""
MODEL GUIDE — Curated insight từ feedback thực tế cho từng AI model.

Nguồn data: tổng hợp 2026 từ Artificial Analysis benchmark + Reddit reviews +
WaveSpeed/Runware/Pollo blog + community feedback.

Mục đích: giúp user pick model phù hợp use case mà không cần thử nhiều.

Cấu trúc per-model:
    best_for:      list use case mạnh nhất (concrete, không generic)
    strengths:     3-5 điểm mạnh kèm số liệu thật
    weaknesses:    2-3 điểm yếu/limitations
    ideal_user:    profile creator phù hợp
    niche_tags:    list tags cho filter UI
    sample_prompt: 1 prompt mẫu pattern tốt
    rating:        Elo / community score (nếu có)
    sources:       link blog/review tham khảo
"""

from typing import Any

# Niche tags — dùng để filter UI
NICHE_TAGS = {
    "UGC",              # User-generated content, lo-fi authentic
    "Talking Head",     # Người nói trước camera (cần lipsync)
    "ASMR",             # Tactile sounds, macro, silent
    "Cinematic",        # Premium ad, dramatic, color graded
    "Anime",            # 2D anime style
    "Faceless",         # Hands-only, top-down, no face
    "Storyboard",       # Multi-shot, narrative
    "Product Showcase", # E-commerce, 360 rotation
    "Lifestyle",        # Vlog, aesthetic
    "Multi-Character",  # 2+ subjects giữ identity
    "Budget",           # Rẻ nhất
    "Premium 1080p",    # Top tier quality
    "Realistic Photo",  # Photoreal output
    "Artistic",         # Creative interpretation
}


VIDEO_GUIDE: dict[str, dict[str, Any]] = {

    "vidu_q3_ref": {
        "best_for": [
            "Anime / cel-animation video 16s",
            "Multi-entity consistency (2-4 subjects giữ identity cùng lúc)",
            "Storyboard rapid prototype với native audio",
            "Pre-roll ads + social promos + landing-page explainers",
        ],
        "strengths": [
            "Ranked #1 China, #2 global (Artificial Analysis 03/2026)",
            "Native audio gen — voice + SFX + BGM tự sync trong 1 pass",
            "16s duration (gấp 2-4× competitors) — đủ setup/conflict/resolution",
            "1080P clean detail, anti-aliased",
            "Smart Cuts tự động chuyển góc camera theo narrative",
        ],
        "weaknesses": [
            "Fingers/hands có thể mushy ở close-up",
            "Audio đôi khi clash với mood scene",
            "Character consistency hơi yếu trên prompt complex",
            "Iteration cost cao (1 fail 16s = nhiều credit)",
        ],
        "ideal_user": "Anime creator, social media marketer, filmmaker storyboarding",
        "niche_tags": ["Anime", "Multi-Character", "Storyboard", "UGC", "Cinematic"],
        "sample_prompt": "Two Vietnamese women friends at Saigon cafe rooftop golden hour, woman A holds product while woman B leans in curious, warm conversation, 16:9, smooth handheld camera",
        "rating": "9.0/10 (Pollo) · 8.5/10 (Filmora)",
        "sources": [
            "https://pollo.ai/hub/vidu-q3-review",
            "https://www.promeai.pro/blog/2026/02/05/what-is-vidu-q3/",
            "https://deevid.ai/blog/vidu-q3-review",
        ],
    },

    "vidu_q3_mix_ref": {
        "best_for": [
            "Premium brand ad 1080p tier",
            "Same Vidu Q3 strengths but pure 1080p output",
            "High-budget shoots cần texture chi tiết nhất",
        ],
        "strengths": [
            "1080p chuẩn cao hơn Q3 base (no 540p tier)",
            "Multi-entity consistency strong",
            "Native audio + 16s duration",
        ],
        "weaknesses": [
            "Đắt 2.5× Q3 base ($0.106 vs $0.042) — chỉ dùng final cut",
            "Vẫn limitations về hands/fingers như Q3",
        ],
        "ideal_user": "Brand creator, premium ad agency",
        "niche_tags": ["Premium 1080p", "Cinematic", "Multi-Character"],
        "sample_prompt": "Cinematic product hero shot, Vietnamese model holding YUUMY backpack, golden hour studio lighting, 1080p ultra-detailed, slow rotation 360",
        "rating": "Premium tier — same Q3 quality, 1080p locked",
        "sources": ["https://www.atlascloud.ai/models/vidu/q3-mix/reference-to-video"],
    },

    "wan_2_7_i2v": {
        "best_for": [
            "Talking head video tiếng Việt với lipsync chính xác",
            "Audio-driven narration / explainer",
            "First-frame to motion với prompt control tốt",
            "Cinematography-aware prompting (camera language)",
        ],
        "strengths": [
            "Audio-driven lipsync NATIVE — đưa file audio VN, model tự sync môi",
            "Temporal coherence smooth (motion physically plausible)",
            "First/last frame control + video continuation",
            "Subject + voice cloning integration",
            "Cinematography prompting strong (camera move terminology)",
            "1080p up to 15s",
        ],
        "weaknesses": [
            "Đắt $0.10/s (gấp 2× Vidu Q3)",
            "I2V variant KHÔNG có field aspect_ratio (đọc từ image)",
            "Phải có first-frame image input",
        ],
        "ideal_user": "VN affiliate creator cần talking head, podcast video, course teacher",
        "niche_tags": ["Talking Head", "Cinematic", "Lifestyle", "Product Showcase"],
        "sample_prompt": "Vietnamese woman 22yo at Hanoi cafe, speaking warmly to camera with iPhone front cam handheld feel, natural facial expression, audio_url=<genmax_tts_mai.mp3>",
        "rating": "$0.625/720p gen tier — competitive với Kling/Veo",
        "sources": [
            "https://blog.segmind.com/ai-image-to-video-api-wan-2-7-i2v-review-real-world-use-cases-2026/",
            "https://www.seaart.ai/blog/wan-2-7-review",
            "https://runware.ai/collections/best-lip-sync",
        ],
    },

    "wan_2_7_t2v": {
        "best_for": [
            "Long prompt window (cinematography terminology)",
            "Text-to-video không cần first-frame",
            "Soundtrack via audio URL parameter",
        ],
        "strengths": [
            "Long prompt window — accept detailed scene description",
            "Sharper controls vs Wan 2.5",
            "Native audio output (sync với text scene)",
        ],
        "weaknesses": [
            "Không có lipsync specific như i2v",
            "Cùng $0.10/s — không rẻ",
        ],
        "ideal_user": "Creator viết prompt chi tiết, không có ảnh ref",
        "niche_tags": ["Cinematic", "Storyboard"],
        "sample_prompt": "A supercar exploding out of a long dark tunnel at extreme speed, motion blur, cinematic blockbuster style, ultra-realistic",
        "rating": "Strong text-to-video baseline 2026",
        "sources": ["https://z.tools/blog/alibaba-wan2-7-video"],
    },

    "seedance_v15_pro_i2v": {
        "best_for": [
            "Quick image-to-video 10s clips (simple concept)",
            "Production-stable API (Seedance 2.0 chưa global API)",
            "Basic Pan/Zoom/Tilt camera",
            "Realistic motion với reference image rõ ràng",
        ],
        "strengths": [
            "Production API stable (vs 2.0 vẫn preview)",
            "Camera_fixed flag — lock camera cho macro/product shot",
            "Native audio (generate_audio=true)",
            "$0.047/s — cost-effective tier",
        ],
        "weaknesses": [
            "Resolution chỉ 480p/720p (no 1080p như 2.0)",
            "Duration cap 12s (so 2.0: 15s + auto)",
            "Camera moves cơ bản (no advanced trajectory như 2.0)",
            "ByteDance content filter aggressive cho realistic human faces",
        ],
        "ideal_user": "Production user cần API stable, budget conscious",
        "niche_tags": ["Product Showcase", "UGC", "Faceless"],
        "sample_prompt": "Product 360° rotation on white marble, dramatic side light, macro detail focus, camera_fixed=true, 10s",
        "rating": "Elo ~1200 (vs 2.0 Elo 1351) — solid baseline",
        "sources": [
            "https://www.seedance.best/blog/seedance-1-5-pro-review/",
            "https://www.seedancev2ai.com/en/blog/seedance-1-5-pro-vs-seedance-2-0-ultimate-comparison",
        ],
    },

    "seedance_v15_pro_t2v": {
        "best_for": [
            "Text-to-video budget tier ($0.047/s)",
            "Simple narrative scenes",
        ],
        "strengths": ["Production API stable", "Same v1.5 reliability"],
        "weaknesses": ["Resolution cap 720p"],
        "ideal_user": "Same i2v but no image ref",
        "niche_tags": ["Budget", "UGC"],
        "sample_prompt": "A golden retriever running on sunny beach, waves crashing, cinematic lighting",
        "rating": "Solid budget t2v",
        "sources": ["https://www.seedance.best/blog/seedance-1-5-pro-review/"],
    },

    "seedance_v15_pro_i2v_fast": {
        "best_for": [
            "PROTOTYPE iteration cực rẻ ($0.018/s — rẻ NHẤT hệ thống)",
            "Test concept trước khi commit model đắt",
            "High-volume content production (TikTok daily batch)",
        ],
        "strengths": [
            "RẺ NHẤT — $0.018/s (gấp 5× rẻ hơn Wan 2.7)",
            "5s × $0.018 = $0.09 = ~2.200đ/video",
            "Locked 720p (no quality drop dáo dác)",
            "Camera_fixed cho product shot stable",
        ],
        "weaknesses": [
            "Resolution locked 720p (no upgrade option)",
            "Quality giảm so v1.5 chuẩn — speed vs detail tradeoff",
        ],
        "ideal_user": "Affiliate VN làm 100 video/tháng cần iterate nhanh",
        "niche_tags": ["Budget", "Product Showcase", "UGC"],
        "sample_prompt": "Quick product demo: hand holds backpack, rotates 90°, places on desk, 5s, camera fixed",
        "rating": "Sweet spot cost/quality cho volume use",
        "sources": ["https://zencreator.pro/ai-university/guides/seedance-pro-fast-v15-zencreator"],
    },

    "seedance_2_0_ref": {
        "best_for": [
            "Multi-shot storytelling 60s+ (compared 1.5 Pro chỉ 10s)",
            "Cinematic match cut + whip pan + advanced camera trajectory",
            "Multi-ref synthesis: 9 images + 3 videos + 3 audio cùng generation",
            "Hyper-realistic physics + fluid dynamics",
            "Premium ad cao cấp với @image1, @image2 syntax",
        ],
        "strengths": [
            "Elo 1351 — #1 global (vượt Kling 3.0, Veo 3, Sora 2)",
            "Physics score +31.7 vs 1.5 (gravity, inertia chuẩn)",
            "Multimodal: 9 img + 3 vid + 3 audio in 1 pass",
            "Audio gen + video sync trong cùng pass (không layer post)",
            "Real lipsync multi-language",
            "Super-resolution 720p-SR / 1080p-SR / 1440p-SR",
        ],
        "weaknesses": [
            "API GLOBAL CHƯA — chỉ qua AtlasCloud + select partners (fal.ai)",
            "Disney/Netflix/Paramount/Sony legal pressure → content filter rất gắt",
            "Realistic human faces làm reference image bị BLOCK",
            "Đắt $0.096/s",
        ],
        "ideal_user": "Solo creator 1-người-1-production-crew, ad agency premium",
        "niche_tags": ["Cinematic", "Storyboard", "Multi-Character", "Premium 1080p", "Realistic Photo"],
        "sample_prompt": "In Saigon rooftop@image2, robot@image3 sits, then vehicle@image1 approaches, robot@image3 boards@image1 and drives away, cinematic, 1080p-SR",
        "rating": "Elo 1351 (T2V) / 1269 (I2V) — global #1",
        "sources": [
            "https://aimlapi.com/blog/seedance-2-0-vs-seedance-1-5-pro---bytedances-breakthrough-multimodal-ai-video-models-2026",
            "https://wavespeed.ai/blog/posts/seedance-2-0-review-issues-and-alternatives/",
            "https://www.chatartpro.com/blog/seedance-2-0-upgrade-review/",
        ],
    },

    "seedance_2_0_i2v": {
        "best_for": [
            "Image-to-video flagship — first frame + cinematic motion",
            "Super-resolution upscale 1440p",
        ],
        "strengths": [
            "Same 2.0 quality nhưng input là single image",
            "Advanced camera trajectories",
            "1440p-SR output",
        ],
        "weaknesses": ["Content filter realistic faces", "API preview status"],
        "ideal_user": "Creator có ảnh anchor + muốn cinematic motion",
        "niche_tags": ["Cinematic", "Premium 1080p", "Product Showcase"],
        "sample_prompt": "First frame: sleek spaceship orbiting planet, glowing atmosphere visible, smooth orbital movement, cinematic sci-fi, 1440p-SR",
        "rating": "Elo 1269 I2V global #1",
        "sources": ["https://runware.ai/blog/seedance-2-0-has-landed-on-runware"],
    },

    "seedance_2_0_t2v": {
        "best_for": [
            "Text-to-video không cần image ref",
            "Multi-shot scene description",
        ],
        "strengths": ["Same 2.0 quality", "Native audio sync"],
        "weaknesses": ["No image guidance"],
        "ideal_user": "Creator dùng prompt thuần",
        "niche_tags": ["Cinematic", "Storyboard"],
        "sample_prompt": "Cinematic ocean at sunrise, golden sun spreading across deep blue, powerful waves with white foam, 4K cinematic atmosphere",
        "rating": "Top tier T2V 2026",
        "sources": ["https://www.chatartpro.com/blog/seedance-2-0-upgrade-review/"],
    },

    "seedance_2_0_fast_ref": {
        "best_for": [
            "Iteration TRUNG TIER — gần 2.0 quality nhưng rẻ hơn 20%",
            "High-volume content cần quality > v1.5",
            "Sweet spot reference-to-video budget",
        ],
        "strengths": [
            "$0.076/s (rẻ hơn 2.0 ~20%)",
            "Same multi-ref capability (9 + 3 + 3)",
            "Audio sync native",
        ],
        "weaknesses": [
            "Resolution mất tier 1080p chuẩn (chỉ SR variants)",
            "Tốc độ render nhanh hơn nhưng có thể giảm coherence vài shot",
        ],
        "ideal_user": "Production user cần 2.0 quality + giá hợp lý",
        "niche_tags": ["Cinematic", "Storyboard", "Multi-Character"],
        "sample_prompt": "Multi-ref scene with @image1, @image2, @image3, smooth camera transition, native audio",
        "rating": "Best price/quality 2.0 family",
        "sources": ["https://www.atlascloud.ai/models/bytedance/seedance-2.0-fast/reference-to-video"],
    },

    "seedance_2_0_fast_i2v": {
        "best_for": ["Image-to-video budget 2.0 quality"],
        "strengths": ["20% rẻ hơn 2.0", "Super-res variants"],
        "weaknesses": ["No 1080p chuẩn tier"],
        "ideal_user": "Same i2v 2.0 nhưng budget",
        "niche_tags": ["Product Showcase", "Cinematic"],
        "sample_prompt": "First-frame product macro, smooth orbital motion 360°, 720p-SR",
        "rating": "Middle tier",
        "sources": [],
    },

    "seedance_2_0_fast_t2v": {
        "best_for": ["Text-to-video budget 2.0 quality"],
        "strengths": ["20% rẻ hơn 2.0", "Same prompt language"],
        "weaknesses": ["No 1080p chuẩn"],
        "ideal_user": "Volume t2v production",
        "niche_tags": ["Storyboard", "Cinematic"],
        "sample_prompt": "Cinematic text-to-video with 720p-SR upscale",
        "rating": "Middle tier",
        "sources": [],
    },
}


IMAGE_GUIDE: dict[str, dict[str, Any]] = {

    "seedream_v45": {
        "best_for": [
            "Typography, poster design, brand visual creation",
            "Artistic high-volume gen (rẻ + đẹp)",
            "Stylized images (anime, illustration)",
            "Photography commercial 2K-4K",
        ],
        "strengths": [
            "Lean creativity + style (vs Nano Banana realistic)",
            "Native 2K output, AI upscale 4K",
            "Rẻ $0.036/img — workhorse tier",
            "16 size presets bao gồm 6240*2656 ultra-wide",
            "Strong prompt adherence",
        ],
        "weaknesses": [
            "Speed 10-30s/img (chậm hơn Nano Banana sub-10s)",
            "Text rendering kém Nano Banana Pro",
            "Photorealism không bằng Nano Banana Pro",
        ],
        "ideal_user": "Affiliate VN làm 100 ảnh sản phẩm/tháng, designer artistic",
        "niche_tags": ["Artistic", "Budget", "Product Showcase"],
        "sample_prompt": "Aesthetic Vietnamese street food poster, warm color palette, typography Vietnamese, 2K detailed",
        "rating": "Best budget artistic 2026",
        "sources": [
            "https://wavespeed.ai/blog/posts/seedream-4-5-vs-nano-banana-pro-comparison/",
            "https://blog.laozhang.ai/en/posts/nano-banana-pro-vs-seedream",
        ],
    },

    "seedream_v45_edit": {
        "best_for": [
            "Edit + preserve identity (face, lighting, color tone)",
            "Reference-based gen với 1-10 ảnh anchor",
        ],
        "strengths": ["Same Seedream artistic strengths", "Multi-ref strong"],
        "weaknesses": ["Same Seedream weaknesses + edit-specific drift"],
        "ideal_user": "Designer edit asset có sẵn",
        "niche_tags": ["Artistic", "Multi-Character"],
        "sample_prompt": "Place character from @image1 into beach scene from @image2, preserve face identity",
        "rating": "Solid edit baseline",
        "sources": [],
    },

    "nano_banana_pro_t2i": {
        "best_for": [
            "Photorealistic commercial photography",
            "Native 4K output với text rendering 94-96% accuracy",
            "Magazine cover, billboard, premium ad",
            "Skin/fabric/glass micro-detail",
        ],
        "strengths": [
            "Native 4K (vs Seedream upscale 4K)",
            "Text accuracy 94-96% (Seedream text yếu)",
            "Photorealistic gần DSLR — neutral, realistic",
            "Sub-10s gen speed",
            "Web search grounding cho real-time info",
        ],
        "weaknesses": [
            "Đắt 4-7× Seedream ($0.084 vs $0.036)",
            "Ít artistic interpretation — output neutral",
            "Khi cần style/anime, Seedream tốt hơn",
        ],
        "ideal_user": "Brand premium, agency magazine, e-commerce hero shot",
        "niche_tags": ["Realistic Photo", "Premium 1080p", "Product Showcase"],
        "sample_prompt": "DSLR photo Vietnamese woman holding luxury bag, natural lighting, 4K detail, fabric weave visible",
        "rating": "Photorealism leader 2026",
        "sources": [
            "https://wavespeed.ai/blog/posts/seedream-4-5-vs-nano-banana-pro-comparison/",
            "https://www.seaart.ai/blog/seedream-4-5-vs-nano-banana-pro",
        ],
    },

    "nano_banana_pro_edit": {
        "best_for": ["Edit cao cấp giữ photorealism"],
        "strengths": ["Same Pro quality", "1-5 refs"],
        "weaknesses": ["Premium pricing"],
        "ideal_user": "Premium designer",
        "niche_tags": ["Realistic Photo", "Premium 1080p"],
        "sample_prompt": "Integrate character @image1 into desert dune scene, cinematic lighting, 4K",
        "rating": "Top edit tier",
        "sources": [],
    },

    "nano_banana_2_t2i": {
        "best_for": [
            "Mid-tier photorealism với thinking_level control",
            "Image search grounding cho reference real",
            "Same Google quality giá ~½ Pro",
        ],
        "strengths": [
            "$0.048/img (vs Pro $0.084)",
            "thinking_level: high cho complex prompt",
            "Web + image search grounding",
        ],
        "weaknesses": ["Quality dưới Pro 1 tier"],
        "ideal_user": "User cần Google quality nhưng budget",
        "niche_tags": ["Realistic Photo", "Budget"],
        "sample_prompt": "Photorealistic cyberpunk Vietnam street, neon reflections, 2k",
        "rating": "Best mid-tier Google",
        "sources": [],
    },

    "nano_banana_2_edit": {
        "best_for": ["Edit mid-tier"],
        "strengths": ["thinking_level for complex edits"],
        "weaknesses": ["Below Pro tier"],
        "ideal_user": "Mid-budget edit",
        "niche_tags": ["Realistic Photo", "Budget"],
        "sample_prompt": "Integrate figures in current style scene",
        "rating": "Mid tier",
        "sources": [],
    },

    "wan_2_7_t2i": {
        "best_for": [
            "Multi-output (n=1-4) trong 1 lần gen",
            "Illustration + photorealistic flexible",
            "Color palette control via API",
            "Strong prompt fidelity",
        ],
        "strengths": [
            "RẺ NHẤT $0.03/img (gấp 2× rẻ hơn nano_banana_2)",
            "n=4 output cho 1 prompt — A/B test cực rẻ",
            "thinking_mode flag cho quality boost",
            "5000 char prompt window",
            "color_palette param (3-10 hex)",
        ],
        "weaknesses": [
            "Quality dưới Seedream + Nano Banana ở premium",
            "Resolution 1K/2K only (no 4K native)",
        ],
        "ideal_user": "Volume creator A/B test, designer budget",
        "niche_tags": ["Budget", "Artistic", "Multi-Character"],
        "sample_prompt": "Vietnamese countryside landscape, color_palette: #F5DEB3 70%, #228B22 30%, n=4 variations",
        "rating": "Best volume image 2026",
        "sources": ["https://www.atlascloud.ai/models/alibaba/wan-2.7/text-to-image"],
    },

    "wan_2_7_edit": {
        "best_for": [
            "Multi-image reference edit (1-9 refs)",
            "Recompose scene với text instruction",
        ],
        "strengths": [
            "$0.03/img — rẻ nhất edit tier",
            "1-9 references — flexible compose",
            "Same Wan quality + n=4 output",
        ],
        "weaknesses": ["Quality dưới Nano Banana Pro edit"],
        "ideal_user": "Budget edit creator",
        "niche_tags": ["Budget", "Artistic"],
        "sample_prompt": "Girl in @image1 wearing necklace @image2 carrying bag @image3, golden hour, n=2",
        "rating": "Budget edit champion",
        "sources": [],
    },
}


def get_video_guide(model_key: str) -> dict:
    """Get guide cho model video. Trả empty dict nếu không có."""
    return VIDEO_GUIDE.get(model_key, {})


def get_image_guide(model_key: str) -> dict:
    """Get guide cho model image."""
    return IMAGE_GUIDE.get(model_key, {})


def list_by_niche(niche: str) -> list[str]:
    """Trả list model_key có niche_tag cụ thể.

    Args:
        niche: 1 trong NICHE_TAGS, e.g. "Talking Head", "Budget", "Anime"
    """
    matches = []
    for key, guide in {**VIDEO_GUIDE, **IMAGE_GUIDE}.items():
        if niche in guide.get("niche_tags", []):
            matches.append(key)
    return matches


def recommend_for_use_case(use_case: str) -> list[dict]:
    """Recommend model cho 1 use case cụ thể.

    Use case examples:
        - "Talking head VN audio" → wan_2_7_i2v
        - "Anime 16s" → vidu_q3_ref
        - "Budget volume video" → seedance_v15_pro_i2v_fast
        - "Premium ad 1080p" → vidu_q3_mix_ref or seedance_2_0_*
        - "Photorealistic 4K image" → nano_banana_pro_t2i
        - "Volume A/B test image" → wan_2_7_t2i (n=4)
    """
    use_case_l = use_case.lower()
    matches = []

    rules = [
        # Video
        (["talking head", "lipsync", "voice", "narration", "thuyết minh", "khớp môi"], "wan_2_7_i2v"),
        (["anime", "cel", "2d animation"], "vidu_q3_ref"),
        (["budget video", "rẻ video", "iterate", "test concept"], "seedance_v15_pro_i2v_fast"),
        (["multi-shot", "storyboard", "cinematic", "premium ad"], "seedance_2_0_ref"),
        (["premium 1080p video", "brand ad", "hero shot video"], "vidu_q3_mix_ref"),
        (["multi entity", "multiple subject", "2 người", "nhiều nhân vật"], "vidu_q3_ref"),
        # Image
        (["photorealistic", "4k photo", "magazine", "dslr", "ảnh thật"], "nano_banana_pro_t2i"),
        (["artistic", "stylized", "poster", "typography", "nghệ thuật"], "seedream_v45"),
        (["budget image", "volume image", "rẻ ảnh", "a/b test"], "wan_2_7_t2i"),
        (["edit image", "compose", "ghép ảnh"], "nano_banana_pro_edit"),
    ]

    for keywords, model_key in rules:
        if any(kw in use_case_l for kw in keywords):
            guide = {**VIDEO_GUIDE, **IMAGE_GUIDE}.get(model_key, {})
            matches.append({
                "model_key": model_key,
                "best_for": guide.get("best_for", []),
                "ideal_user": guide.get("ideal_user"),
                "rating": guide.get("rating"),
            })

    return matches
