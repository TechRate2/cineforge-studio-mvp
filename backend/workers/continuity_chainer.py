"""Last-frame continuity chaining for segmented renders."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ContinuityChainState(BaseModel):
    """State carried between segment renders."""

    model_config = ConfigDict(extra="forbid")

    previous_shot_id: str | None = None
    previous_video_url: str | None = None
    previous_last_frame_url: str | None = None


class ContinuityChainer:
    """Apply previous last-frame URLs to subsequent render payloads."""

    def payload_for_next_segment(
        self,
        payload: dict,
        state: ContinuityChainState,
    ) -> dict:
        """Return payload updated with a last-frame continuity anchor when available."""
        if not state.previous_last_frame_url:
            return dict(payload)
        out = dict(payload)
        out["image"] = state.previous_last_frame_url
        out["images"] = [state.previous_last_frame_url]
        out["continuity_anchor"] = "previous_last_frame"
        return out

    def update_state(
        self,
        *,
        shot_id: str,
        video_url: str | None,
        last_frame_url: str | None,
        previous_state: ContinuityChainState | None = None,
    ) -> ContinuityChainState:
        """Return chain state after a segment render."""
        prior = previous_state or ContinuityChainState()
        return ContinuityChainState(
            previous_shot_id=shot_id,
            previous_video_url=video_url or prior.previous_video_url,
            previous_last_frame_url=last_frame_url or video_url or prior.previous_last_frame_url,
        )


__all__ = ["ContinuityChainer", "ContinuityChainState"]
