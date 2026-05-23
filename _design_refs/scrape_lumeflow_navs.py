"""Retry-pass: visit Lumeflow sub-routes with domcontentloaded (networkidle fails on SPA).

Targets common reference routes (pricing, features, login) plus links extracted from homepage.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).parent
OUT = ROOT / "lumeflow"
URL = "https://www.lumeflow.ai"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Curated candidates + dedupe with homepage nav report
CANDIDATES = [
    "/pricing",
    "/pricing/",
    "/features",
    "/features/",
    "/login",
    "/signin",
    "/sign-in",
    "/app",
    "/app/",
    "/docs",
    "/about",
    "/blog",
]


def slugify(text: str) -> str:
    t = re.sub(r"[^a-zA-Z0-9-]+", "-", text.lower()).strip("-")
    return t[:40] or "page"


async def main() -> None:
    report = {"visited": [], "errors": []}
    # Augment with nav_links_found from previous run
    prev = OUT / "scrape-report.json"
    extra_paths: list[str] = []
    if prev.exists():
        try:
            data = json.loads(prev.read_text(encoding="utf-8"))
            for n in data.get("nav_links_found", []):
                href = n.get("href", "")
                if href.startswith("http") and "lumeflow.ai" not in href:
                    continue
                if href.startswith("javascript"):
                    continue
                extra_paths.append(href)
        except Exception:
            pass

    targets = list(dict.fromkeys(CANDIDATES + extra_paths))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=UA,
            locale="en-US",
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = await ctx.new_page()

        for t in targets:
            full = urljoin(URL, t) if t.startswith("/") else t
            host = urlparse(full).netloc
            if host and "lumeflow.ai" not in host:
                continue
            slug = slugify(urlparse(full).path or "home")
            out_path = OUT / f"route-{slug}.png"
            if out_path.exists():
                continue
            try:
                resp = await page.goto(full, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3500)
                status = resp.status if resp else None
                if status and status >= 400:
                    report["errors"].append(f"{full} -> HTTP {status}")
                    continue
                await page.screenshot(path=str(out_path), full_page=True)
                report["visited"].append({"url": full, "screenshot": str(out_path), "status": status})
                print(f"OK {full} -> {out_path.name}")
            except Exception as e:
                report["errors"].append(f"{full}: {type(e).__name__}: {str(e)[:150]}")
                print(f"FAIL {full}: {type(e).__name__}")

        await ctx.close()
        await browser.close()

    (OUT / "nav-pass-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"visited": len(report["visited"]), "errors": len(report["errors"])}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
