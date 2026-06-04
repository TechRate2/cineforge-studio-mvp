"""Competitive research map for CineJelly Autonomous Agent.

This is a source-backed way to keep external research useful. It maps Atlas /
Seedance docs, open-source AI film systems, and long-video papers into concrete
product patterns, current implementation status, and next engineering steps.
"""
from __future__ import annotations

from typing import Any


def build_autonomous_competitive_research() -> dict[str, Any]:
    """Return curated external patterns and how CineJelly currently matches them."""
    sources = _sources()
    patterns = _patterns()
    return {
        "schema_version": "cinejelly.autonomous_competitive_research.v1",
        "research_position": {
            "plain_answer": (
                "CineJelly has the right architecture shape for a top autonomous video agent, "
                "but cannot honestly claim parity with the strongest production apps until paid "
                "benchmark outputs prove quality, cost, latency, identity, audio, and long-form stability."
            ),
            "closest_strength_today": "autonomous short-form product/social/UGC production with Seedance 2.0 references",
            "largest_remaining_gap": "real long-form graph benchmark evidence and model-backed identity/product/lip-sync QA",
        },
        "sources": sources,
        "patterns": patterns,
        "implementation_score": _implementation_score(patterns),
        "source_backed_upgrade_matrix": _source_backed_upgrade_matrix(),
        "best_patterns_to_apply_next": [
            {
                "priority": "P0",
                "pattern": "paid benchmark evidence loop",
                "why": "All top-tier claims depend on real outputs, reviewer notes, cost, latency, QA frames, and retry counts.",
                "code_direction": "promote routes from benchmark storage only after evidence validator passes",
            },
            {
                "priority": "P0",
                "pattern": "graph executor default-on only after proof",
                "why": "5-30m videos fail if rendered as one prompt or as an untracked linear chain.",
                "code_direction": "run CINEJELLY_ENABLE_GRAPH_LONG_FORM benchmark jobs and promote after accepted outputs",
            },
            {
                "priority": "P1",
                "pattern": "omni segment prompt editor",
                "why": "Chinese Seedance 2.0 short-drama tools treat each segment as an independent omni prompt with explicit @image/@video/@audio bindings.",
                "code_direction": "keep the user UI one-click, but expose an admin/debug inspector for generated segment prompts and reference roles",
            },
            {
                "priority": "P1",
                "pattern": "first-frame grid and keyframe handoff",
                "why": "Seedance workflows use storyboard/keyframe grids and first/last-frame continuity to reduce drift across shots.",
                "code_direction": "benchmark 9-panel board anchors plus previous-frame handoffs against plain per-shot references",
            },
            {
                "priority": "P1",
                "pattern": "memory-to-video keyframe bank",
                "why": "Long-form coherence improves when each generated shot updates a compact memory bank of keyframes instead of relying only on text history.",
                "code_direction": "promote scene_memory_pack into a dynamic keyframe memory bank populated from accepted render outputs",
            },
            {
                "priority": "P1",
                "pattern": "script-keyframe-shot-smoothing pipeline",
                "why": "Multi-shot systems outperform one-pass prompts by separating script generation, consistent keyframes, shot video generation, and transition smoothing.",
                "code_direction": "make long-form graph nodes explicitly carry script beat, keyframe prompt, video prompt, smoothing/handoff requirement, and QA result",
            },
            {
                "priority": "P1",
                "pattern": "multi-candidate hero shot selection",
                "why": "Top short-drama workflows generate several candidate frames/clips for important beats and select the best before final assembly.",
                "code_direction": "for hero shots, generate 2-3 benchmark candidates, score identity/product/story fit, and keep only the accepted candidate",
            },
            {
                "priority": "P1",
                "pattern": "asset library as production memory",
                "why": "China-style short-drama systems win through reusable characters, locations, props, costumes, and voice.",
                "code_direction": "expand asset pins into full character/product/location/style/voice library with usage analytics",
            },
            {
                "priority": "P1",
                "pattern": "dialogue lane benchmark",
                "why": "Vietnamese/global speech needs a separate model route for talking-head and two-speaker scenes.",
                "code_direction": "benchmark InfiniteTalk, MultiTalk, Wan, and lip-sync repair on VN/EN scripts",
            },
            {
                "priority": "P1",
                "pattern": "model-backed visual QA",
                "why": "Deterministic checks catch structure; top apps also need face/product/reference/lip-sync evaluators.",
                "code_direction": "add embeddings/OCR/lip-sync models and block failed outputs before assembly",
            },
            {
                "priority": "P1",
                "pattern": "likeness and known-IP guard",
                "why": "Seedance 2.0 realism has already triggered public legal and labor pushback around recognizable actors and protected characters.",
                "code_direction": "add a pre-render policy gate for known IP, celebrity likeness, voice cloning, and unlicensed character prompts",
            },
        ],
        "seedance_2_workflow_rules": [
            "Treat Seedance 2.0 as a quad-modal director, not a paragraph-to-video toy.",
            "Use image refs for identity/product/style, video refs for motion/camera, audio refs for rhythm/SFX/dialogue.",
            "Keep each unit inside 4-15 seconds with one filmable action.",
            "Use structured shot lists and reference jobs; avoid blob prompts.",
            "For longer videos, build screenplay scenes and render many verified units.",
            "Use previous-final-frame or keyframe i2v handoffs for continuity.",
            "Use dialogue/audio/post models as inserts or repair lanes after visual route planning.",
        ],
        "niche_strategy_summary": {
            "sell_first": [
                "ugc_review",
                "beauty",
                "food",
                "ecommerce_catalog",
                "fashion",
                "app_saas",
                "tech",
                "asmr",
                "lifestyle",
            ],
            "benchmark_next": [
                "real_estate",
                "travel",
                "restaurant_hospitality",
                "automotive",
                "fitness",
                "education",
                "music_video",
                "gaming",
                "drama_short_form",
            ],
            "review_locked": [
                "finance_education",
                "medical_wellness",
                "kids_family",
                "documentary/news/current_events",
            ],
            "r_and_d": [
                "10-30m episodes",
                "multi-character dialogue drama",
                "fact-heavy documentary",
                "high-risk public figures or known IP",
            ],
        },
    }


def _sources() -> list[dict[str, Any]]:
    return [
        {
            "name": "AtlasCloud Docs",
            "url": "https://www.atlascloud.ai/docs",
            "kind": "vendor_docs",
            "takeaways": [
                "unified API for 300+ models",
                "async prediction lifecycle",
                "model library and pricing can change, so routing must stay benchmark-gated",
            ],
            "applied_in_source": ["vendors.atlascloud", "model_scorecard", "benchmark store"],
        },
        {
            "name": "AtlasCloud Video Generation Docs",
            "url": "https://www.atlascloud.ai/docs/models/video",
            "kind": "vendor_docs",
            "takeaways": [
                "video generation is an async submit/poll workflow through generateVideo and prediction endpoints",
                "Atlas exposes text-to-video, image-to-video, video-to-video, and audio-to-video model categories",
                "model choice should depend on quality/speed, motion control, style, resolution, and duration support",
            ],
            "applied_in_source": ["vendors.atlascloud", "video_worker", "model_scorecard", "autonomous_model_route_strategy"],
        },
        {
            "name": "AtlasCloud Predictions and Upload Files Docs",
            "url": "https://www.atlascloud.ai/docs/predictions",
            "kind": "vendor_docs",
            "takeaways": [
                "non-LLM generation tasks return prediction IDs and require polling with timeout/error handling",
                "video/image-to-video tasks commonly take 30 seconds to 3 minutes and can fail for parameter, URL, moderation, or balance reasons",
                "local files should be uploaded through uploadMedia and passed as temporary URLs to model calls",
            ],
            "applied_in_source": ["upload-media", "vendors.atlascloud", "video_worker", "production_graph_executor"],
        },
        {
            "name": "AtlasCloud Seedance 2.0",
            "url": "https://www.atlascloud.ai/seedance-2",
            "kind": "vendor_model_page",
            "takeaways": [
                "six Seedance 2.0 endpoints: t2v, i2v, reference-to-video, and fast variants",
                "reference-to-video is the core route for multimodal production",
                "Fast is default/draft; premium is for high-fidelity hero shots",
            ],
            "applied_in_source": ["model_scorecard", "autonomous_model_route_strategy", "video_worker model resolver"],
        },
        {
            "name": "ByteDance Seedance 2.0 official",
            "url": "https://seed.bytedance.com/en/seedance2_0",
            "kind": "official_model_page",
            "takeaways": [
                "text, image, audio, and video inputs",
                "director-level control over performance, lighting, shadow, camera movement",
                "audio-video joint generation and motion stability",
            ],
            "applied_in_source": ["seedance_prompt_compiler", "seedance_reference_allocation", "niche_production_recipe"],
        },
        {
            "name": "Higgsfield cinematic logic layer",
            "url": "https://openai.com/index/higgsfield/",
            "kind": "production_case_study",
            "takeaways": [
                "simple idea, product link, or image is expanded into a concrete video plan before generation",
                "planning layer infers narrative arc, pacing, camera logic, and visual emphasis",
                "social-first video quality depends on invisible hook timing, shot rhythm, and native-platform pacing",
            ],
            "applied_in_source": [
                "conversational_preflight",
                "creative_treatment_search",
                "cinematic_grammar_contract",
                "niche_runtime_director",
            ],
        },
        {
            "name": "Higgsfield MCP creative studio",
            "url": "https://higgsfield.ai/blog/Generate-AI-Videos-From-Claude-with-Higgsfield-MCP",
            "kind": "production_product_reference",
            "takeaways": [
                "a chat thread can become the production environment when model routing, assets, generation, and iteration live behind one agent",
                "model routing should stay invisible by default while still choosing the best route per shot, input, aspect, and modality",
                "persistent clip/project memory lets future requests refer back to accepted renders instead of restarting from scratch",
            ],
            "applied_in_source": [
                "app/studio/page.tsx",
                "autonomous_model_route_strategy",
                "asset_memory",
                "production_artifacts",
            ],
        },
        {
            "name": "Higgsfield Supercomputer",
            "url": "https://higgsfield.ai/",
            "kind": "production_product_reference",
            "takeaways": [
                "agent products are moving toward skills, memory, automations, connectors, and campaign-scale batch production from one prompt",
                "reusable skills and presets turn winning creative workflows into repeatable routes rather than one-off prompts",
                "the strongest SaaS surface is a clean agent workspace; routing, tools, and memory stay behind the conversation",
            ],
            "applied_in_source": [
                "conversational_preflight",
                "niche_playbooks",
                "benchmark_promotion_policy",
                "autonomous_asset_pins",
            ],
        },
        {
            "name": "Topview AI Video Agent V2",
            "url": "https://www.trytopview.com/",
            "kind": "production_product_reference",
            "takeaways": [
                "ad agents reduce the user surface to product/idea/references and hide production mechanics",
                "UGC and commerce routes need platform-optimized hooks, product demonstration, avatar/voice options, and motion reference reuse",
                "product-to-video workflows should favor strong defaults and approval/edit loops over manual render parameters",
            ],
            "applied_in_source": [
                "app/studio/page.tsx",
                "conversational_preflight",
                "market_playbooks",
                "distribution_package",
            ],
        },
        {
            "name": "HeyGen rebuilt Video Agent",
            "url": "https://heygen.noticeable.news/publications/introducing-our-new-video-agent",
            "kind": "production_product_reference",
            "takeaways": [
                "blueprint-first creation shows the full plan before rendering",
                "chat-based edits should change the plan before build, not force the user to rewrite raw prompts",
                "build mode and chat mode are separate product modes; CineJelly intentionally keeps user-facing Studio in approval-first chat mode",
            ],
            "applied_in_source": [
                "conversational_preflight",
                "app/studio/page.tsx",
                "check-autonomous-ui",
            ],
        },
        {
            "name": "OpenMontage",
            "url": "https://github.com/calesthio/OpenMontage",
            "kind": "open_source_agentic_video_system",
            "takeaways": [
                "agentic production systems need pipelines, tools, artifacts, and reviewable render outputs",
                "production can mix generated assets, stock footage, voice, music, captions, editing, and final assembly",
                "agent-readable reports and render-review loops matter as much as initial generation",
            ],
            "applied_in_source": [
                "production_graph",
                "production_artifacts",
                "benchmark_evidence_pack_builder",
                "JobResultModal",
            ],
        },
        {
            "name": "Montaj agent timeline editor",
            "url": "https://www.montaj.ag/",
            "kind": "agentic_editor_reference",
            "takeaways": [
                "agent workflows benefit from a timeline, caption editor, overlay preview, and tool-callable edit surface",
                "post-render user trust improves when the agent can explain and adjust edit decisions",
                "editing UX should stay separate from pre-render model parameters",
            ],
            "applied_in_source": [
                "JobResultModal",
                "production_artifacts",
                "future_edit_workspace",
            ],
        },
        {
            "name": "Seedance 2.0 docs",
            "url": "https://seedance2.app/docs",
            "kind": "model_docs",
            "takeaways": [
                "up to 9 images, 3 videos, 3 audio files, 12 mixed refs total",
                "4-15 second generation units",
                "reference-first prompting",
            ],
            "applied_in_source": ["reference caps in UI", "reference_sufficiency_gate", "seedance_shot_linter"],
        },
        {
            "name": "ChatCut Seedance 2.0 Prompt Guide on X",
            "url": "https://x.com/chatcutapp/status/2041763561333264865",
            "kind": "creator_x_report",
            "takeaways": [
                "uploaded files need explicit jobs; do not expect Seedance to infer why each asset exists",
                "a strong prompt names asset role, action timing, camera behavior, sound behavior, and constraints",
                "image, video, audio, and text references should be prioritized by production value when upload slots are limited",
            ],
            "applied_in_source": ["seedance_reference_allocation", "seedance_prompt_compiler", "reference_sufficiency_gate"],
        },
        {
            "name": "OpenArt / Seedance creator reports on X",
            "url": "https://x.com/azed_ai/status/2040460544495526397",
            "kind": "creator_x_report",
            "takeaways": [
                "practical creator workflows use up to 9 image, 3 video, and 3 audio references for controlled multi-shot scenes",
                "camera control and reference depth are competitive differentiators, not optional advanced settings",
                "good prompt templates are reusable per niche and should be benchmarked before promotion",
            ],
            "applied_in_source": ["reference caps in UI", "niche_production_recipe", "benchmark_promotion_policy"],
        },
        {
            "name": "CapCut Video Studio / Seedance agent workflow reports on X",
            "url": "https://x.com/masahirochaen/status/2037147512046252168",
            "kind": "creator_x_report",
            "takeaways": [
                "top consumer workflows are moving toward AI agent story ideation, writing, structure, storyboard, and Seedance generation in one workspace",
                "timeline complexity is hidden from the user, but storyboard and frame-level edit controls remain available internally",
                "global products should localize by market while keeping the default UI simple",
            ],
            "applied_in_source": ["app/studio/page.tsx", "autonomous_workflow_contract", "market_playbooks"],
        },
        {
            "name": "Codeywood",
            "url": "https://codeywood.com/",
            "kind": "open_source_repo",
            "takeaways": [
                "autonomous story systems benefit from explicit gates before generation",
                "writers-room style agent debate improves story structure before expensive rendering",
                "reference completeness and visual continuity validation should be visible production gates",
            ],
            "applied_in_source": ["producer_story_critic", "reference_sufficiency_gate", "cross_shot_diagnostic", "autonomous_preflight_gate"],
        },
        {
            "name": "VibeFrame",
            "url": "https://vibeframe.ai/",
            "kind": "open_source_agent_workflow",
            "takeaways": [
                "agent-friendly video workflows should persist storyboard/design files and render inspection reports",
                "build reports make autonomous output debuggable without exposing end-user manual controls",
                "CLI-style artifact contracts help agents resume and diagnose long renders",
            ],
            "applied_in_source": ["production_artifacts", "production_graph_store", "benchmark_evidence_pack_builder"],
        },
        {
            "name": "Jellyfish AI Short Drama Studio",
            "url": "https://github.com/Forget-C/Jellyfish",
            "kind": "open_source_repo",
            "takeaways": [
                "script to storyboard to shot preparation",
                "centralized characters/scenes/props/costumes",
                "unified async task center and reusable generated assets",
            ],
            "applied_in_source": ["asset memory pins", "production graph store", "job history/artifacts"],
        },
        {
            "name": "NovelVids",
            "url": "https://novelvids.com/",
            "kind": "production_pipeline_reference",
            "takeaways": [
                "long narrative video benefits from entity extraction before storyboard generation",
                "character and scene reference images should be established before downstream video synthesis",
                "novel/script-to-short-drama workflows need a durable asset and task pipeline, not a one-shot prompt",
            ],
            "applied_in_source": ["screenplay_planner", "script_asset_sop", "asset_memory", "production_graph"],
        },
        {
            "name": "Alibaba LumenX Studio",
            "url": "https://github.com/alibaba/lumenx",
            "kind": "open_source_repo_china",
            "takeaways": [
                "novel/script to AI short comic-drama production should follow a full SOP",
                "script analysis, entity extraction, character customization, storyboard drawing, and video synthesis are separate production stages",
                "strong platforms make asset extraction and storyboard state explicit before generation",
            ],
            "applied_in_source": ["screenplay_planner", "reference_manifest", "asset_memory", "niche_playbook_catalog"],
        },
        {
            "name": "Huobao Drama",
            "url": "https://github.com/chatfire-AI/huobao-drama",
            "kind": "open_source_repo_china",
            "takeaways": [
                "one-sentence to complete drama requires script generation, role design, storyboard, and video synthesis",
                "short-drama automation is a full-stack production workflow, not a single render endpoint",
                "agent orchestration and workflow state should remain explicit even when the user UI is one-click",
            ],
            "applied_in_source": ["autonomous_workflow_contract", "screenplay_planner", "production_graph", "asset_memory"],
        },
        {
            "name": "Toonflow",
            "url": "https://github.com/HBAI-Ltd/Toonflow-app",
            "kind": "open_source_repo_china",
            "takeaways": [
                "practical Seedance 2.0 short-drama production still generates extra material and cuts weak clips",
                "cost and accepted-output ratio matter as much as raw model pricing",
                "script, storyboard, generation, and editing should be measurable stages",
            ],
            "applied_in_source": ["paid_benchmark_manifest", "benchmark_review_rubric", "production_graph", "assembly_worker"],
        },
        {
            "name": "ViMax / AI-Creator",
            "url": "https://github.com/HKUDS/ViMax",
            "kind": "open_source_repo",
            "takeaways": [
                "idea-to-video multi-agent workflow",
                "director, screenwriter, producer, generator roles",
                "novel-to-video narrative compression and character tracking",
                "reference image selection and consistency checking happen before expensive video generation",
            ],
            "applied_in_source": ["planner/storyboard/director/editor skills", "screenplay_planner", "niche_runtime_director", "production_graph"],
        },
        {
            "name": "Awesome Seedance 2.0 Prompt and Examples",
            "url": "https://github.com/makesupday/Awesome-Seedance-2.0-Prompt-and-Examples",
            "kind": "prompt_workflow",
            "takeaways": [
                "Seedance prompt examples consistently use @Image, @Video, and @Audio role references",
                "prompt banks should be organized by genre, transition type, camera behavior, rhythm, and reference job",
                "accepted prompt templates should become benchmarked route assets rather than ad hoc text",
            ],
            "applied_in_source": ["seedance_prompt_formula", "seedance_prompt_compiler", "niche_production_recipe"],
        },
        {
            "name": "Fal Seedance 2.0 Reference-to-Video Examples",
            "url": "https://github.com/fal-ai/seedance-2.0-api/blob/main/examples/reference_to_video.py",
            "kind": "api_example",
            "takeaways": [
                "reference-to-video examples use explicit @Image1, @Video1, and @Audio1 syntax",
                "duration, aspect, audio generation, and references should be compiled from the agent plan",
                "provider examples reinforce the need for a Seedance prompt compiler instead of freeform user settings",
            ],
            "applied_in_source": ["seedance_reference_allocation", "seedance_prompt_compiler", "model_specs"],
        },
        {
            "name": "Seedance structured shot-list creator reports",
            "url": "https://www.reddit.com/r/Seedance_AI/comments/1tprtbi/7_shots_from_one_seedance_20_prompt_shot_list/",
            "kind": "creator_workflow_report",
            "takeaways": [
                "creators report better continuity when prompts are structured as subjects, shot list, camera/lens, and SFX instead of blob prompts",
                "each character should bind a reference tag plus stable identity details",
                "the same structure is provider-agnostic and maps well to Seedance reference prompts",
            ],
            "applied_in_source": ["seedance_prompt_formula", "seedance_prompt_compiler", "seedance_segment_inspector"],
        },
        {
            "name": "LocalMiniDrama",
            "url": "https://github.com/xuanyustudio/LocalMiniDrama",
            "kind": "open_source_repo_china",
            "takeaways": [
                "story to storyboard to video local short-drama workflow",
                "Seedance 2.0 omni segment mode with explicit @image reference ordering",
                "4-15s duration snapping and multi-reference assembly are first-class production constraints",
            ],
            "applied_in_source": ["seedance_shot_linter", "seedance_prompt_compiler", "scene_generation_agent"],
        },
        {
            "name": "Moyin Creator",
            "url": "https://github.com/MemeCalculate/moyin-creator",
            "kind": "open_source_repo_china",
            "takeaways": [
                "screenplay to characters to scenes to storyboard to Seedance 2.0 pipeline",
                "batch short-drama/anime production needs character and scene assets before video",
                "first-frame grid stitching and layered action/camera/dialogue prompt fusion are strong Seedance patterns",
            ],
            "applied_in_source": ["storyboard_board", "asset_memory", "reference_manifest", "seedance_prompt_compiler"],
        },
        {
            "name": "MapleShaw Seedance prompt skill",
            "url": "https://github.com/MapleShaw/seedance2.0-prompt-skill/blob/main/SKILL.md",
            "kind": "prompt_workflow",
            "takeaways": [
                "character consistency uses subject plus @image role binding",
                "motion and camera replication should reference @video assets explicitly",
                "Seedance can extend, edit, and rhythm-match clips when the prompt names the operation",
            ],
            "applied_in_source": ["seedance_reference_allocation", "seedance_prompt_compiler", "reference_policy_optimizer"],
        },
        {
            "name": "ComfyUI Seedance 2.0 docs",
            "url": "https://docs.comfy.org/zh/tutorials/partner-nodes/bytedance/seedance-2-0",
            "kind": "workflow_docs",
            "takeaways": [
                "text, image, video, and audio inputs are unified in the Seedance workflow",
                "available workflows include T2V, reference-to-video, and first/last-frame video",
                "strong use cases include ads, short drama, film previsualization, product showcase, virtual characters, games, and animation",
            ],
            "applied_in_source": ["model_scorecard", "seedance_reference_allocation", "long_form_orchestrator"],
        },
        {
            "name": "MovieAgent",
            "url": "https://github.com/showlab/MovieAgent",
            "kind": "research_repo",
            "takeaways": [
                "multi-agent chain-of-thought movie planning",
                "separate creative roles improve structure",
                "movie generation needs explicit planning before rendering",
            ],
            "applied_in_source": ["autonomous skill chain", "producer story critic", "cinematic grammar contract"],
        },
        {
            "name": "DrawVideo",
            "url": "https://arxiv.org/abs/2605.23508",
            "kind": "research_paper",
            "takeaways": [
                "storyboard/keyframe guidance improves long-video controllability",
                "appearance consistency and structural stability need explicit intermediate artifacts",
            ],
            "applied_in_source": ["storyboard panels", "scene memory pack", "production graph"],
        },
        {
            "name": "Seedance 2.0 paper",
            "url": "https://arxiv.org/abs/2604.14148",
            "kind": "research_paper",
            "takeaways": [
                "world-complexity video generation benefits from multimodal references",
                "model capability should be evaluated across text/image/multimodal tasks",
            ],
            "applied_in_source": ["capability matrix", "benchmark suite", "quad-modal reference roles"],
        },
        {
            "name": "StoryMem",
            "url": "https://arxiv.org/abs/2512.19539",
            "kind": "research_paper",
            "takeaways": [
                "long-video storytelling benefits from an updated memory bank of generated keyframes",
                "memory-to-video design improves cross-shot consistency and smooth transitions",
                "minute-long stories need persistent visual memory, not only prompt history",
            ],
            "applied_in_source": ["scene_memory_pack", "continuity_handoff_policy", "production_graph"],
        },
        {
            "name": "CoAgent",
            "url": "https://arxiv.org/abs/2512.22536",
            "kind": "research_paper",
            "takeaways": [
                "coherent video generation benefits from a plan-synthesize-verify loop",
                "a global context manager should preserve entity-level appearance, spatial relations, and temporal cues",
                "a verifier agent should trigger selective regeneration instead of accepting every generated shot",
            ],
            "applied_in_source": ["production_graph", "cross_shot_diagnostic", "render_retry_planner", "scene_memory_pack"],
        },
        {
            "name": "Co-Director",
            "url": "https://arxiv.org/abs/2604.24842",
            "kind": "research_paper",
            "takeaways": [
                "agentic video storytelling should be optimized globally, not only by isolated handcrafted prompts",
                "multiple creative directions can be explored, scored, and refined before the final render route",
                "local multimodal self-refinement reduces identity drift and cascading narrative failures",
            ],
            "applied_in_source": ["creative_treatment_search", "producer_story_critic", "route_quality_scorecard", "autonomous_preflight_gate"],
        },
        {
            "name": "DreamShot",
            "url": "https://arxiv.org/abs/2604.17195",
            "kind": "research_paper",
            "takeaways": [
                "storyboard synthesis should use video priors, not only text-to-image style panels",
                "Text-to-Shot and Reference-to-Shot generation help preserve role, scene, and transition consistency",
                "multi-reference role conditioning is a strong pattern for character-heavy stories",
            ],
            "applied_in_source": ["storyboard_board", "seedance_reference_allocation", "dynamic_keyframe_memory", "scene_memory_pack"],
        },
        {
            "name": "CANVAS",
            "url": "https://arxiv.org/abs/2604.13452",
            "kind": "research_paper",
            "takeaways": [
                "continuity-aware narrative systems should explicitly plan character, background, prop, and location continuity",
                "long-range consistency needs benchmarkable continuity dimensions, not only final-video inspection",
                "hard continuity cases should be separated from easy short-form cases",
            ],
            "applied_in_source": ["scene_memory_pack", "continuity_handoff_policy", "cross_shot_diagnostic", "benchmark_review_rubric"],
        },
        {
            "name": "StoryBlender",
            "url": "https://arxiv.org/abs/2604.03315",
            "kind": "research_paper",
            "takeaways": [
                "long-story generation should decouple global assets from shot-specific variables",
                "canonical asset materialization reduces identity and layout drift",
                "a continuity memory graph is useful before shot synthesis",
            ],
            "applied_in_source": ["asset_memory", "scene_memory_pack", "production_graph", "dynamic_keyframe_memory"],
        },
        {
            "name": "Camera Artist",
            "url": "https://arxiv.org/abs/2604.09195",
            "kind": "research_paper",
            "takeaways": [
                "a dedicated cinematography-shot role improves cinematic language and shot-to-shot storytelling",
                "recursive storyboard generation helps narrative continuity",
                "camera language should be evaluated separately from prompt adherence",
            ],
            "applied_in_source": ["cinematic_grammar_contract", "niche_runtime_director", "benchmark_review_rubric"],
        },
        {
            "name": "VideoGen-of-Thought",
            "url": "https://arxiv.org/abs/2412.02259",
            "kind": "research_paper",
            "takeaways": [
                "multi-shot video generation should be decomposed into script, keyframe generation, shot-level video, and smoothing",
                "story and visual consistency improve when each module has a narrow role",
                "manual intervention drops when the pipeline creates intermediate artifacts explicitly",
            ],
            "applied_in_source": ["screenplay_planner", "storyboard_board", "seedance_prompt_compiler", "production_graph"],
        },
        {
            "name": "TTV Pipeline",
            "url": "https://github.com/trilogy-group/ttv-pipeline",
            "kind": "long_form_pipeline",
            "takeaways": [
                "long videos need segmentation because short-model outputs drift over time",
                "keyframe mode and chaining mode are distinct continuity strategies",
                "parallelism is safe for independent keyframe segments but chained continuity needs ordered execution",
            ],
            "applied_in_source": ["production_graph", "continuity_handoff_policy", "dynamic_keyframe_memory", "production_graph_executor"],
        },
        {
            "name": "Stable Video Infinity",
            "url": "https://github.com/vita-epfl/Stable-Video-Infinity",
            "kind": "long_video_research_repo",
            "takeaways": [
                "infinite or long-range video needs explicit anti-drift and transition strategy",
                "long-form storylines benefit from streaming/iterative generation rather than one static prompt",
                "error recycling and memory concepts should inform Seedance graph retry and handoff policy even if the model backend differs",
            ],
            "applied_in_source": ["scene_memory_pack", "dynamic_keyframe_memory", "cross_shot_diagnostic", "render_retry_planner"],
        },
        {
            "name": "One Sentence, One Drama",
            "url": "https://arxiv.org/abs/2605.22144",
            "kind": "research_paper",
            "takeaways": [
                "one-prompt drama systems fail on pacing, spatial consistency, and quality control without multi-agent review",
                "debate-style story generation can improve hook, escalation, and ending quality",
                "3D-grounded first frames and multi-stage reviewer loops reduce spatial drift and production defects",
            ],
            "applied_in_source": ["creative_treatment_search", "producer_story_critic", "screenplay_scene_linter", "production_graph"],
        },
        {
            "name": "MUSE",
            "url": "https://arxiv.org/abs/2602.03028",
            "kind": "research_paper",
            "takeaways": [
                "long-form audio-visual stories need a closed-loop plan-execute-verify-revise process",
                "high-level user intent must be preserved across shot-level multimodal generation",
                "orchestration should keep constraints explicit rather than relying on prompt memory alone",
            ],
            "applied_in_source": ["production_graph_executor", "cross_shot_diagnostic", "render_retry_planner", "scene_memory_pack"],
        },
        {
            "name": "AniMaker",
            "url": "https://arxiv.org/abs/2506.10540",
            "kind": "research_paper",
            "takeaways": [
                "multi-candidate clip generation plus reviewer selection improves story-level coherence",
                "shot evaluation should judge action completion and neighboring-clip context, not isolated beauty only",
                "MCTS-style candidate search is useful for high-value shots when budget allows",
            ],
            "applied_in_source": ["creative_treatment_search", "route_quality_scorecard", "benchmark_review_rubric", "render_retry_planner"],
        },
        {
            "name": "Lights Camera Consistency",
            "url": "https://arxiv.org/abs/2512.16954",
            "kind": "research_paper",
            "takeaways": [
                "character-stable AI video stories need scripts, character sheets, and per-scene anchors before generation",
                "text-to-image character assets should guide scene-level video synthesis",
                "long cohesive stories require reusable identity anchors across scenes",
            ],
            "applied_in_source": ["asset_memory", "reference_manifest", "scene_memory_pack"],
        },
        {
            "name": "Creator short-drama asset workflow reports",
            "url": "https://www.reddit.com/r/Seedance_AI/comments/1taqeiv/two_weeks_into_ai_short_drama_the_wall_isnt/",
            "kind": "creator_workflow_report",
            "takeaways": [
                "real creators report the bottleneck is asset workflow, not simply picking a video model",
                "characters should be imported and reviewed in an asset library before video generation",
                "end-to-end short drama often needs LLM script, image assets, scene assets, video generation, and audio/sound tools",
            ],
            "applied_in_source": ["asset_memory", "autonomous_asset_pins", "autonomous_input_upgrade_plan"],
        },
        {
            "name": "Seedance 2.0 legal and likeness risk coverage",
            "url": "https://apnews.com/article/7e445388401d172c6bf51d0d42aa4f24",
            "kind": "industry_risk",
            "takeaways": [
                "realistic AI video generation creates copyright, likeness, and consent risks",
                "top-tier production systems need policy gates for public figures, known characters, and voice/likeness cloning",
                "viral realism is useful only if routed through responsible review controls",
            ],
            "applied_in_source": ["niche_runtime_director", "autonomous_preflight_gate", "top_tier_completion_gate"],
        },
    ]


def _patterns() -> list[dict[str, Any]]:
    return [
        _pattern(
            "autonomous_one_click_ui",
            "User gives idea + refs; system hides model/shot/manual controls.",
            "implemented",
            ["app/studio/page.tsx", "StudioTopbar", "StudioRail", "check-autonomous-ui"],
            "Keep user UI autonomous-only; move model experiments to benchmark/admin APIs behind future authenticated SaaS admin.",
        ),
        _pattern(
            "saas_shell_hides_provider_security_noise",
            "The user-facing Studio shell shows the Agent workspace, not API keys, provider balances, admin/debug links, or manual playgrounds.",
            "implemented",
            ["StudioTopbar", "StudioRail", "studio redirect routes", "check-autonomous-ui"],
            "Keep provider status, credits, logs, and model diagnostics out of the default SaaS creation surface.",
        ),
        _pattern(
            "conversational_preflight_approval_gate",
            "User chats the idea; the agent asks if blocking details are missing, drafts treatment/script/storyboard, accepts revision notes, then locks an approved render source before paid rendering.",
            "implemented",
            ["conversational_preflight", "app/studio/page.tsx", "director.autonomous_generate"],
            "Add a visual diff between previous and revised plans once the editor workspace exists.",
        ),
        _pattern(
            "chat_native_tool_orchestration",
            "The chat is the production surface; route selection, reference handling, project memory, and generation tools stay behind the agent instead of becoming user-facing settings.",
            "partial",
            ["app/studio/page.tsx", "autonomous_model_route_strategy", "asset_memory", "production_artifacts"],
            "Add project-level accepted-render memory and post-render chat edits so users can reference a previous clip, revise a scene, or create variants without seeing model/tool controls.",
        ),
        _pattern(
            "cinematic_logic_layer_before_generation",
            "Minimal inputs are expanded into narrative arc, pacing, camera logic, shot emphasis, platform fit, and QA policy before generation.",
            "implemented_benchmark_gated",
            ["creative_treatment_search", "cinematic_grammar_contract", "niche_runtime_director", "producer_story_critic"],
            "Attach accepted real-output evidence to each cinematic treatment so the planner learns which logic wins per niche and market.",
        ),
        _pattern(
            "reference_first_seedance_prompting",
            "Every image/video/audio reference receives one production job before prompting.",
            "implemented",
            ["seedance_reference_allocation", "seedance_prompt_compiler", "reference_policy_optimizer"],
            "Add visual UI labels for ref jobs after role tagging so users understand what the agent inferred.",
        ),
        _pattern(
            "creator_proven_asset_job_formula",
            "Seedance prompts should assign every asset a job, then specify timing, action, camera, sound, and constraints.",
            "implemented",
            ["seedance_reference_allocation", "seedance_prompt_compiler", "seedance_shot_linter"],
            "Store accepted per-niche prompt formulas from paid benchmark winners and reuse them as route templates.",
        ),
        _pattern(
            "niche_specific_directing",
            "Every niche has hook, beat flow, camera language, sound, QA risks, and failure modes.",
            "implemented",
            ["niche_playbooks", "niche_runtime_director", "niche_production_recipe", "cinematic_grammar_contract"],
            "Expand recipes with real benchmark examples and accepted prompt templates per niche.",
        ),
        _pattern(
            "screenplay_scene_graph_long_form",
            "5-30m video is screenplay -> scenes -> chunks -> shots -> QA -> assembly.",
            "implemented_benchmark_gated",
            ["long_form_orchestrator", "screenplay_planner", "scene_memory_pack", "production_graph_store"],
            "Run paid graph executor benchmarks before enabling graph mode by default.",
        ),
        _pattern(
            "omni_segment_reference_binding",
            "Each segment prompt binds ordered @image/@video/@audio references instead of relying on implicit model guessing.",
            "implemented",
            ["seedance_reference_allocation", "seedance_prompt_compiler", "scene_generation_agent"],
            "Add a read-only prompt/reference inspector for admin QA and failed-render diagnosis.",
        ),
        _pattern(
            "keyframe_grid_and_previous_frame_handoff",
            "Storyboard boards, first-frame grids, and previous-frame handoffs stabilize identity and scene continuity.",
            "implemented_benchmark_gated",
            ["storyboard_board", "continuity_handoff_policy", "scene_memory_pack", "production_graph"],
            "Run A/B benchmarks: plain refs versus board-anchor plus last-frame handoff for drama/product/real-estate.",
        ),
        _pattern(
            "durable_asset_memory",
            "Characters, products, locations, styles, and voices persist across productions.",
            "partial",
            ["asset_memory", "autonomous_asset_pins"],
            "Add full asset library with location/voice/style anchors, search, approval history, and usage stats.",
        ),
        _pattern(
            "dynamic_keyframe_memory_bank",
            "Accepted shots update a compact keyframe memory bank that future shots can reference.",
            "partial",
            ["scene_memory_pack", "continuity_handoff_policy", "production_graph"],
            "Persist accepted shot keyframes and feed them into later graph nodes as positive/negative visual memory.",
        ),
        _pattern(
            "script_keyframe_shot_smoothing_pipeline",
            "Long-form generation separates script, keyframe assets, shot generation, transition smoothing, and QA.",
            "implemented_benchmark_gated",
            ["screenplay_planner", "storyboard_board", "seedance_prompt_compiler", "production_graph"],
            "Make every long-form graph node expose its script beat, keyframe prompt, video prompt, smoothing rule, and QA verdict.",
        ),
        _pattern(
            "multi_candidate_selection_for_hero_beats",
            "Important first frames, product close-ups, character reveals, and twist/payoff shots should generate candidates and keep the best.",
            "partial",
            ["creative_treatment_search", "route_quality_scorecard", "benchmark_review_rubric"],
            "Add candidate generation/selection nodes for high-value shots when budget and route policy allow it.",
        ),
        _pattern(
            "benchmark_winning_prompt_template_bank",
            "Per-niche Seedance prompt templates should come from accepted output evidence, not static taste.",
            "partial",
            ["seedance_prompt_formula", "seedance_prompt_compiler", "benchmark_store"],
            "Store accepted prompt structures by niche/runtime/model/market and reuse them in future autonomous plans.",
        ),
        _pattern(
            "global_creative_direction_search",
            "The agent explores and scores multiple treatments before committing to screenplay, refs, model route, and QA policy.",
            "implemented_benchmark_gated",
            ["creative_treatment_search", "producer_story_critic", "cinematic_grammar_contract", "route_quality_scorecard"],
            "Store accepted/rejected treatment evidence from real renders so the search policy learns which creative directions work per niche.",
        ),
        _pattern(
            "writers_room_and_producer_gate",
            "Complex stories should be challenged by producer/story/continuity critics before any paid model call.",
            "implemented_benchmark_gated",
            ["producer_story_critic", "screenplay_scene_linter", "creative_treatment_search", "autonomous_preflight_gate"],
            "For 3-30m jobs, benchmark a stronger writers-room pass that compares 3 screenplay arcs and keeps the best one.",
        ),
        _pattern(
            "continuity_benchmark_dimensions",
            "Character, background, prop, location, and scene-transition continuity should be scored as separate dimensions.",
            "partial",
            ["cross_shot_diagnostic", "benchmark_review_rubric", "visual_reference_probe", "scene_memory_pack"],
            "Add per-dimension long-form continuity evidence to benchmark rows and block route promotion when any continuity dimension is below bar.",
        ),
        _pattern(
            "agent_readable_artifact_reports",
            "Every autonomous render should leave storyboard, design, graph, QA, and assembly reports that another agent can resume from.",
            "implemented",
            ["production_artifacts", "production_graph_store", "benchmark_evidence_pack_builder", "director production-report endpoint"],
            "Attach report links to JobResultModal and benchmark rows so reviewers can inspect the exact storyboard/design/graph/QA context.",
        ),
        _pattern(
            "agent_timeline_review_after_render",
            "After render, the product should expose a clean timeline/caption/revision surface instead of forcing users to inspect internal graphs.",
            "partial",
            ["JobResultModal", "production_artifacts", "director-job-api"],
            "Add a SaaS-grade timeline review/edit panel with caption, cut, voice, overlay, regenerate-shot, and approve-export actions.",
        ),
        _pattern(
            "video_prior_storyboard_and_role_conditioning",
            "Storyboards should become renderable reference/keyframe assets with role binding, not just text descriptions.",
            "partial",
            ["storyboard_board", "seedance_reference_allocation", "dynamic_keyframe_memory"],
            "Generate and QA storyboard/keyframe candidates before video for character-heavy drama and long-form scenes.",
        ),
        _pattern(
            "novel_or_script_to_asset_sop",
            "Long narrative input should extract entities, characters, props, locations, costumes, and reusable refs before shot rendering.",
            "partial",
            ["screenplay_planner", "reference_manifest", "asset_memory", "scene_memory_pack"],
            "Add an entity extraction pass that proposes character/location/prop pins from long scripts before graph execution.",
        ),
        _pattern(
            "dialogue_as_separate_lane",
            "Talking-head, multi-speaker, and lip-sync repair are routed separately from visual coverage.",
            "partial",
            ["dialogue_route_policy", "model_scorecard", "autonomous_model_route_strategy"],
            "Benchmark InfiniteTalk/MultiTalk/LipSync/Wan on Vietnamese and English scripts.",
        ),
        _pattern(
            "responsible_likeness_ip_gate",
            "Realistic outputs require pre-render checks for public figures, known IP, and unlicensed voice/likeness cloning.",
            "partial",
            ["niche_runtime_director", "autonomous_preflight_gate", "top_tier_completion_gate"],
            "Add an explicit policy classifier before vendor render and force review for celebrity/IP/voice-clone prompts.",
        ),
        _pattern(
            "model_backed_quality_control",
            "QA uses visual/audio/lip-sync/reference evaluators before final assembly.",
            "partial",
            ["media_quality_probe", "visual_reference_probe", "semantic_quality_evaluator", "strong_quality_gate"],
            "Add embeddings, robust OCR, lip-sync scoring, and product/reference identity validators.",
        ),
        _pattern(
            "route_promotion_by_evidence",
            "A route becomes default only after real outputs and reviewer evidence.",
            "implemented_needs_data",
            ["benchmark_store", "benchmark_promotion_policy", "route_quality_scorecard"],
            "Populate benchmark rows with paid AtlasCloud outputs, cost, latency, QA frames, and reviewer notes.",
        ),
        _pattern(
            "long_form_resume_and_retry",
            "Expensive graph nodes can be leased, retried, resumed, and assembled without re-planning everything.",
            "implemented_benchmark_gated",
            ["production_graph_store", "production_graph_executor", "video_worker graph handlers"],
            "Stress test crash/retry/resume with real failed vendor tasks.",
        ),
        _pattern(
            "long_form_error_recycling",
            "Failed or drifting long-form segments should feed their failure reason into the next prompt, keyframe, and retry route.",
            "missing",
            ["render_retry_planner", "cross_shot_diagnostic", "dynamic_keyframe_memory"],
            "Persist per-shot drift/error signatures and use them as negative constraints for rerender and next-scene handoffs.",
        ),
    ]


def _pattern(
    key: str,
    principle: str,
    status: str,
    source_modules: list[str],
    next_step: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "principle": principle,
        "status": status,
        "source_modules": source_modules,
        "next_step": next_step,
    }


def _source_backed_upgrade_matrix() -> list[dict[str, Any]]:
    """Return the next upgrades that directly map external patterns to source work."""
    return [
        {
            "priority": "P0",
            "upgrade": "paid_seedance_benchmark_pack",
            "external_pattern": "top platforms prove routes with real clips, not architecture claims",
            "source_evidence": ["AtlasCloud Docs", "Higgsfield cinematic logic layer", "Topview AI Video Agent V2", "Jellyfish AI Short Drama Studio"],
            "current_status": "infrastructure_ready_data_missing",
            "implementation_target": [
                "run two paid outputs per sell-first niche on Seedance Fast Reference",
                "run premium Reference benchmarks for beauty, food, fashion, ecommerce hero shots",
                "attach output_url, cost_usd, latency_s, retry_count, qa_frames, and reviewer notes",
            ],
            "promotion_gate": "benchmark_evidence_validator passes and route_quality_scorecard allows top-tier claim",
        },
        {
            "priority": "P0",
            "upgrade": "conversational_cinematic_preflight",
            "external_pattern": "Higgsfield-style cinematic logic layer and Topview-style minimal-input ad agent",
            "source_evidence": ["Higgsfield cinematic logic layer", "Topview AI Video Agent V2"],
            "current_status": "implemented_needs_live_ui_review_and_paid_render_evidence",
            "implementation_target": [
                "keep chat as the primary intake",
                "ask only blocking questions before paid rendering",
                "show editable treatment, script beats, storyboard, and revision notes",
                "lock approved render source with hash/length before vendor calls",
            ],
            "promotion_gate": "UI guard passes and paid renders prove accepted output quality for short and long routes",
        },
        {
            "priority": "P0",
            "upgrade": "model_backed_reference_and_lipsync_qa",
            "external_pattern": "production-grade systems use reviewer/model loops for identity, spatial consistency, and defects",
            "source_evidence": ["OpenMontage", "One Sentence, One Drama", "ViMax / AI-Creator", "Jellyfish AI Short Drama Studio"],
            "current_status": "deterministic_qa_ready_model_qa_missing",
            "implementation_target": [
                "identity/product embedding similarity",
                "robust multilingual OCR and caption alignment",
                "lip-sync and speaker consistency score for dialogue routes",
                "cross-shot character/product/location continuity dimensions",
            ],
            "promotion_gate": "QA evidence plan passes for each promoted model/niche/runtime/market route",
        },
        {
            "priority": "P1",
            "upgrade": "agent_timeline_review_workspace",
            "external_pattern": "agentic editor surfaces expose timeline/caption/revision controls after generation",
            "source_evidence": ["Montaj agent timeline editor", "OpenMontage"],
            "current_status": "job_modal_partial",
            "implementation_target": [
                "clean timeline with clips, captions, voice/music lanes, and publish package",
                "regenerate selected shot without reopening manual model settings",
                "agent explanation for edit choices and failed QA reasons",
                "approve-export state for SaaS handoff",
            ],
            "promotion_gate": "reviewers can fix caption/cut/voice defects without leaving CineJelly or seeing provider internals",
        },
        {
            "priority": "P1",
            "upgrade": "accepted_render_memory_and_variant_chat",
            "external_pattern": "chat-native video agents keep project memory so accepted clips become reusable context for future edits and campaign variants",
            "source_evidence": ["Higgsfield MCP creative studio", "Higgsfield Supercomputer", "HeyGen rebuilt Video Agent"],
            "current_status": "asset_pins_and_job_history_partial",
            "implementation_target": [
                "save accepted render, hook, caption, storyboard, references, and QA score as reusable project memory",
                "let the user ask for variants from a previous clip through chat without selecting models or rebuilding the whole brief",
                "attach accepted-render memory to future preflight and benchmark evidence rows",
            ],
            "promotion_gate": "users can create approved variants from an accepted render while the UI remains chat-first and hides model/tool internals",
        },
        {
            "priority": "P1",
            "upgrade": "full_asset_library_and_entity_extraction",
            "external_pattern": "China short-drama systems extract characters, locations, props, costumes before generation",
            "source_evidence": ["Alibaba LumenX Studio", "Huobao Drama", "Jellyfish AI Short Drama Studio"],
            "current_status": "asset_pins_partial",
            "implementation_target": [
                "long script entity extraction",
                "character/product/location/style/voice asset records",
                "approval state, usage analytics, and series/campaign memory",
                "automatic pin suggestion before long-form graph render",
            ],
            "promotion_gate": "long-form jobs show asset bible completeness before the first paid video node",
        },
        {
            "priority": "P1",
            "upgrade": "benchmark_winning_seedance_prompt_bank",
            "external_pattern": "Seedance creators organize reusable templates by reference role, camera, transition, rhythm, and genre",
            "source_evidence": ["Awesome Seedance 2.0 Prompt and Examples", "Fal Seedance 2.0 Reference-to-Video Examples", "Seedance 2.0 docs"],
            "current_status": "formula_compiler_implemented_template_learning_missing",
            "implementation_target": [
                "persist accepted prompt formula per niche/runtime/model/market",
                "compare prompt variants in paid benchmark rows",
                "auto-select best formula for similar future briefs",
            ],
            "promotion_gate": "winning templates beat baseline on QA score, retry rate, and accepted-minute cost",
        },
        {
            "priority": "P1",
            "upgrade": "multi_candidate_hero_shot_selection",
            "external_pattern": "production workflows generate candidate frames/clips and pick the best for key beats",
            "source_evidence": ["Alibaba LumenX Studio", "ViMax / AI-Creator", "AniMaker"],
            "current_status": "creative_treatment_search_exists_candidate_video_selection_missing",
            "implementation_target": [
                "mark first frame, product close-up, character reveal, and twist/payoff as candidate-worthy",
                "generate 2-3 candidates only where budget policy allows",
                "select by identity/product/story/camera score before assembly",
            ],
            "promotion_gate": "accepted candidate route improves QA without unacceptable cost/latency",
        },
        {
            "priority": "P1",
            "upgrade": "long_form_error_recycling_and_keyframe_memory",
            "external_pattern": "long video systems reduce drift through keyframes, chaining, memory, and error recycling",
            "source_evidence": ["TTV Pipeline", "Stable Video Infinity", "StoryMem", "CoAgent"],
            "current_status": "graph_and_memory_contract_ready_error_recycling_missing",
            "implementation_target": [
                "store accepted keyframes from every successful node",
                "store drift/error signatures from failed nodes",
                "feed positive keyframes and negative constraints into rerender and next-scene prompts",
            ],
            "promotion_gate": "5-10m paid graph jobs pass continuity and retry-rate thresholds",
        },
    ]


def _implementation_score(patterns: list[dict[str, Any]]) -> dict[str, Any]:
    weights = {
        "implemented": 1.0,
        "implemented_benchmark_gated": 0.75,
        "implemented_needs_data": 0.7,
        "partial": 0.45,
        "missing": 0.0,
    }
    total = len(patterns)
    score = sum(weights.get(str(p.get("status")), 0.0) for p in patterns)
    return {
        "score": round((score / max(1, total)) * 100, 1),
        "pattern_count": total,
        "fully_implemented_count": sum(1 for p in patterns if p.get("status") == "implemented"),
        "partial_or_data_gated_count": sum(1 for p in patterns if p.get("status") != "implemented"),
        "top_tier_claim_allowed": False,
        "why": "Pattern coverage is strong, but production proof still depends on real benchmark outputs and model-backed QA.",
    }


__all__ = ["build_autonomous_competitive_research"]
