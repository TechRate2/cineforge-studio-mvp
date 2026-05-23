"""Vidu Q3 Mix Strategy — premium 1080p variant của Vidu Q3.

Identical format với ViduQ3Strategy nhưng:
    - Resolution lock 1080p (model spec restrict)
    - Cost 2.5× ($0.106/s vs $0.042/s)
    - Use case: final cut premium, brand showcase, không phải iteration

Sweet spot:
    - Cùng pattern Vidu Q3 nhưng output 1080p HD
    - Cho tier subscription cao (anh bán $19-49/tháng)
"""

from agent.strategies.vidu_q3 import ViduQ3Strategy
from agent.strategies.base import Script


class ViduQ3MixStrategy(ViduQ3Strategy):
    user_model = "vidu_q3_mix"
    atlas_model_key = "vidu_q3_mix_ref"
    display_name_vn = "Vidu Q3 Mix — Premium 1080p multi-character"

    def suitability_score(self, script: Script) -> float:
        """Wins khi: ViduQ3 fit + user muốn premium 1080p."""
        base = super().suitability_score(script)
        # Premium bonus khi resolution hint là 1080p
        if script.resolution_hint == "1080p":
            base += 0.1
        # Trừ điểm nếu là iteration/preview (Q3 thường rẻ hơn 2.5x)
        if script.style in ("preview", "iteration"):
            base -= 0.3
        return max(0.0, min(base, 1.0))

    def reasoning_for_script(self, script: Script) -> str:
        return super().reasoning_for_script(script) + " · Premium 1080p HD output"

    def build_prompt(self, script, keyframes=None, audio_urls=None):
        # Force 1080p (Vidu Q3 Mix chỉ support 1080p per spec)
        original_res = script.resolution_hint
        script.resolution_hint = "1080p"
        try:
            job = super().build_prompt(script, keyframes, audio_urls)
            # Override model_key + atlas endpoint
            job.model_key = self.atlas_model_key
            job.payload["model"] = "vidu/q3-mix/reference-to-video"
            job.payload["resolution"] = "1080p"
            job.strategy_name = self.display_name_vn
            job.reasoning = self.reasoning_for_script(script)
            return job
        finally:
            script.resolution_hint = original_res
