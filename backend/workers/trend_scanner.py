"""Trend Scanner — Background worker scan TikTok/X VN trends mỗi 6h.

Schedule (Dramatiq cron + Redis):
    @actor(periodic, every="6h")
    def scan_trends_task():
        scan_tiktok_vn()
        scan_x_twitter_vn()
        cleanup_expired()

Strategy:
    1. **TikTok scrape via Scrapling** — fetch trending hashtags/sounds VN
    2. **X/Twitter via API or scrape** — keyword "viral tiktok" filter VN
    3. **LLM classifier** (DeepSeek V4 Flash) parse raw scrape → structured Trend objects
    4. Upsert vào trend_cache.db
    5. Soft-delete trends > 60 days

Current status: SKELETON với 1 manual seed function. Production wiring (Dramatiq)
sẽ làm Week 4 cùng với worker chain render.

Manual usage (Week 3-4):
    python -m workers.trend_scanner --manual-seed
    python -m workers.trend_scanner --scan-tiktok
"""

import argparse
import json
import re
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from agent.trend_cache import insert_scanned_trend, log_scan
from vendors.llm_router import llm


# ============================================
# TikTok VN scraper (skeleton)
# ============================================

TIKTOK_VN_DISCOVER_URL = "https://www.tiktok.com/discover/vietnam"


def scan_tiktok_vn(max_trends: int = 20) -> int:
    """Scan TikTok VN trending → extract + structure → insert to trend_cache.

    Returns:
        count of trends inserted.

    NOTE: TikTok có Cloudflare/Akamai anti-bot rất mạnh. Production sẽ dùng:
        - Scrapling (đã có trong requirements.txt) với StealthyFetcher
        - HOẶC TikTok unofficial API (TikAPI/ScrapeCreators)

    Hiện stub — Week 4 sẽ implement full.
    """
    logger.info("[TrendScanner] scanning TikTok VN (stub Week 4)")

    # Stub: trả 0 + log để pipeline test
    log_scan(source="tiktok_vn", items_found=0, status="stub_week4")
    return 0


# ============================================
# X/Twitter VN scraper (skeleton)
# ============================================

def scan_x_twitter_vn(max_trends: int = 10) -> int:
    """Scan X/Twitter VN cho viral content + UGC discussions.

    Search queries:
        - "viral tiktok" lang:vi
        - "trend mới" lang:vi
        - keyword theo từng niche (beauty, tech, food, ...)

    Hiện stub — Week 4 implement.
    """
    logger.info("[TrendScanner] scanning X/Twitter VN (stub Week 4)")
    log_scan(source="x_twitter_vn", items_found=0, status="stub_week4")
    return 0


# ============================================
# LLM classifier — parse raw scrape → structured Trend
# ============================================

TREND_CLASSIFIER_SYSTEM = """Bạn là trend analyst TikTok VN.

Input: raw scraped data (hashtags, sound titles, post examples).
Output: list of TrendObject JSON với fields:
{
  "trend_id": "snake_case_unique",
  "title": "Tên trend ngắn",
  "description": "1 câu mô tả format",
  "format_type": "POV | curiosity_gap | controversial | satisfying_visual_proof | authority | community",
  "target_niches": "comma-separated (beauty,tech,fashion,food,supplement)",
  "audience_age_min": int,
  "audience_age_max": int,
  "trending_score": 1-10,
  "raw_example": "1 câu ví dụ tiếng Việt"
}

Output: JSON array, KHÔNG markdown.
"""


def classify_raw_to_trends(raw_text: str, source: str) -> list[dict]:
    """LLM parse raw scrape → list of structured trends."""
    response = llm.complete(
        system_prompt=TREND_CLASSIFIER_SYSTEM,
        user_message=f"Source: {source}\n\nRaw data:\n{raw_text}",
        task="analyzer",
        max_tokens=3000,
        temperature=0.3,
    )

    # Try array parse first
    try:
        match = re.search(r"\[[\s\S]*\]", response)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass

    logger.warning(f"[TrendScanner] classifier failed parse: {response[:200]}")
    return []


# ============================================
# Manual seed — extend default seeds
# ============================================

MANUAL_SEED_TRENDS_2026 = [
    {
        "trend_id": "tet_2026_outfit_lookbook",
        "title": "Tết 2026 Outfit Lookbook",
        "description": "OOTD cho Tết với multiple outfits transition match cut",
        "format_type": "satisfying_visual_proof",
        "target_niches": "fashion,beauty,lifestyle",
        "audience_age_min": 18,
        "audience_age_max": 35,
        "trending_score": 9,
        "raw_example": "Outfit Tết 2026 — 5 looks chuẩn duyên dáng",
        "expires_at": "2026-02-15T00:00:00",
    },
    {
        "trend_id": "macro_food_asmr_2026",
        "title": "Macro Food ASMR",
        "description": "Close-up cực gần food + ASMR sound, minimal voiceover",
        "format_type": "satisfying_visual_proof",
        "target_niches": "food",
        "audience_age_min": 18,
        "audience_age_max": 40,
        "trending_score": 10,
        "raw_example": "Macro tiếng phở chan + sồi nước béo",
    },
    {
        "trend_id": "valentine_2026_couple_pov",
        "title": "Valentine 2026 Couple POV",
        "description": "POV first-person gift exchange / shared moment",
        "format_type": "relatable_emotion",
        "target_niches": "beauty,fashion,lifestyle,food",
        "audience_age_min": 18,
        "audience_age_map": 32,
        "trending_score": 8,
        "raw_example": "POV: nhận gift Valentine từ người ấy",
        "expires_at": "2026-02-20T00:00:00",
    },
]


def manual_seed():
    """Insert manual seed trends (vd: Tết, Valentine, seasonal)."""
    count = 0
    for trend in MANUAL_SEED_TRENDS_2026:
        try:
            insert_scanned_trend(trend)
            count += 1
        except Exception as e:
            logger.error(f"[TrendScanner] manual seed fail {trend.get('trend_id')}: {e}")
    logger.info(f"[TrendScanner] manual seed: {count}/{len(MANUAL_SEED_TRENDS_2026)} inserted")
    return count


# ============================================
# CLI entry
# ============================================

def main():
    parser = argparse.ArgumentParser(description="Trend Scanner CLI")
    parser.add_argument("--manual-seed", action="store_true", help="Insert seasonal seeds")
    parser.add_argument("--scan-tiktok", action="store_true", help="Scan TikTok VN (Week 4 stub)")
    parser.add_argument("--scan-x", action="store_true", help="Scan X/Twitter VN (Week 4 stub)")
    parser.add_argument("--scan-all", action="store_true", help="Scan all sources")

    args = parser.parse_args()

    if args.manual_seed:
        manual_seed()
    if args.scan_tiktok or args.scan_all:
        scan_tiktok_vn()
    if args.scan_x or args.scan_all:
        scan_x_twitter_vn()

    if not any([args.manual_seed, args.scan_tiktok, args.scan_x, args.scan_all]):
        parser.print_help()


if __name__ == "__main__":
    main()
