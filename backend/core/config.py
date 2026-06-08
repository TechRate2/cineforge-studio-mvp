"""Settings loader từ environment variables.

Đọc theo thứ tự (file sau ghi đè file trước):
    1. ../.env.local      (root monorepo — chia sẻ với Next.js)
    2. ./.env             (backend-only override, optional)
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_MONOREPO_ROOT = _BACKEND_ROOT.parent


class Settings(BaseSettings):
    """App settings — load từ .env.local (root) + .env (backend optional)."""

    model_config = SettingsConfigDict(
        env_file=(
            str(_MONOREPO_ROOT / ".env.local"),
            str(_BACKEND_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # AI / LLM — multi-provider routing
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"  # premium fallback only

    # LLM router config — per-task model selection
    # Default DeepSeek V4 Flash (50× rẻ Claude Sonnet, vẫn đủ cho prompt gen)
    llm_provider: str = "atlascloud"  # "atlascloud" | "anthropic"
    llm_model_analyzer: str = "deepseek-ai/deepseek-v4-flash"  # cheap fast for insight extraction
    # V5.5 — switched default generator to flash. Pro is 12× more expensive
    # ($1.68/$3.38 per 1M tokens vs $0.14/$0.28) and the cost/quality ratio
    # tilted in flash's favor after Director Agent V4 prompt hardening +
    # storytelling validators fix drift downstream. Override LLM_MODEL_GENERATOR
    # env to opt back into pro for premium tier.
    llm_model_generator: str = "deepseek-ai/deepseek-v4-flash"
    llm_model_vision: str = "qwen/qwen3-vl-30b-a3b-instruct"   # vision-capable (product image analysis)
    llm_model_premium: str = "anthropic/claude-sonnet-4.6"     # opt-in premium
    llm_allow_pro_for_complex_brief: bool = False              # cost guard: Pro only when explicitly enabled
    llm_allow_premium_brain: bool = False                      # cost guard: Claude brain only when explicitly enabled

    # AtlasCloud — 2 wallet riêng, 2 key riêng
    # Pay-as-you-go: image/video/upload via /api/v1/model/*
    atlascloud_api_key: str = ""
    atlascloud_base_url: str = "https://api.atlascloud.ai/api/v1"
    # Coding Plan: LLM (DeepSeek/Qwen/Claude) via /v1/chat/completions
    atlascloud_llm_api_key: str = ""
    atlascloud_llm_base_url: str = "https://api.atlascloud.ai/v1"

    # GenMax (primary TTS VN) — aggregator ElevenLabs + MiniMax
    # Doc: https://genmax.io/app/api-docs
    # 12 voice VN preset (6 ElevenLabs + 6 MiniMax) hardcode trong vendors/genmax.py
    genmax_api_key: str = ""
    genmax_base_url: str = "https://api.genmax.io"
    genmax_default_voice_id: str = "d5HVupAWCwe4e6GvMCAL"  # Mai — ElevenLabs natural female

    # ElevenLabs SFX (cho ASMR mode — sound effects)
    elevenlabs_api_key: str = ""

    # Cloudflare R2
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "ugc-vietnam-output"
    r2_public_url: str = ""
    r2_endpoint_url: str = ""
    r2_presigned_url_expires_s: int = 7 * 24 * 60 * 60
    r2_final_video_access_mode: str = "auto"  # auto | public | private
    r2_final_video_presigned_expires_s: int = 90 * 24 * 60 * 60
    r2_presigned_refresh_enabled: bool = True
    r2_upload_max_attempts: int = 3
    allow_r2_local_fallback: bool = False

    # Post-render visual consistency probe. Uses OpenCV locally to derive
    # deterministic CV signals from rendered segment videos and reference
    # images before the policy evaluator scores them.
    post_render_cv_probe_enabled: bool = True
    post_render_cv_probe_max_frames: int = 8
    post_render_cv_probe_download_timeout_s: int = 30
    post_render_cv_probe_enable_embedding: bool = True
    post_render_cv_probe_embedding_model_path: str = ""
    post_render_cv_probe_embedding_input_size: int = 224
    post_render_cv_probe_max_regions: int = 8
    post_render_cv_probe_frame_strategy: str = "smart"

    # Database & Cache
    database_url: str = "postgresql://postgres:mypass@localhost:5432/ugc_vn"
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_env: str = "development"
    app_port: int = 8000
    worker_concurrency: int = 4
    ffmpeg_bin: str = ""
    ffprobe_bin: str = ""

    # V3 CRITICAL C1 — Admin key guards mutating /api/v1/admin/* endpoints.
    # Set `ADMIN_API_KEY` env in production. When empty, admin mutations are
    # ONLY allowed when `app_env=='development'` (localhost dev convenience).
    admin_api_key: str = ""

    # Direct image/video/audio generate endpoints bypass the autonomous Agent.
    # Keep them off by default for SaaS safety; normal users should use the
    # approved autonomous render flow instead of direct vendor submission.
    allow_direct_paid_generation: bool = False

    # Paths
    base_dir: Path = Path(__file__).parent.parent
    templates_dir: Path = Path(__file__).parent.parent / "templates"
    prompts_dir: Path = Path(__file__).parent.parent / "prompts"
    sfx_library_dir: Path = Path(__file__).parent.parent / "sfx_library"


settings = Settings()
