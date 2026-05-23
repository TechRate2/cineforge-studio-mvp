"""Claude API client với prompt caching để giảm 90% cost."""

import anthropic
from typing import Optional

from core.config import settings


class ClaudeClient:
    """Wrapper Claude API với prompt caching auto."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        few_shot_examples: Optional[list[dict]] = None,
        max_tokens: int = 4096,
    ) -> str:
        """Call Claude với caching system prompt + few-shot."""

        # Build messages array với few-shot
        messages = []

        if few_shot_examples:
            for ex in few_shot_examples:
                messages.append({"role": "user", "content": ex["input"]})
                messages.append({"role": "assistant", "content": ex["output"]})

        messages.append({"role": "user", "content": user_message})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},  # Cache 90% off
                }
            ],
            messages=messages,
        )

        return response.content[0].text

    def complete_with_image(
        self,
        system_prompt: str,
        user_message: str,
        image_url: str,
        max_tokens: int = 4096,
    ) -> str:
        """Call Claude với image (vision) — dùng cho avatar analyzer."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_message},
                        {
                            "type": "image",
                            "source": {"type": "url", "url": image_url},
                        },
                    ],
                }
            ],
        )

        return response.content[0].text


claude_client = ClaudeClient() if settings.anthropic_api_key else None
