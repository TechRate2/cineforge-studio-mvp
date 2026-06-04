"""Read-only autonomous production decision preview.

This module answers the practical product question before a paid render starts:
given an idea, runtime, market, and references, what production workflow should
CineJelly use? It is deterministic and vendor-free, so it can back admin/UI
inspection without calling LLMs or AtlasCloud.
"""
from __future__ import annotations

import re
import unicodedata
from math import ceil, floor
from typing import Any, Optional

from agent.creative_treatment_search import build_creative_treatment_search
from agent.creative_brief_contract import build_creative_brief_contract
from agent.creative_producer_v2 import build_creative_producer_v2
from agent.cinematic_grammar_contract import build_cinematic_grammar_contract
from agent.asset_bible_completion_policy import build_asset_bible_completion_policy
from agent.dialogue_route_policy import build_dialogue_route_policy
from agent.hero_shot_candidate_policy import build_hero_shot_candidate_policy
from agent.long_form_error_recycling_policy import build_long_form_error_recycling_policy
from agent.long_form_execution_gate import build_long_form_execution_gate
from agent.long_form_orchestrator import plan_runtime_structure
from agent.llm_brain_policy import build_llm_brain_policy
from agent.market_inference import infer_target_market
from agent.autonomous_model_route_strategy import build_model_route_strategy
from agent.niche_execution_rubric import build_niche_execution_rubric
from agent.niche_production_recipe import build_niche_production_recipe
from agent.niche_runtime_director import build_niche_runtime_director_contract
from agent.autonomous_route_quality_scorecard import build_route_quality_scorecard
from agent.prompt_template_bank_policy import build_prompt_template_bank_policy
from agent.prompt_execution_contract_v3 import build_prompt_execution_contract_v3
from agent.viral_creative_brain import build_viral_creative_brain
from agent.output_qa_retry_brain import build_output_qa_retry_brain
from agent.scene_planner import plan_scene_blueprints
from agent.screenplay_planner import plan_screenplay
from agent.seedance_reference_allocation import build_seedance_reference_allocation
from agent.seedance_prompt_formula import build_seedance_prompt_formula
from agent.reference_sufficiency_gate import build_reference_sufficiency_report
from agent.responsible_content_gate import build_responsible_content_gate
from agent.script_asset_sop import build_script_asset_sop
from skills.market_playbooks import get_market_playbook
from skills.niche_benchmarks import get_benchmark_case
from skills.niche_playbooks import get_niche_playbook, list_niche_keys
from skills.niche_readiness import build_niche_readiness_matrix


_KEYWORDS: dict[str, list[str]] = {
    "app_saas": [
        "saas", "app", "dashboard", "inbox", "workflow", "automation", "ai tool", "crm",
        "shop online", "online shop", "launch app", "app ai", "ai app", "founder launch",
        "doanh thu", "ra mat app", "ra mat ung dung", "ung dung", "phan mem", "cong cu ai",
        "ứng dụng", "phần mềm", "bảng điều khiển", "tự động hóa", "công cụ ai",
    ],
    "asmr": [
        "asmr", "satisfying", "peel", "tap", "crunch", "texture", "packaging",
        "bóc vỏ", "gõ nhẹ", "giòn", "chất liệu", "đóng gói",
    ],
    "automotive": [
        "car", "suv", "vehicle", "motorbike", "headlight", "engine", "interior",
        "ô tô", "xe hơi", "xe máy", "đèn pha", "động cơ", "nội thất xe",
    ],
    "beauty": [
        "beauty", "skincare", "makeup", "lipstick", "serum", "haircare", "fragrance",
        "làm đẹp", "mỹ phẩm", "chăm sóc da", "trang điểm", "son môi", "kem nền",
        "kem chống nắng", "nước hoa", "dưỡng tóc",
    ],
    "documentary": [
        "documentary", "docu", "true story", "history", "founder story", "coffee shop",
        "phóng sự", "tài liệu", "câu chuyện thật", "lịch sử", "hành trình sáng lập",
    ],
    "drama": [
        "drama", "short film", "story", "relationship", "twist", "message", "apartment",
        "phim ngắn", "câu chuyện", "cốt truyện", "tình cảm", "cú twist", "căn hộ",
    ],
    "ecommerce_catalog": [
        "catalog", "marketplace", "sku", "backpack", "feature", "compartment",
        "sản phẩm", "thương mại điện tử", "gian hàng", "tính năng", "ngăn chứa",
    ],
    "education": [
        "explain", "learn", "tutorial", "education", "how to", "lesson", "study",
        "giải thích", "học", "hướng dẫn", "giáo dục", "bài học", "nghiên cứu",
    ],
    "fashion": [
        "fashion", "outfit", "dress", "lookbook", "styling", "fabric",
        "thời trang", "trang phục", "váy", "áo", "phối đồ", "vải",
    ],
    "finance_education": [
        "finance", "invest", "emergency fund", "budget", "saving", "money",
        "tài chính", "đầu tư", "quỹ dự phòng", "ngân sách", "tiết kiệm", "tiền",
    ],
    "fitness": [
        "fitness", "gym", "squat", "coach", "workout", "posture",
        "thể hình", "tập gym", "huấn luyện viên", "tập luyện", "tư thế",
    ],
    "food": [
        "food", "recipe", "banh mi", "bánh mì", "restaurant", "dish", "cook", "sauce",
        "món ăn", "công thức", "phở", "bún", "quán ăn", "nấu", "nước sốt",
    ],
    "gaming": [
        "game", "gaming", "boss", "weapon", "hud", "player", "esports",
        "trò chơi", "vũ khí", "người chơi", "thể thao điện tử",
    ],
    "kids_family": [
        "kids", "child", "toy", "parent", "family", "playtime",
        "trẻ em", "trẻ nhỏ", "đồ chơi", "bố mẹ", "gia đình", "giờ chơi",
    ],
    "lifestyle": [
        "routine", "home", "journal", "reset", "calm", "lifestyle", "room",
        "thói quen", "nhà", "nhật ký", "sống chậm", "phòng",
    ],
    "medical_wellness": [
        "medical", "wellness", "sleep", "clinic", "health", "symptom", "routine",
        "y tế", "sức khỏe", "giấc ngủ", "phòng khám", "triệu chứng",
    ],
    "music_video": [
        "music video", "artist", "dancer", "beat", "neon", "performance",
        "mv", "ca sĩ", "nghệ sĩ", "vũ công", "màn trình diễn",
    ],
    "real_estate": [
        "real estate", "apartment", "property", "tour", "balcony", "bedroom",
        "bất động sản", "căn hộ", "nhà mẫu", "tham quan nhà", "ban công", "phòng ngủ",
    ],
    "restaurant_hospitality": [
        "cafe", "hotel", "hospitality", "espresso", "dessert", "service",
        "quán cafe", "cà phê", "khách sạn", "nhà hàng", "bánh ngọt", "dịch vụ",
    ],
    "tech": [
        "gadget", "camera", "device", "tech", "object detection", "searchable",
        "đồ công nghệ", "máy ảnh", "thiết bị", "điện thoại", "nhận diện vật thể",
    ],
    "travel": [
        "travel", "destination", "da nang", "đà nẵng", "beach", "itinerary",
        "du lịch", "điểm đến", "biển", "lịch trình", "hội an", "sa pa", "phú quốc",
    ],
    "ugc_review": [
        "review", "creator", "test", "portable", "blender", "honest", "tiktok shop",
        "đánh giá", "kiểm chứng", "cầm tay", "máy xay", "thành thật",
    ],
}

_ASCII_KEYWORDS: dict[str, list[str]] = {
    "app_saas": [
        "app ai", "ai app", "shop online", "online shop", "ra mat app", "ra mat ung dung",
        "app giup", "phan mem", "cong cu ai", "dashboard", "crm", "doanh thu",
    ],
    "beauty": [
        "lam dep", "my pham", "cham soc da", "trang diem", "son moi", "kem nen",
        "kem chong nang", "nuoc hoa", "duong toc",
    ],
    "education": ["giai thich", "hoc", "huong dan", "giao duc", "bai hoc", "nghien cuu"],
    "fashion": ["thoi trang", "trang phuc", "vay", "phoi do", "vai"],
    "finance_education": ["tai chinh", "dau tu", "quy du phong", "ngan sach", "tiet kiem", "tien"],
    "fitness": ["the hinh", "tap gym", "huan luyen vien", "tap luyen", "tu the"],
    "food": ["mon an", "cong thuc", "pho", "bun", "quan an", "nau", "nuoc sot"],
    "medical_wellness": ["y te", "suc khoe", "giac ngu", "phong kham", "trieu chung"],
    "real_estate": ["bat dong san", "can ho", "nha mau", "tham quan nha", "ban cong", "phong ngu"],
    "restaurant_hospitality": [
        "quan cafe", "ca phe", "khach san", "nha hang", "quan pho", "khong gian nha hang",
        "banh ngot", "dich vu",
    ],
    "tech": ["do cong nghe", "may anh", "thiet bi", "dien thoai", "nhan dien vat the"],
    "travel": ["du lich", "diem den", "bien", "lich trinh", "hoi an", "sa pa", "phu quoc"],
    "ugc_review": ["danh gia", "kiem chung", "cam tay", "may xay", "thanh that"],
}

for _niche, _keywords in _ASCII_KEYWORDS.items():
    _KEYWORDS.setdefault(_niche, []).extend(_keywords)

_KEYWORDS.setdefault("drama", []).extend([
    "phim ngan",
    "cau chuyen",
    "cot truyen",
    "bi mat gia dinh",
    "co thoai",
    "loi thoai",
    "nhan vat",
    "cam xuc manh",
    "cinematic",
    "short film",
    "family secret",
    "character arc",
    "dialogue scene",
    "reveal",
])

_ASCII_DIALOGUE_TOKENS = {
    "co thoai",
    "loi thoai",
    "thoai tieng viet",
    "noi tieng viet",
    "noi chuyen",
    "noi tu nhien",
    "giong noi",
    "thuyet minh",
    "loi dan",
    "doc thoai",
    "voice tieng viet",
}

_DIALOGUE_TOKENS = {
    "dialogue",
    "talking",
    "explains",
    "explain",
    "voice",
    "voiceover",
    "vo",
    "narration",
    "interview",
    "presenter",
    "spokesperson",
    "lip-sync",
    "lipsync",
    "khớp môi",
    "lời thoại",
    "thuyết minh",
    "nói chuyện",
}

_NICHE_TIE_PRIORITY = {
    "beauty": 30,
    "food": 29,
    "fashion": 28,
    "ecommerce_catalog": 27,
    "app_saas": 26,
    "tech": 25,
    "restaurant_hospitality": 24,
    "real_estate": 23,
    "travel": 22,
    "automotive": 21,
    "fitness": 20,
    "gaming": 19,
    "music_video": 18,
    "education": 17,
    "finance_education": 16,
    "medical_wellness": 15,
    "documentary": 14,
    "kids_family": 13,
    "drama": 12,
    "asmr": 11,
    "lifestyle": 10,
    "ugc_review": 1,
}

_SPECIFIC_NICHE_KEYWORDS: dict[str, list[str]] = {
    "app_saas": [
        "app ai", "ai app", "ai tool", "saas", "shop online", "online shop", "ra mat app",
        "ra mat ung dung", "app giup", "phan mem giup", "cong cu ai", "workflow automation",
        "dashboard", "crm", "doanh thu", "founder ra mat", "founder launch",
    ],
    "beauty": [
        "son môi", "lipstick", "serum", "kem nền", "kem chống nắng", "nước hoa",
        "skincare", "makeup", "mỹ phẩm",
    ],
    "real_estate": ["bất động sản", "căn hộ", "nhà mẫu", "balcony", "bedroom", "property tour"],
    "finance_education": ["quỹ dự phòng", "đầu tư", "ngân sách", "tiết kiệm", "emergency fund"],
    "medical_wellness": ["y tế", "sức khỏe", "triệu chứng", "phòng khám", "clinic"],
    "automotive": ["ô tô", "xe hơi", "xe máy", "engine", "headlight"],
    "fashion": ["thời trang", "outfit", "lookbook", "phối đồ"],
    "travel": ["du lịch", "điểm đến", "lịch trình", "itinerary"],
}


_ASCII_SPECIFIC_NICHE_KEYWORDS: dict[str, list[str]] = {
    "beauty": ["son moi", "son m", "skincare", "makeup", "my pham", "nuoc hoa"],
    "fashion": ["thoi trang", "outfit", "lookbook", "phoi do", "vay"],
    "food": ["mon an", "cong thuc", "pho", "bun", "nuoc sot"],
    "restaurant_hospitality": ["nha hang", "quan pho", "khong gian nha hang", "khach san", "quan cafe"],
    "app_saas": [
        "app ai", "ai app", "ai tool", "saas", "shop online", "online shop", "ra mat app",
        "ra mat ung dung", "app giup", "phan mem giup", "cong cu ai", "workflow automation",
        "dashboard", "crm", "doanh thu", "founder ra mat", "founder launch",
    ],
    "real_estate": ["bat dong san", "can ho", "nha mau", "ban cong", "phong ngu", "property tour"],
}

for _niche, _keywords in _ASCII_SPECIFIC_NICHE_KEYWORDS.items():
    _SPECIFIC_NICHE_KEYWORDS.setdefault(_niche, []).extend(_keywords)

_SPECIFIC_NICHE_KEYWORDS.setdefault("drama", []).extend([
    "phim ngan",
    "short film",
    "cot truyen",
    "cu twist",
    "bi mat gia dinh",
    "family secret",
    "character arc",
    "co thoai",
    "loi thoai",
])


def build_autonomous_production_decision(
    *,
    user_idea: str,
    target_market: str = "auto",
    target_platform: str = "tiktok",
    duration_hint_s: Optional[int] = None,
    reference_counts: Optional[dict[str, int]] = None,
    reference_image_urls: Optional[list[str]] = None,
    reference_video_urls: Optional[list[str]] = None,
    reference_audio_urls: Optional[list[str]] = None,
    reference_manifest: Optional[dict[str, Any]] = None,
    niche_hint: Optional[str] = None,
    speaker_count: int = 1,
    allow_expensive_reasoning: bool = False,
    allow_premium_brain: bool = False,
) -> dict[str, Any]:
    """Return the source-backed workflow decision for an autonomous job."""
    idea = (user_idea or "").strip()
    reference_image_urls = _clean_url_list(reference_image_urls or [], limit=9)
    reference_video_urls = _clean_url_list(reference_video_urls or [], limit=3)
    reference_audio_urls = _clean_url_list(reference_audio_urls or [], limit=3)
    reference_manifest = _clean_reference_manifest(reference_manifest or {})
    reference_counts = reference_counts or {}
    refs = {
        "images": max(_reference_count(reference_counts, "images", "image"), len(reference_image_urls)),
        "videos": max(_reference_count(reference_counts, "videos", "video"), len(reference_video_urls)),
        "audios": max(_reference_count(reference_counts, "audios", "audio"), len(reference_audio_urls)),
        "pinned_assets": _reference_count(reference_counts, "pinned_assets", "pinned"),
    }
    reference_context = {
        "image_urls": reference_image_urls,
        "video_urls": reference_video_urls,
        "audio_urls": reference_audio_urls,
        "reference_manifest": reference_manifest,
        "manifest_confirmed": bool(reference_manifest.get("confirmed")) if reference_manifest else False,
        "vision_scan_recommended": bool(reference_image_urls),
        "motion_reference_scan_recommended": bool(reference_video_urls),
        "audio_reference_scan_recommended": bool(reference_audio_urls),
    }
    creative_brief_contract = build_creative_brief_contract(
        user_idea=idea,
        target_market=target_market,
        target_platform=target_platform,
        duration_hint_s=duration_hint_s,
        reference_counts=refs,
    )
    parsed_duration_s = (
        (creative_brief_contract.get("parsed") or {})
        .get("duration", {})
        .get("requested_s")
    )
    parsed_platform = str((creative_brief_contract.get("parsed") or {}).get("target_platform") or "")
    parsed_platform_source = str(
        (creative_brief_contract.get("parsed") or {}).get("target_platform_source") or ""
    )
    effective_target_platform = (
        parsed_platform
        if parsed_platform and parsed_platform_source == "prompt_text"
        else target_platform or "tiktok"
    )
    effective_duration_hint_s = duration_hint_s or parsed_duration_s
    niche_resolution = _resolve_niche_with_evidence(
        idea,
        niche_hint,
        duration_hint_s=effective_duration_hint_s,
        reference_counts=refs,
    )
    niche = str(niche_resolution["selected_niche"])
    market_inference = infer_target_market(idea, target_market)
    effective_target_market = str(market_inference["effective_target_market"])
    duration = _resolve_duration(effective_duration_hint_s, effective_target_platform, niche)
    runtime = plan_runtime_structure(duration, niche=niche, platform=effective_target_platform)
    runtime_payload = runtime.model_dump()
    market = get_market_playbook(effective_target_market)
    playbook = get_niche_playbook(niche)
    benchmark = get_benchmark_case(niche)
    readiness_row = _readiness_row(niche)
    has_dialogue = _detect_dialogue(idea, refs, niche, duration, speaker_count=speaker_count)
    responsible_content_gate = build_responsible_content_gate(
        user_idea=idea,
        target_market=effective_target_market,
        has_dialogue=has_dialogue,
        reference_counts=refs,
    )
    dialogue = build_dialogue_route_policy(
        niche=niche,
        target_market=effective_target_market,
        duration_s=duration,
        has_dialogue=has_dialogue,
        reference_audio_count=refs["audios"],
        speaker_count=speaker_count,
    ).model_dump()

    model_route = _model_route(niche, runtime_payload["runtime_class"], refs, has_dialogue)
    graph_required = duration > 180
    seedance_contract = _seedance_contract(runtime_payload["runtime_class"], refs)
    niche_resolution_review_required = _niche_resolution_review_required(niche_resolution)
    qa_gates = _qa_gates(
        niche,
        runtime_payload["runtime_class"],
        refs,
        has_dialogue,
        niche_resolution=niche_resolution,
    )
    long_form_preview = _long_form_scene_preview(
        user_idea=idea,
        runtime_payload=runtime_payload,
        niche_playbook=playbook,
    )
    creative_treatment_search = build_creative_treatment_search(
        user_idea=idea,
        niche=niche,
        target_market=effective_target_market,
        target_platform=effective_target_platform,
        runtime_payload=runtime_payload,
        reference_counts=refs,
        niche_playbook=playbook,
        market_playbook=market,
        has_dialogue=has_dialogue,
    )
    selected_creative_treatment = _selected_creative_treatment(creative_treatment_search)
    seedance_reference_allocation = build_seedance_reference_allocation(
        niche=niche,
        runtime_payload={**runtime_payload, "target_market": effective_target_market},
        reference_counts=refs,
        has_dialogue=has_dialogue,
        creative_treatment=selected_creative_treatment,
        reference_manifest=reference_manifest,
    )
    reference_sufficiency = build_reference_sufficiency_report(
        niche=niche,
        runtime_payload={**runtime_payload, "target_market": effective_target_market},
        reference_counts=refs,
        has_dialogue=has_dialogue,
        target_market=effective_target_market,
    )
    niche_execution_rubric = build_niche_execution_rubric(
        niche=niche,
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
    )
    niche_runtime_director = build_niche_runtime_director_contract(
        niche=niche,
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
        target_platform=effective_target_platform,
        has_dialogue=has_dialogue,
        reference_counts=refs,
    )
    cinematic_grammar = build_cinematic_grammar_contract(
        niche=niche,
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
        creative_treatment=selected_creative_treatment,
    )
    niche_production_recipe = build_niche_production_recipe(
        niche=niche,
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
        target_platform=effective_target_platform,
        niche_playbook=playbook,
        reference_counts=refs,
        has_dialogue=has_dialogue,
        selected_creative_treatment=selected_creative_treatment,
    )
    seedance_prompt_formula = build_seedance_prompt_formula(
        niche=niche,
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
        target_platform=effective_target_platform,
        has_dialogue=has_dialogue,
        reference_allocation=seedance_reference_allocation,
        niche_production_recipe=niche_production_recipe,
    )
    model_route_strategy = build_model_route_strategy(
        niche=niche,
        target_market=effective_target_market,
        target_platform=effective_target_platform,
        duration_s=duration,
        runtime_payload=runtime_payload,
        reference_counts=refs,
        has_dialogue=has_dialogue,
        speaker_count=speaker_count,
        creative_treatment=selected_creative_treatment,
    )
    model_route = _normalize_primary_model_route(model_route, model_route_strategy)
    seedance_segment_inspector = _seedance_segment_inspector(
        user_idea=idea,
        niche=niche,
        target_market=effective_target_market,
        runtime_payload=runtime_payload,
        niche_playbook=playbook,
        market_playbook=market,
        seedance_reference_allocation=seedance_reference_allocation,
        long_form_preview=long_form_preview,
        selected_creative_treatment=selected_creative_treatment,
        model_route_strategy=model_route_strategy,
        has_dialogue=has_dialogue,
    )
    creative_producer_v2 = build_creative_producer_v2(
        user_idea=idea,
        creative_brief_contract=creative_brief_contract,
        decision={
            "niche": niche,
            "runtime_class": runtime_payload["runtime_class"],
            "target_duration_s": duration,
            "target_platform": effective_target_platform,
        },
        creative_treatment_search=creative_treatment_search,
        seedance_segment_inspector=seedance_segment_inspector,
        reference_counts=refs,
    )
    autonomous_input_upgrade_plan = _autonomous_input_upgrade_plan(
        niche=niche,
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
        has_dialogue=has_dialogue,
        reference_sufficiency=reference_sufficiency,
        niche_production_recipe=niche_production_recipe,
        route_quality_scorecard=None,
        segment_inspector=seedance_segment_inspector,
    )
    base_decision = {
        "decision": {
            "niche": niche,
            "readiness": readiness_row.get("readiness"),
            "target_market": effective_target_market,
            "requested_target_market": target_market or "auto",
            "target_duration_s": duration,
            "target_platform": effective_target_platform,
            "runtime_class": runtime_payload["runtime_class"],
            "execution_mode": (
                "graph_executor_long_form_when_flagged" if graph_required else "linear_worker_short_form"
            ),
            "graph_required": graph_required,
            "dialogue_required": has_dialogue,
            "niche_resolution_review_required": niche_resolution_review_required,
            "responsible_review_required": bool(responsible_content_gate.get("manual_review_required")),
            "render_blocked_by_responsible_gate": not bool(responsible_content_gate.get("render_allowed", True)),
            "primary_model_route": model_route,
            "dialogue_route_policy": dialogue,
            "seedance_contract": seedance_contract,
            "reference_context": reference_context,
            "benchmark_required_before_top_tier_claim": _benchmark_required(
                readiness_row.get("readiness"), graph_required, dialogue
            ) or niche_resolution_review_required,
        }
    }
    llm_brain_policy = build_llm_brain_policy(
        user_idea=idea,
        target_market=effective_target_market,
        target_platform=effective_target_platform,
        duration_s=duration,
        runtime_class=runtime_payload["runtime_class"],
        reference_counts=refs,
        niche=niche,
        has_dialogue=has_dialogue,
        speaker_count=speaker_count,
        graph_required=graph_required,
        niche_resolution_review_required=niche_resolution_review_required,
        responsible_review_required=bool(responsible_content_gate.get("manual_review_required")),
        allow_expensive_reasoning=allow_expensive_reasoning,
        allow_premium_brain=allow_premium_brain,
    )
    base_decision["decision"]["llm_brain_route"] = llm_brain_policy["route_summary"]
    route_quality_scorecard = build_route_quality_scorecard(
        decision=base_decision,
        reference_sufficiency=reference_sufficiency,
        niche_runtime_director=niche_runtime_director,
        model_route_strategy=model_route_strategy,
    )
    autonomous_input_upgrade_plan = _autonomous_input_upgrade_plan(
        niche=niche,
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
        has_dialogue=has_dialogue,
        reference_sufficiency=reference_sufficiency,
        niche_production_recipe=niche_production_recipe,
        route_quality_scorecard=route_quality_scorecard,
        segment_inspector=seedance_segment_inspector,
    )
    long_form_execution_gate = build_long_form_execution_gate(
        duration_s=duration,
        runtime_payload=runtime_payload,
        production_graph=None,
        scene_memory_pack=None,
        shots=None,
        graph_executor_enabled=None,
        route_quality_scorecard=route_quality_scorecard,
    )
    script_asset_sop = build_script_asset_sop(
        user_idea=idea,
        niche=niche,
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
        reference_counts=refs,
        has_dialogue=has_dialogue,
    )
    asset_bible_completion_policy = build_asset_bible_completion_policy(
        script_asset_sop=script_asset_sop,
        runtime_payload=runtime_payload,
        reference_counts=refs,
        route_quality_scorecard=route_quality_scorecard,
    )
    hero_shot_candidate_policy = build_hero_shot_candidate_policy(
        niche=niche,
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
        reference_counts=refs,
        has_dialogue=has_dialogue,
        seedance_segment_inspector=seedance_segment_inspector,
        route_quality_scorecard=route_quality_scorecard,
    )
    long_form_error_recycling_policy = build_long_form_error_recycling_policy(
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
        has_dialogue=has_dialogue,
        seedance_segment_inspector=seedance_segment_inspector,
        hero_shot_candidate_policy=hero_shot_candidate_policy,
        route_quality_scorecard=route_quality_scorecard,
    )
    prompt_template_bank_policy = build_prompt_template_bank_policy(
        niche=niche,
        runtime_payload=runtime_payload,
        target_market=effective_target_market,
        target_platform=effective_target_platform,
        seedance_prompt_formula=seedance_prompt_formula,
        model_route_strategy=model_route_strategy,
        route_quality_scorecard=route_quality_scorecard,
    )
    prompt_execution_contract_v3 = build_prompt_execution_contract_v3(
        user_idea=idea,
        creative_brief_contract=creative_brief_contract,
        creative_producer_v2=creative_producer_v2,
        decision=base_decision["decision"],
        seedance_prompt_formula=seedance_prompt_formula,
        seedance_reference_allocation=seedance_reference_allocation,
        model_route_strategy=model_route_strategy,
        llm_brain_policy=llm_brain_policy,
    )
    viral_creative_brain = build_viral_creative_brain(
        user_idea=idea,
        creative_brief_contract=creative_brief_contract,
        creative_producer_v2=creative_producer_v2,
        prompt_execution_contract_v3=prompt_execution_contract_v3,
        decision=base_decision["decision"],
        creative_treatment_search=creative_treatment_search,
        niche_playbook=playbook,
        market_playbook=market,
    )
    output_qa_retry_brain = build_output_qa_retry_brain(
        user_idea=idea,
        creative_brief_contract=creative_brief_contract,
        creative_producer_v2=creative_producer_v2,
        prompt_execution_contract_v3=prompt_execution_contract_v3,
        viral_creative_brain=viral_creative_brain,
        decision=base_decision["decision"],
    )

    return {
        "schema_version": "cinejelly.autonomous_production_decision.v1",
        "input_summary": {
            "idea_chars": len(idea),
            "target_market": effective_target_market,
            "requested_target_market": target_market or "auto",
            "market_inference": market_inference,
            "target_platform": effective_target_platform,
            "requested_target_platform": target_platform or "tiktok",
            "parsed_target_platform": parsed_platform or None,
            "parsed_target_platform_source": parsed_platform_source or None,
            "duration_hint_s": duration_hint_s,
            "parsed_duration_hint_s": parsed_duration_s,
            "effective_duration_hint_s": effective_duration_hint_s,
            "reference_counts": refs,
            "reference_context": reference_context,
            "niche_resolution": niche_resolution,
            "niche_hint": niche_hint,
            "speaker_count": speaker_count,
        },
        "decision": base_decision["decision"],
        "creative_brief_contract": creative_brief_contract,
        "creative_producer_v2": creative_producer_v2,
        "llm_brain_policy": llm_brain_policy,
        "workflow_steps": _workflow_steps(
            runtime_class=runtime_payload["runtime_class"],
            graph_required=graph_required,
            has_dialogue=has_dialogue,
        ),
        "model_route_strategy": model_route_strategy,
        "creative_treatment_search": creative_treatment_search,
        "hero_shot_candidate_policy": hero_shot_candidate_policy,
        "long_form_error_recycling_policy": long_form_error_recycling_policy,
        "prompt_template_bank_policy": prompt_template_bank_policy,
        "prompt_execution_contract_v3": prompt_execution_contract_v3,
        "viral_creative_brain": viral_creative_brain,
        "output_qa_retry_brain": output_qa_retry_brain,
        "seedance_reference_allocation": seedance_reference_allocation,
        "seedance_segment_inspector": seedance_segment_inspector,
        "seedance_prompt_formula": seedance_prompt_formula,
        "script_asset_sop": script_asset_sop,
        "asset_bible_completion_policy": asset_bible_completion_policy,
        "responsible_content_gate": responsible_content_gate,
        "autonomous_input_upgrade_plan": autonomous_input_upgrade_plan,
        "reference_sufficiency": reference_sufficiency,
        "niche_execution_rubric": niche_execution_rubric,
        "niche_runtime_director": niche_runtime_director,
        "niche_production_recipe": niche_production_recipe,
        "cinematic_grammar": cinematic_grammar,
        "route_quality_scorecard": route_quality_scorecard,
        "long_form_execution_gate": long_form_execution_gate,
        "runtime_structure": runtime_payload,
        "long_form_scene_preview": long_form_preview,
        "market_playbook": {
            "requested_target_market": target_market or "auto",
            "target_market": market.get("target_market"),
            "market_inference": market_inference,
            "primary_language": market.get("primary_language"),
            "caption_language": market.get("caption_language"),
            "hook_style": market.get("hook_style"),
            "dialogue_style": market.get("dialogue_style"),
            "claim_style": market.get("claim_style"),
            "seedance_notes": market.get("seedance_notes", []),
        },
        "niche_playbook": {
            "best_for": playbook.get("best_for"),
            "hook_moves": playbook.get("hook_moves", [])[:4],
            "beat_flow": playbook.get("beat_flow", []),
            "camera": playbook.get("camera", [])[:5],
            "audio": playbook.get("audio"),
            "quality_bar": playbook.get("quality_bar", []),
            "safety_rules": playbook.get("safety_rules", []),
        },
        "qa_gates": qa_gates,
        "benchmark_reference": {
            "case_id": f"bench_{niche}",
            "idea": benchmark.get("idea"),
            "target_market": benchmark.get("target_market"),
            "duration_hint_s": benchmark.get("duration_hint_s"),
            "reference_strategy": benchmark.get("reference_strategy", []),
            "success_criteria": benchmark.get("success_criteria", []),
        },
        "readiness": readiness_row,
    }


def _reference_count(counts: dict[str, int], *keys: str) -> int:
    for key in keys:
        if key in counts:
            return max(0, int(counts.get(key) or 0))
    return 0


def _clean_url_list(values: list[str], *, limit: int) -> list[str]:
    out: list[str] = []
    for value in values[: max(0, limit)]:
        text = str(value or "").strip()
        if not text:
            continue
        if text.startswith(("http://", "https://", "data:image/", "data:video/", "data:audio/")):
            out.append(text)
    return out


def _clean_reference_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return {}
    raw_items = manifest.get("items") or []
    if not isinstance(raw_items, list):
        raw_items = []
    items: list[dict[str, Any]] = []
    for raw in raw_items[:12]:
        if not isinstance(raw, dict):
            continue
        tag = str(raw.get("tag") or "").strip()[:24]
        kind = str(raw.get("kind") or "").strip().lower()
        role = str(raw.get("role") or "unknown").strip().lower()[:60]
        url = str(raw.get("url") or "").strip()
        if kind not in {"image", "video", "audio"} or not tag.startswith("@"):
            continue
        if url and not url.startswith(("http://", "https://", "data:image/", "data:video/", "data:audio/")):
            url = ""
        item = {
            "tag": tag,
            "kind": kind,
            "role": role or "unknown",
            "role_confirmed": bool(raw.get("role_confirmed")),
            "role_source": str(raw.get("role_source") or "auto").strip().lower()[:20],
            "name": str(raw.get("name") or "").strip()[:160],
            "url": url,
            "prompt_binding": str(raw.get("prompt_binding") or "").strip()[:260],
        }
        items.append(item)
    return {
        "schema_version": "cinejelly.reference_manifest.v1",
        "confirmed": bool(manifest.get("confirmed")) and all(item["role_confirmed"] for item in items),
        "items": items,
        "images": [item for item in items if item["kind"] == "image"],
        "videos": [item for item in items if item["kind"] == "video"],
        "audios": [item for item in items if item["kind"] == "audio"],
        "instruction": (
            "Use every @reference only for its assigned role. Never swap product, "
            "character, style, camera, motion, beat, SFX or voice responsibilities."
        ),
    }


def _resolve_niche(user_idea: str, niche_hint: Optional[str]) -> str:
    return str(_resolve_niche_with_evidence(user_idea, niche_hint)["selected_niche"])


def _resolve_niche_with_evidence(
    user_idea: str,
    niche_hint: Optional[str],
    *,
    duration_hint_s: Optional[int] = None,
    reference_counts: Optional[dict[str, int]] = None,
) -> dict[str, Any]:
    supported = set(list_niche_keys())
    hint = (niche_hint or "").strip().lower()
    if hint in supported:
        return {
            "selected_niche": hint,
            "source": "explicit_niche_hint",
            "confidence": 1.0,
            "scores": [{"niche": hint, "score": 999, "hits": ["niche_hint"], "specific_hits": []}],
            "fallback_reason": None,
            "clarifying_questions": [],
            "suggested_brief_signals": [],
            "suggested_brief_template": "",
        }
    text = _normalize_match_text(user_idea)
    rows: list[dict[str, Any]] = []
    for niche, keywords in _KEYWORDS.items():
        hits = _keyword_hits(keywords, text)
        specific_hits = _keyword_hits(_SPECIFIC_NICHE_KEYWORDS.get(niche, []), text)
        score = len(hits) + 3 * len(specific_hits)
        if niche == "drama":
            drama_bonus = _drama_narrative_bonus(text, duration_hint_s)
            if drama_bonus:
                score += drama_bonus
                specific_hits = [*specific_hits, "narrative_short_film_signal"]
        if score:
            rows.append({
                "niche": niche,
                "score": score,
                "tie_priority": _NICHE_TIE_PRIORITY.get(niche, 0),
                "hits": hits[:12],
                "specific_hits": specific_hits[:12],
            })
    rows.sort(key=lambda item: (item["score"], item["tie_priority"]), reverse=True)
    if rows:
        top = rows[0]
        runner_up = rows[1] if len(rows) > 1 else None
        margin = int(top["score"]) - int(runner_up["score"]) if runner_up else int(top["score"])
        confidence = 0.95 if margin >= 3 else 0.82 if margin >= 1 else 0.68
        needs_clarification = confidence < 0.75 or margin == 0
        return {
            "selected_niche": top["niche"],
            "source": "keyword_score",
            "confidence": confidence,
            "scores": rows[:6],
            "fallback_reason": None,
            "clarifying_questions": _niche_clarifying_questions(rows[:3]) if needs_clarification else [],
            "suggested_brief_signals": _suggested_brief_signals(rows[:3]) if needs_clarification else [],
            "suggested_brief_template": _suggested_brief_template(rows[:3]) if needs_clarification else "",
        }
    if _looks_like_reference_product_request(text, reference_counts or {}):
        return {
            "selected_niche": "ugc_review",
            "source": "reference_product_fallback",
            "confidence": 0.82,
            "scores": [{
                "niche": "ugc_review",
                "score": 3,
                "hits": ["image_reference", "product_subject"],
                "specific_hits": ["product_in_reference"],
            }],
            "fallback_reason": "image reference plus product-in-image wording",
            "clarifying_questions": [],
            "suggested_brief_signals": ["reference image role", "viewer payoff", "proof/result"],
            "suggested_brief_template": "",
        }
    fallback = "ugc_review" if _looks_commercial(text) else "lifestyle"
    return {
        "selected_niche": fallback,
        "source": "commercial_fallback" if fallback == "ugc_review" else "lifestyle_fallback",
        "confidence": 0.45,
        "scores": [],
        "fallback_reason": "commercial terms detected" if fallback == "ugc_review" else "no niche keyword match",
        "clarifying_questions": _niche_clarifying_questions([]),
        "suggested_brief_signals": _suggested_brief_signals([]),
        "suggested_brief_template": _suggested_brief_template([]),
    }


def _drama_narrative_bonus(text: str, duration_hint_s: Optional[int]) -> int:
    """Prefer story genre over object/context keywords for explicit short films."""
    negated_genre_terms = [
        "not fictional drama",
        "not drama",
        "not a drama",
        "not short drama",
        "khong phai drama",
        "khong phai phim ngan",
    ]
    if any(_normalize_match_text(term) in text for term in negated_genre_terms):
        return 0

    explicit_genre_terms = [
        "short drama",
        "mini drama",
        "drama about",
        "a drama",
        "drama ve",
        "phim ngan",
        "short film",
    ]
    if any(_normalize_match_text(term) in text for term in explicit_genre_terms):
        return 8 if duration_hint_s and int(duration_hint_s) >= 180 else 4

    narrative_terms = [
        "drama",
        "short film",
        "short drama",
        "phim ngan",
        "story",
        "cau chuyen",
        "cot truyen",
        "family secret",
        "bi mat gia dinh",
        "character arc",
        "cinematic",
        "co thoai",
        "loi thoai",
        "twist",
        "reveal",
    ]
    hits = sum(1 for term in narrative_terms if _normalize_match_text(term) in text)
    if hits < 2:
        return 0
    if duration_hint_s and int(duration_hint_s) >= 180:
        return 6
    return 3


def _resolve_duration(duration_hint_s: Optional[int], target_platform: str, niche: str) -> int:
    if duration_hint_s:
        return max(4, min(int(duration_hint_s), 1800))
    platform = (target_platform or "tiktok").lower()
    if platform in {"youtube_long", "facebook"}:
        return 120 if niche not in {"drama", "documentary"} else 300
    if niche in {"education", "travel", "documentary"}:
        return 60
    if niche == "drama":
        return 120
    return 30


def _detect_dialogue(
    user_idea: str,
    refs: dict[str, int],
    niche: str,
    duration_s: int,
    *,
    speaker_count: int = 1,
) -> bool:
    text = _normalize_match_text(user_idea)
    token_hit = any(_normalize_match_text(token) in text for token in (_DIALOGUE_TOKENS | _ASCII_DIALOGUE_TOKENS))
    return bool(
        token_hit
        or (duration_s > 180 and niche in {"education", "documentary"})
        or (speaker_count > 1 and duration_s > 60 and niche in {"drama", "education", "documentary"})
    )


def _niche_resolution_review_required(niche_resolution: dict[str, Any]) -> bool:
    confidence = float(niche_resolution.get("confidence") or 0.0)
    source = str(niche_resolution.get("source") or "")
    scores = list(niche_resolution.get("scores") or [])
    if source.endswith("_fallback") or confidence < 0.75:
        return True
    if len(scores) >= 2:
        top_score = int(scores[0].get("score") or 0)
        runner_score = int(scores[1].get("score") or 0)
        return top_score == runner_score
    return False


def _niche_clarifying_questions(top_scores: list[dict[str, Any]]) -> list[str]:
    candidates = [str(item.get("niche") or "").replace("_", " ") for item in top_scores if item.get("niche")]
    if candidates:
        return [
            f"Should this be treated primarily as {', '.join(candidates[:3])}?",
            "What exact product, service, place, character, or story conflict must stay consistent?",
            "What result should viewers understand in the first 3 seconds?",
        ]
    return [
        "What is the primary niche: product review, app demo, food, beauty, education, drama, travel, or another category?",
        "What exact product, service, place, character, or story conflict must stay consistent?",
        "What result should viewers understand in the first 3 seconds?",
    ]


def _suggested_brief_signals(top_scores: list[dict[str, Any]]) -> list[str]:
    candidates = [str(item.get("niche") or "") for item in top_scores if item.get("niche")]
    signals = [
        "primary niche",
        "target viewer",
        "specific product/service/person/place",
        "desired proof or payoff",
        "reference roles for image/video/audio",
    ]
    if "app_saas" in candidates:
        signals.extend(["app feature", "dashboard/result metric", "workflow before-after"])
    if "food" in candidates or "restaurant_hospitality" in candidates:
        signals.extend(["signature dish/place", "texture or ambience", "visit/order CTA"])
    if "beauty" in candidates or "fashion" in candidates:
        signals.extend(["hero product/look", "texture/material detail", "before-after or reveal"])
    return list(dict.fromkeys(signals))[:10]


def _suggested_brief_template(top_scores: list[dict[str, Any]]) -> str:
    candidates = [
        str(item.get("niche") or "").replace("_", " ")
        for item in top_scores
        if item.get("niche")
    ]
    niche_hint = " / ".join(candidates[:3]) if candidates else "product review / app demo / food / beauty / education / drama / travel"
    return (
        f"Niche: {niche_hint}. Main subject: __. Target viewer: __. "
        "Target market/language: __. First 3s proof or hook: __. "
        "References: image=__, video=__, audio=__. Final payoff or CTA: __."
    )


def _model_route(niche: str, runtime_class: str, refs: dict[str, int], has_dialogue: bool) -> dict[str, Any]:
    primary = "seedance_2_0_fast_ref" if refs.get("images", 0) or refs.get("videos", 0) or refs.get("audios", 0) else "seedance_2_0_fast_t2v"
    if niche in {"beauty", "fashion", "food", "ecommerce_catalog"}:
        primary = "seedance_2_0_ref"
    notes = ["internal-only route; do not expose model picker on the one-click UI"]
    if runtime_class in {"short_film", "episode"}:
        notes.append("split into graph-managed 4-15s Seedance shots")
    elif runtime_class == "short":
        notes.append("single-call multi-shot allowed only when total duration <=15s and scene is coherent")
    if has_dialogue:
        notes.append("visible speech uses dialogue route policy; Seedance remains visual coverage")
    return {
        "primary_visual_model": primary,
        "continuity_model": "seedance_2_0_fast_i2v",
        "premium_visual_model": "seedance_2_0_ref",
        "notes": notes,
    }


def _normalize_primary_model_route(
    model_route: dict[str, Any],
    model_route_strategy: dict[str, Any],
) -> dict[str, Any]:
    """Make the strategy summary the single source of truth for preview routes."""
    route = dict(model_route or {})
    summary = (model_route_strategy or {}).get("summary") or {}
    strategy_primary = str(summary.get("primary_visual_model") or "").strip()
    if strategy_primary:
        legacy_primary = route.get("primary_visual_model")
        route["primary_visual_model"] = strategy_primary
        route["route_source_of_truth"] = "model_route_strategy.summary"
        if legacy_primary and legacy_primary != strategy_primary:
            route["legacy_primary_visual_model"] = legacy_primary
            notes = list(route.get("notes") or [])
            notes.append(
                f"legacy heuristic suggested {legacy_primary}; normalized to {strategy_primary} from model_route_strategy"
            )
            route["notes"] = notes
    if summary.get("continuity_model"):
        route["continuity_model"] = summary.get("continuity_model")
    if summary.get("premium_visual_model"):
        route["premium_visual_model"] = summary.get("premium_visual_model")
    if summary.get("draft_visual_model"):
        route["draft_visual_model"] = summary.get("draft_visual_model")
    return route


def _seedance_contract(runtime_class: str, refs: dict[str, int]) -> dict[str, Any]:
    return {
        "single_call_max_s": 15,
        "shot_duration_s": "4-15",
        "image_reference_cap": 9,
        "video_reference_cap": 3,
        "audio_reference_cap": 3,
        "input_refs_fit": {
            "images": refs.get("images", 0) <= 9,
            "videos": refs.get("videos", 0) <= 3,
            "audios": refs.get("audios", 0) <= 3,
        },
        "strategy": (
            "single-call multi-shot only for <=15s coherent scene"
            if runtime_class == "short"
            else "per-shot/chunk graph; never one long Seedance request"
        ),
    }


def _qa_gates(
    niche: str,
    runtime_class: str,
    refs: dict[str, int],
    has_dialogue: bool,
    *,
    niche_resolution: Optional[dict[str, Any]] = None,
) -> list[str]:
    gates = [
        "planner: niche, hook, market, and duration are coherent",
        "reference manifest: every uploaded ref has a role and per-shot job",
        "prompt: subject/action/setting/camera/lighting/motion/audio are explicit",
        "render: every Seedance call stays within 4-15s",
        "media QA: ffprobe duration/codec/audio stream checks",
        "visual QA: sampled frames check identity/product/style drift",
    ]
    if refs.get("audios", 0) or has_dialogue:
        gates.append("audio QA: loudness, silence, SFX/voice fit, and lip-sync review")
    if runtime_class in {"short_film", "episode"}:
        gates.extend([
            "graph QA: failed shot/chunk can resume without regenerating whole film",
            "assembly QA: pacing, scene handoff, continuity anchors, and final duration",
        ])
    if niche_resolution and _niche_resolution_review_required(niche_resolution):
        gates.append("niche resolution: clarify or review ambiguous brief before paid render")
    if niche in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        gates.append("safety review: claims, child-safe framing, or documentary fact framing")
    return gates


def _workflow_steps(*, runtime_class: str, graph_required: bool, has_dialogue: bool) -> list[dict[str, Any]]:
    steps = [
        {"step": 1, "name": "intake", "owner": "producer", "output": "idea, market, runtime, refs"},
        {"step": 2, "name": "planner", "owner": "creative strategist", "output": "niche, hook 3s, mood, platform format"},
        {"step": 3, "name": "reference manifest", "owner": "casting/art director", "output": "image/video/audio jobs and per-shot ref policy"},
        {"step": 4, "name": "script asset SOP", "owner": "casting/art director", "output": "character/location/prop/style/voice asset checklist"},
        {"step": 5, "name": "treatment", "owner": "director/producer/editor", "output": "story engine, camera grammar, edit rhythm, QA risks"},
        {"step": 6, "name": "screenplay/storyboard", "owner": "screenwriter", "output": "scenes/chunks/shots with continuity bible"},
        {"step": 7, "name": "prompt compiler", "owner": "cinematographer", "output": "Seedance-ready shot prompts"},
    ]
    if has_dialogue:
        steps.append({"step": 8, "name": "dialogue lane", "owner": "voice/dialogue producer", "output": "Wan/InfiniteTalk/MultiTalk/LipSync candidate decision"})
    steps.append({
        "step": 9,
        "name": "render",
        "owner": "render producer",
        "output": "graph-managed shots" if graph_required else "linear per-shot clips",
    })
    steps.extend([
        {"step": 10, "name": "qa/retry", "owner": "QA supervisor", "output": "pass/warn/fail, retry only failed units"},
        {"step": 11, "name": "assembly/editor", "owner": "editor", "output": "final MP4, caption, hashtags, production evidence"},
    ])
    return steps


def _long_form_scene_preview(
    *,
    user_idea: str,
    runtime_payload: dict[str, Any],
    niche_playbook: dict[str, Any],
) -> dict[str, Any]:
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    if runtime_class in {"short", "sequence"}:
        return {
            "enabled": False,
            "reason": "short_runtime",
            "scene_blueprints": [],
            "screenplay_plan": {},
        }

    hook = _preview_hook(niche_playbook)
    scene_blueprints = plan_scene_blueprints(
        user_idea=user_idea,
        runtime_structure=runtime_payload,
        niche_playbook=niche_playbook,
        planner_hook=hook,
    )
    screenplay = plan_screenplay(
        user_idea=user_idea,
        runtime_structure=runtime_payload,
        scene_blueprints=scene_blueprints,
        niche_playbook=niche_playbook,
        hook_first_3s=hook,
        primary_emotion="curiosity",
    )
    scene_scripts_by_id = {
        scene["scene_id"]: scene
        for scene in screenplay.model_dump().get("scene_scripts", [])
    }
    scenes: list[dict[str, Any]] = []
    for scene in scene_blueprints:
        payload = scene.model_dump()
        script = scene_scripts_by_id.get(scene.scene_id) or {}
        render_plan = _scene_seedance_render_plan(
            scene_index=int(payload.get("index") or 0),
            duration_s=int(payload.get("duration_s") or 15),
            reference_priorities=script.get("reference_priorities", []),
        )
        scenes.append({
            **payload,
            "seedance_render_plan": render_plan,
            "conflict": script.get("conflict"),
            "turning_point": script.get("turning_point"),
            "opening_image": script.get("opening_image"),
            "closing_image": script.get("closing_image"),
            "dialogue_or_vo_intent": script.get("dialogue_or_vo_intent"),
            "reference_priorities": script.get("reference_priorities", []),
            "qa_focus": script.get("qa_focus", []),
        })
    return {
        "enabled": True,
        "scene_count": len(scenes),
        "estimated_seedance_units": sum(
            int((scene.get("seedance_render_plan") or {}).get("estimated_units") or 0)
            for scene in scenes
        ),
        "logline": screenplay.logline,
        "editor_promise": screenplay.editor_promise,
        "continuity_contract": screenplay.continuity_contract,
        "scene_blueprints": scenes,
    }


def _scene_seedance_render_plan(
    *,
    scene_index: int,
    duration_s: int,
    reference_priorities: list[str],
) -> dict[str, Any]:
    duration = max(4, int(duration_s or 4))
    estimated_units = max(1, ceil(duration / 12))
    target_unit_duration = max(4, min(15, ceil(duration / estimated_units)))
    return {
        "estimated_units": estimated_units,
        "target_unit_duration_s": target_unit_duration,
        "min_units_by_15s_cap": max(1, ceil(duration / 15)),
        "max_units_by_4s_floor": max(1, floor(duration / 4)),
        "unit_duration_contract_s": [4, 15],
        "continuity_mode": (
            "establish_anchor_refs" if scene_index == 0 else "previous_scene_final_frame_plus_anchor_refs"
        ),
        "reference_policy": reference_priorities or [
            "character/product identity refs",
            "style reference",
            "video/audio refs when available",
        ],
        "retry_scope": "retry_failed_units_only",
    }


def _seedance_segment_inspector(
    *,
    user_idea: str,
    niche: str,
    target_market: str,
    runtime_payload: dict[str, Any],
    niche_playbook: dict[str, Any],
    market_playbook: dict[str, Any],
    seedance_reference_allocation: dict[str, Any],
    long_form_preview: dict[str, Any],
    selected_creative_treatment: dict[str, Any],
    model_route_strategy: dict[str, Any],
    has_dialogue: bool,
) -> dict[str, Any]:
    """Build a vendor-free preview of how Seedance units will be directed.

    This is not the final LLM prompt. It is an inspectable production contract
    modeled after Seedance omni workflows: each 4-15s segment gets a purpose,
    explicit reference jobs, camera/action/sound guidance, continuity anchor,
    model lane, and QA checks before a paid render.
    """
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    total_duration = max(4, int(runtime_payload.get("target_duration_s") or 30))
    unit_target = int(
        ((model_route_strategy.get("seedance_execution") or {}).get("unit_duration_s"))
        or 12
    )
    unit_target = max(4, min(15, unit_target))
    ref_jobs = _segment_reference_jobs(seedance_reference_allocation)
    policy = seedance_reference_allocation.get("per_shot_policy") or []
    segments: list[dict[str, Any]] = []

    if long_form_preview.get("enabled"):
        for scene in (long_form_preview.get("scene_blueprints") or [])[:4]:
            render_plan = scene.get("seedance_render_plan") or {}
            target_duration = max(4, min(15, int(render_plan.get("target_unit_duration_s") or unit_target)))
            policy_row = _policy_for_segment(policy, len(segments))
            segments.append(_segment_row(
                segment_id=f"scene_{int(scene.get('index') or len(segments) + 1):02d}_unit_01",
                source_scene_id=str(scene.get("scene_id") or ""),
                unit_index=1,
                target_duration_s=target_duration,
                shot_type=str(policy_row.get("shot_type") or "scene_handoff"),
                purpose=str(scene.get("purpose") or scene.get("beat") or "advance the scene"),
                hook_or_turn=str(scene.get("turning_point") or scene.get("visual_hook") or ""),
                action=str(scene.get("closing_image") or scene.get("opening_image") or user_idea),
                camera=_camera_line(niche_playbook, selected_creative_treatment, len(segments)),
                sound=_sound_line_preview(market_playbook, niche_playbook, has_dialogue),
                use_refs=list(policy_row.get("use_refs") or []) or list(render_plan.get("reference_policy") or [])[:4],
                reference_jobs=ref_jobs,
                continuity_anchor=str(render_plan.get("continuity_mode") or "previous frame plus anchors"),
                model_route=str((model_route_strategy.get("summary") or {}).get("primary_visual_model") or "seedance_2_0_fast_ref"),
                qa_checks=_segment_qa_checks(niche=niche, runtime_class=runtime_class, has_dialogue=has_dialogue),
            ))
    else:
        estimated_units = max(1, ceil(total_duration / unit_target))
        beat_flow = list(niche_playbook.get("beat_flow") or ["hook", "proof", "payoff"])
        for index in range(min(4, estimated_units)):
            policy_row = _policy_for_segment(policy, index)
            beat = str(beat_flow[index % len(beat_flow)])
            segments.append(_segment_row(
                segment_id=f"short_unit_{index + 1:02d}",
                source_scene_id="short_form",
                unit_index=index + 1,
                target_duration_s=max(4, min(15, ceil(total_duration / estimated_units))),
                shot_type=str(policy_row.get("shot_type") or beat),
                purpose=f"{beat}: {policy_row.get('goal') or 'make the idea visually readable'}",
                hook_or_turn=_preview_hook(niche_playbook) if index == 0 else beat,
                action=_short_action_line(user_idea=user_idea, niche=niche, beat=beat),
                camera=_camera_line(niche_playbook, selected_creative_treatment, index),
                sound=_sound_line_preview(market_playbook, niche_playbook, has_dialogue),
                use_refs=list(policy_row.get("use_refs") or []),
                reference_jobs=ref_jobs,
                continuity_anchor="same identity/product/style anchors across units" if index else "establish strongest anchors first",
                model_route=str((model_route_strategy.get("summary") or {}).get("primary_visual_model") or "seedance_2_0_fast_ref"),
                qa_checks=_segment_qa_checks(niche=niche, runtime_class=runtime_class, has_dialogue=has_dialogue),
            ))

    return {
        "schema_version": "cinejelly.seedance_segment_inspector.v1",
        "mode": "long_form_scene_units" if long_form_preview.get("enabled") else "short_form_units",
        "runtime_class": runtime_class,
        "target_duration_s": total_duration,
        "preview_segment_count": len(segments),
        "estimated_total_units": (
            int(long_form_preview.get("estimated_seedance_units") or 0)
            if long_form_preview.get("enabled")
            else max(1, ceil(total_duration / unit_target))
        ),
        "unit_contract": {
            "duration_s": [4, 15],
            "rule": "one filmable action per Seedance unit; use explicit reference jobs, not blob prompts",
            "long_form_rule": "preview shows first units only; graph expands every scene/chunk before render",
        },
        "reference_job_count": len(ref_jobs),
        "segments": segments,
        "operator_policy": [
            "Keep the user UI one-click; this inspector is for admin/debug QA.",
            "Reject or rewrite any segment that lacks subject, action, camera, continuity, or reference intent.",
            "For long-form, never promote route quality from this preview alone; require paid graph benchmark evidence.",
        ],
    }


def _segment_reference_jobs(allocation: dict[str, Any]) -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    for key in ("image_role_plan", "video_role_plan", "audio_role_plan"):
        for item in allocation.get(key) or []:
            tag = str(item.get("tag") or "").strip()
            role = str(item.get("role") or "").strip()
            job = str(item.get("job") or "").strip()
            if tag:
                jobs.append({"tag": tag, "role": role, "job": job})
    if (allocation.get("long_form_handoff_policy") or {}).get("enabled"):
        jobs.append({
            "tag": "previous_scene_final_frame",
            "role": "continuity_anchor",
            "job": "reuse the accepted final frame to preserve pose, layout, lighting, and scene state",
        })
    return jobs[:12]


def _policy_for_segment(policy: list[dict[str, Any]], index: int) -> dict[str, Any]:
    if not policy:
        return {}
    if index < len(policy):
        return policy[index]
    return policy[-1]


def _segment_row(
    *,
    segment_id: str,
    source_scene_id: str,
    unit_index: int,
    target_duration_s: int,
    shot_type: str,
    purpose: str,
    hook_or_turn: str,
    action: str,
    camera: str,
    sound: str,
    use_refs: list[str],
    reference_jobs: list[dict[str, str]],
    continuity_anchor: str,
    model_route: str,
    qa_checks: list[str],
) -> dict[str, Any]:
    return {
        "segment_id": segment_id,
        "source_scene_id": source_scene_id,
        "unit_index": unit_index,
        "target_duration_s": max(4, min(15, int(target_duration_s or 12))),
        "shot_type": shot_type,
        "purpose": purpose[:240],
        "model_route": model_route,
        "use_refs": use_refs[:6],
        "continuity_anchor": continuity_anchor,
        "prompt_blocks": {
            "reference_jobs": [
                f"{item['tag']}={item['role']}: {item['job']}"
                for item in reference_jobs
                if item.get("tag")
            ][:8],
            "timeline": f"{max(4, min(15, int(target_duration_s or 12)))}s Seedance unit",
            "story_intent": hook_or_turn[:220],
            "action": action[:260],
            "camera": camera[:180],
            "sound": sound[:180],
            "constraints": [
                "one physical action",
                "no unrequested text overlays/logos",
                "preserve identity/product/style geometry",
                "match market language and caption tone",
            ],
        },
        "qa_checks": qa_checks,
    }


def _camera_line(niche_playbook: dict[str, Any], selected_creative_treatment: dict[str, Any], index: int) -> str:
    treatment_camera = str(selected_creative_treatment.get("camera_language") or "").strip()
    if treatment_camera:
        return treatment_camera
    cameras = list(niche_playbook.get("camera") or [])
    if cameras:
        return str(cameras[index % len(cameras)])
    return "controlled cinematic camera with readable subject, action, and continuity"


def _sound_line_preview(market_playbook: dict[str, Any], niche_playbook: dict[str, Any], has_dialogue: bool) -> str:
    audio = str(niche_playbook.get("audio") or "natural production sound").strip()
    language = str(market_playbook.get("primary_language") or "auto").strip()
    if has_dialogue:
        return f"{language} dialogue/voiceover kept short; {audio}"
    return audio


def _short_action_line(*, user_idea: str, niche: str, beat: str) -> str:
    idea = " ".join((user_idea or "").split())[:180] or "the main subject"
    if beat in {"hook", "problem", "setup"}:
        return f"Open with the most visual proof of {idea}; make the niche '{niche}' readable immediately."
    if beat in {"proof", "demo", "escalation"}:
        return f"Show a concrete visible action or before-after proof from {idea}."
    return f"Resolve the beat with a clear payoff from {idea}, without adding unrelated claims."


def _segment_qa_checks(*, niche: str, runtime_class: str, has_dialogue: bool) -> list[str]:
    checks = [
        "subject/action/camera/setting explicit",
        "Seedance duration within 4-15s",
        "reference roles are not mixed",
        "identity/product/style continuity preserved",
    ]
    if runtime_class in {"micro_film", "short_film", "episode"}:
        checks.append("handoff frame matches next scene state")
    if has_dialogue:
        checks.append("dialogue/lip-sync candidate requires benchmark review")
    if niche in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        checks.append("claims and safety framing reviewed")
    return checks


def _autonomous_input_upgrade_plan(
    *,
    niche: str,
    runtime_payload: dict[str, Any],
    target_market: str,
    has_dialogue: bool,
    reference_sufficiency: dict[str, Any],
    niche_production_recipe: dict[str, Any],
    route_quality_scorecard: Optional[dict[str, Any]],
    segment_inspector: dict[str, Any],
) -> dict[str, Any]:
    """Translate technical gates into a user/action plan for better inputs."""
    checks = list(reference_sufficiency.get("checks") or [])
    warnings = [item for item in checks if item.get("status") in {"warn", "fail"}]
    refs = reference_sufficiency.get("reference_counts") or {}
    ref_recipe = niche_production_recipe.get("reference_recipe") or {}
    best_refs = ref_recipe.get("best_quality_refs") or {}
    minimum_refs = ref_recipe.get("minimum_to_attempt") or {}
    counts = {
        "images": int(refs.get("images") or 0),
        "videos": int(refs.get("videos") or 0),
        "audios": int(refs.get("audios") or 0),
        "pinned_assets": int(refs.get("pinned_assets") or 0),
    }
    missing_to_best = {
        key: max(0, int(best_refs.get(key) or 0) - int(counts.get(key) or 0))
        for key in ("images", "videos", "audios", "pinned_assets")
    }
    missing_minimum = {
        key: max(0, int(minimum_refs.get(key) or 0) - int(counts.get(key) or 0))
        for key in ("images", "videos", "audios", "pinned_assets")
    }
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    renderable_now = not bool(reference_sufficiency.get("render_blocking"))
    top_tier_ready = bool(reference_sufficiency.get("top_tier_ready")) and not (
        route_quality_scorecard or {}
    ).get("blocking_reasons")
    priority_actions = _input_priority_actions(
        warnings=warnings,
        missing_minimum=missing_minimum,
        missing_to_best=missing_to_best,
        niche=niche,
        runtime_class=runtime_class,
        has_dialogue=has_dialogue,
    )
    return {
        "schema_version": "cinejelly.autonomous_input_upgrade_plan.v1",
        "niche": niche,
        "runtime_class": runtime_class,
        "target_market": target_market,
        "renderable_now": renderable_now,
        "top_tier_ready": top_tier_ready,
        "route_confidence": (
            "top_tier_ready"
            if top_tier_ready
            else "renderable_but_benchmark_or_refs_needed"
            if renderable_now
            else "fix_before_render"
        ),
        "current_reference_counts": counts,
        "minimum_to_attempt": minimum_refs,
        "best_quality_targets": best_refs,
        "missing_minimum": missing_minimum,
        "missing_to_best": missing_to_best,
        "priority_actions": priority_actions[:6],
        "first_segment_preview": (segment_inspector.get("segments") or [None])[0],
        "user_message": _input_upgrade_message(
            renderable_now=renderable_now,
            top_tier_ready=top_tier_ready,
            priority_actions=priority_actions,
        ),
        "auto_mode_policy": [
            "Do not expose manual Seedance settings to the user.",
            "Use these actions only as optional input guidance before autonomous render.",
            "If the user ignores non-blocking actions, render through the safest route and keep top-tier claims gated.",
        ],
    }


def _input_priority_actions(
    *,
    warnings: list[dict[str, Any]],
    missing_minimum: dict[str, int],
    missing_to_best: dict[str, int],
    niche: str,
    runtime_class: str,
    has_dialogue: bool,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for item in warnings:
        recommendation = str(item.get("recommendation") or item.get("detail") or "").strip()
        if recommendation:
            actions.append({
                "priority": "required" if item.get("status") == "fail" else "recommended",
                "kind": str(item.get("name") or "reference_gap"),
                "action": recommendation,
                "why": str(item.get("detail") or ""),
            })
    labels = {
        "images": "Add image reference(s)",
        "videos": "Add video motion reference(s)",
        "audios": "Add audio/voice/SFX reference(s)",
        "pinned_assets": "Approve reusable asset pin(s)",
    }
    for key, missing in missing_minimum.items():
        if missing > 0:
            actions.append({
                "priority": "required",
                "kind": f"minimum_{key}",
                "action": f"{labels[key]}: +{missing}",
                "why": "Minimum input contract for this niche/runtime is not met.",
            })
    for key, missing in missing_to_best.items():
        if missing > 0:
            actions.append({
                "priority": "recommended",
                "kind": f"top_tier_{key}",
                "action": f"{labels[key]} for stronger top-tier consistency: +{missing}",
                "why": "Improves identity, product, motion, audio, or long-form continuity before paid render.",
            })
    if runtime_class in {"micro_film", "short_film", "episode"}:
        actions.append({
            "priority": "recommended",
            "kind": "long_form_memory",
            "action": "Approve character/product/location/style pins before long-form render.",
            "why": "Long videos need reusable anchors and previous-frame handoffs to avoid drift.",
        })
    if has_dialogue:
        actions.append({
            "priority": "benchmark",
            "kind": "dialogue_lane",
            "action": "Benchmark or review the dialogue/lip-sync lane for this market.",
            "why": "Visible speech quality depends on language, phoneme fit, and segment stability.",
        })
    if niche in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        actions.append({
            "priority": "review",
            "kind": "claims_safety",
            "action": "Review script/caption/final claims before promotion or publish.",
            "why": "This niche has higher factual, safety, or policy risk.",
        })
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in actions:
        key = f"{action.get('priority')}:{action.get('kind')}:{action.get('action')}"
        if key not in seen:
            seen.add(key)
            deduped.append(action)
    return deduped


def _input_upgrade_message(
    *,
    renderable_now: bool,
    top_tier_ready: bool,
    priority_actions: list[dict[str, Any]],
) -> str:
    if top_tier_ready:
        return "Input set is strong for the selected autonomous route."
    if not renderable_now:
        first = priority_actions[0]["action"] if priority_actions else "Fix blocking reference issues."
        return f"Fix before render: {first}"
    first_recommended = next(
        (item["action"] for item in priority_actions if item.get("priority") in {"recommended", "benchmark", "review"}),
        "",
    )
    if first_recommended:
        return f"Renderable now, but stronger with: {first_recommended}"
    return "Renderable now; top-tier claim remains gated until real benchmark evidence is attached."


def _selected_creative_treatment(search: dict[str, Any]) -> dict[str, Any]:
    selected_id = search.get("selected_treatment_id")
    for item in search.get("candidates") or []:
        if item.get("treatment_id") == selected_id:
            return item
    candidates = search.get("candidates") or []
    return candidates[0] if candidates else {}


def _preview_hook(niche_playbook: dict[str, Any]) -> str:
    hook_moves = niche_playbook.get("hook_moves") or []
    if hook_moves:
        return f"{hook_moves[0]} with immediate visual proof"
    return "a strong opening image with immediate visual proof"


def _benchmark_required(readiness: Any, graph_required: bool, dialogue_policy: dict[str, Any]) -> bool:
    return bool(
        readiness != "high"
        or graph_required
        or dialogue_policy.get("requires_benchmark_before_auto_route")
    )


def _readiness_row(niche: str) -> dict[str, Any]:
    matrix = build_niche_readiness_matrix()
    for row in matrix.get("niches", []):
        if row.get("niche") == niche:
            return row
    return {"niche": niche, "readiness": "unknown"}


def _looks_commercial(text: str) -> bool:
    return bool(re.search(
        r"\b(product|shop|store|brand|app|tool|review|demo|sale|ads?|san pham|thuong hieu|quang cao|tiktok shop)\b",
        text,
    ))


def _looks_like_reference_product_request(text: str, reference_counts: dict[str, int]) -> bool:
    has_visual_ref = (
        _reference_count(reference_counts, "images", "image")
        or _reference_count(reference_counts, "videos", "video")
        or _reference_count(reference_counts, "pinned_assets", "pinned")
    ) > 0
    if not has_visual_ref:
        return False
    subject_terms = [
        "san pham", "product", "hang hoa", "mat hang", "vat pham", "sku",
        "brand", "thuong hieu", "bao bi", "packaging",
    ]
    reference_terms = [
        "trong anh", "trong hinh", "tu anh", "reference", "ref", "attached image",
        "image", "photo", "picture", "hinh anh",
    ]
    social_video_terms = ["tiktok", "viral", "hook", "short", "reel", "ads", "ad ", "video"]
    if any(term in text for term in subject_terms) and any(term in text for term in reference_terms):
        return True
    return any(term in text for term in social_video_terms)


def _normalize_match_text(value: str) -> str:
    text = (value or "").strip().lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d")


def _keyword_in_text(keyword: str, normalized_text: str) -> bool:
    normalized_keyword = _normalize_match_text(keyword)
    if not normalized_keyword:
        return False
    if " " in normalized_keyword:
        return normalized_keyword in normalized_text
    if len(normalized_keyword) <= 3:
        return bool(re.search(rf"\b{re.escape(normalized_keyword)}\b", normalized_text))
    return normalized_keyword in normalized_text


def _keyword_hits(keywords: list[str], normalized_text: str) -> list[str]:
    seen: set[str] = set()
    hits: list[str] = []
    for keyword in keywords:
        normalized_keyword = _normalize_match_text(keyword)
        if normalized_keyword in seen:
            continue
        if _keyword_in_text(keyword, normalized_text):
            seen.add(normalized_keyword)
            hits.append(normalized_keyword)
    return hits


__all__ = ["build_autonomous_production_decision"]
