"""LLM Router — unified interface route giữa AtlasCloud (DeepSeek/Qwen/Claude) vs Anthropic direct.

Mục tiêu: thay `from vendors.anthropic_client import claude_client` bằng `from vendors.llm_router import llm`
mà không phải sửa logic agent.

Routing default (override qua env):
    analyzer task (insight extraction, short)  → deepseek-v4-flash   ($0.14/$0.28)
    generator task (prompt crafting, reasoning) → deepseek-v4-pro     ($1.68/$3.38)
    vision task (analyze ảnh sản phẩm)         → qwen3-vl-30b-instruct ($0.15/$0.60)
    premium opt-in                              → claude-sonnet-4.6   ($3/$15)

Fallback: nếu AtlasCloud LLM trả 402 (out of credit) → tự switch Claude direct.
"""

from typing import Optional, Literal
import httpx
from loguru import logger

from core.config import settings


TaskType = Literal["analyzer", "generator", "vision", "premium"]


class LLMRouter:
    """Route LLM call theo task type — abstract provider dưới hood."""

    def __init__(self):
        self.provider = settings.llm_provider  # "atlascloud" | "anthropic"
        self._atlas = None
        self._claude = None
        # Lazy init — chỉ instantiate khi cần
        if settings.atlascloud_api_key:
            from vendors.atlascloud_llm import atlas_llm
            self._atlas = atlas_llm
        if settings.anthropic_api_key:
            from vendors.anthropic_client import claude_client
            self._claude = claude_client

    def _resolve_model(self, task: TaskType, override: Optional[str] = None) -> tuple[str, str]:
        """Trả (provider, model_id) theo task type.

        Lưu ý: AtlasCloud có Anthropic Claude trong catalog (`anthropic/claude-sonnet-4.6`)
        với cùng pricing API direct. Default route Claude qua AtlasCloud — tiết kiệm setup,
        cùng wallet $50 Pay-as-you-go. Chỉ fallback Anthropic SDK khi AtlasCloud trả 402 + Anthropic key set.
        """
        if override:
            # Caller specify trực tiếp:
            #   "claude-*"     → Anthropic SDK direct (bypass AtlasCloud)
            #   "anthropic/*"  → AtlasCloud Claude proxy (Coding Plan rate)
            #   other          → AtlasCloud catalog (deepseek/qwen/...)
            # FIX N1: Bỏ điều kiện `and not override.startswith("claude-")` luôn False
            # (dead code) → giờ route Anthropic direct hoạt động đúng.
            if override.startswith("claude-"):
                return ("anthropic", override)
            return ("atlascloud", override)

        # Default routing — TẤT CẢ qua AtlasCloud (1 wallet, 1 key)
        if task == "analyzer":
            return ("atlascloud", settings.llm_model_analyzer)
        if task == "generator":
            return ("atlascloud", settings.llm_model_generator)
        if task == "vision":
            return ("atlascloud", settings.llm_model_vision)
        if task == "premium":
            # Claude Sonnet 4.6 qua AtlasCloud (not Anthropic SDK direct)
            return ("atlascloud", "anthropic/claude-sonnet-4.6")
        raise ValueError(f"Unknown task type: {task}")

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        task: TaskType = "analyzer",
        model: Optional[str] = None,
        few_shot_examples: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Route theo task. Fallback Anthropic direct khi AtlasCloud out-of-credit (402)."""
        provider, model_id = self._resolve_model(task, model)

        # Try primary provider
        if provider == "atlascloud":
            if not self._atlas:
                logger.warning("AtlasCloud LLM key chưa set — fallback Anthropic")
                return self._call_claude(system_prompt, user_message, few_shot_examples, max_tokens)
            try:
                return self._atlas.complete(
                    system_prompt, user_message, model=model_id,
                    few_shot_examples=few_shot_examples,
                    max_tokens=max_tokens, temperature=temperature,
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 402:
                    logger.warning(
                        f"[LLM Router] AtlasCloud 402 insufficient balance — fallback Claude direct"
                    )
                    return self._call_claude(system_prompt, user_message, few_shot_examples, max_tokens)
                raise

        # Anthropic direct
        return self._call_claude(system_prompt, user_message, few_shot_examples, max_tokens)

    def complete_with_image(
        self,
        system_prompt: str,
        user_message: str,
        image_urls: list[str],
        task: TaskType = "vision",
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> str:
        """Vision call. Prefer Qwen3-VL trên AtlasCloud (rẻ 5×), fallback Claude direct."""
        provider, model_id = self._resolve_model(task, model)

        if provider == "atlascloud" and self._atlas:
            try:
                return self._atlas.complete_with_image(
                    system_prompt, user_message, image_urls, model=model_id, max_tokens=max_tokens
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 402:
                    logger.warning("[LLM Router] AtlasCloud vision 402 — fallback Claude direct")
                    return self._call_claude_vision(system_prompt, user_message, image_urls, max_tokens)
                raise

        return self._call_claude_vision(system_prompt, user_message, image_urls, max_tokens)

    def _call_claude(
        self,
        system_prompt: str,
        user_message: str,
        few_shot_examples: Optional[list[dict]],
        max_tokens: int,
    ) -> str:
        if not self._claude:
            raise RuntimeError("ANTHROPIC_API_KEY chưa set + AtlasCloud LLM cũng không khả dụng")
        return self._claude.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            few_shot_examples=few_shot_examples,
            max_tokens=max_tokens,
        )

    def _call_claude_vision(
        self, system_prompt: str, user_message: str, image_urls: list[str], max_tokens: int
    ) -> str:
        """Native Claude vision — multi-image content blocks."""
        if not self._claude:
            raise RuntimeError("Vision fallback needs ANTHROPIC_API_KEY")
        content_blocks: list[dict] = [{"type": "text", "text": user_message}]
        for url in image_urls[:12]:
            if not url:
                continue
            if url.startswith("data:image"):
                header, b64 = url.split(",", 1)
                media_type = header.split(";")[0].replace("data:", "")
                content_blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64},
                })
            else:
                content_blocks.append({
                    "type": "image",
                    "source": {"type": "url", "url": url},
                })
        response = self._claude.client.messages.create(
            model=self._claude.model,
            max_tokens=max_tokens,
            system=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": content_blocks}],
        )
        return response.content[0].text


# Singleton
llm = LLMRouter()
