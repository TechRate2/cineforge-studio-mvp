"""Scrape lumeflow.ai for design reference (no production asset download).

Outputs into ../_design_refs/lumeflow/ relative to this script:
  - home-1440.png  (desktop full-page)
  - home-mobile.png (390x844 full-page)
  - home-scroll-{N}.png (scroll snapshots, 200px steps, max 6000px)
  - dom.html  (body outerHTML)
  - computed-css.json  (computed styles for key selectors)
  - palette.json  (deduped non-null background colors)
  - nav-{slug}.png  (per discovered nav link)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

ROOT = Path(__file__).parent
OUT = ROOT / "lumeflow"
OUT.mkdir(parents=True, exist_ok=True)

URL = "https://www.lumeflow.ai"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

KEY_SELECTORS = {
    "html": "html",
    "body": "body",
    "header": "header, [class*=header], [class*=Header], nav",
    "nav": "nav, [role=navigation]",
    "hero_h1": "h1",
    "hero_section": "section:first-of-type, main > div:first-child, [class*=hero], [class*=Hero]",
    "button_primary": "button, a[class*=button], a[class*=Button], [class*=btn]",
    "card": "[class*=card], [class*=Card], article",
}

CSS_PROPS = [
    "background-color", "color", "font-family", "font-size", "font-weight",
    "line-height", "letter-spacing", "border-radius", "border", "box-shadow",
    "padding", "margin", "max-width", "display", "grid-template-columns",
    "gap", "backdrop-filter", "background-image",
]

JS_COMPUTED = """
([selectors, props]) => {
  const out = {};
  for (const [k, sel] of Object.entries(selectors)) {
    const el = document.querySelector(sel);
    if (!el) { out[k] = null; continue; }
    const cs = getComputedStyle(el);
    const o = { _selector_used: sel, _tag: el.tagName, _classes: el.className };
    for (const p of props) o[p] = cs.getPropertyValue(p);
    out[k] = o;
  }
  return out;
}
"""

JS_PALETTE = """
() => {
  const bgs = new Set();
  const colors = new Set();
  document.querySelectorAll('section, div, header, footer, nav, main, aside, button, a')
    .forEach(el => {
      const cs = getComputedStyle(el);
      const bg = cs.backgroundColor;
      const col = cs.color;
      if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') bgs.add(bg);
      if (col) colors.add(col);
    });
  return { backgrounds: [...bgs], colors: [...colors] };
}
"""

JS_NAV_LINKS = """
() => {
  const links = new Set();
  document.querySelectorAll('header a, nav a').forEach(a => {
    const href = a.getAttribute('href');
    if (!href) return;
    if (href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
    links.add(JSON.stringify({ text: (a.innerText || '').trim().slice(0, 40), href }));
  });
  return [...links].map(s => JSON.parse(s));
}
"""


def slugify(text: str) -> str:
    t = re.sub(r"[^a-zA-Z0-9-]+", "-", text.lower()).strip("-")
    return t[:40] or "page"


async def scrape() -> dict:
    report: dict = {"url": URL, "screenshots": [], "nav_routes": [], "errors": []}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=UA,
            locale="en-US",
            device_scale_factor=1,
        )
        # Light stealth: hide webdriver
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )

        page = await ctx.new_page()
        try:
            await page.goto(URL, wait_until="networkidle", timeout=60000)
        except PWTimeout:
            report["errors"].append("networkidle timeout, using domcontentloaded")
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        await page.wait_for_timeout(3000)

        # === Desktop full-page ===
        p_desktop = OUT / "home-1440.png"
        await page.screenshot(path=str(p_desktop), full_page=True)
        report["screenshots"].append(str(p_desktop))

        # === DOM body ===
        body_html = await page.evaluate("() => document.body.outerHTML")
        (OUT / "dom.html").write_text(body_html, encoding="utf-8")

        # === Title + meta ===
        title = await page.title()
        report["title"] = title

        # === Computed CSS for key selectors ===
        computed = await page.evaluate(JS_COMPUTED, [KEY_SELECTORS, CSS_PROPS])
        (OUT / "computed-css.json").write_text(
            json.dumps(computed, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # === Palette ===
        palette = await page.evaluate(JS_PALETTE)
        (OUT / "palette.json").write_text(
            json.dumps(palette, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # === Nav links ===
        nav_links = await page.evaluate(JS_NAV_LINKS)
        report["nav_links_found"] = nav_links

        # === Scroll snapshots (desktop) ===
        scroll_count = 0
        for i, y in enumerate(range(200, 6001, 800)):  # 200,1000,1800,...
            try:
                await page.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}});")
                await page.wait_for_timeout(700)
                p = OUT / f"home-scroll-{i+1}.png"
                await page.screenshot(path=str(p), full_page=False)
                report["screenshots"].append(str(p))
                scroll_count += 1
            except Exception as e:
                report["errors"].append(f"scroll-{i}: {e}")
                break
        report["scroll_snapshots"] = scroll_count

        # === Mobile ===
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.evaluate("window.scrollTo(0,0)")
        await page.wait_for_timeout(1500)
        p_mobile = OUT / "home-mobile.png"
        await page.screenshot(path=str(p_mobile), full_page=True)
        report["screenshots"].append(str(p_mobile))

        # Back to desktop
        await page.set_viewport_size({"width": 1440, "height": 900})
        await page.evaluate("window.scrollTo(0,0)")
        await page.wait_for_timeout(800)

        # === Visit nav routes (same host only, max 5) ===
        seen = set()
        host = urlparse(URL).netloc
        for nav in nav_links:
            href = nav.get("href", "")
            text = nav.get("text", "")
            if not href:
                continue
            full = urljoin(URL, href)
            if urlparse(full).netloc and urlparse(full).netloc != host:
                continue
            if full in seen or full == URL.rstrip("/") + "/":
                continue
            if len(seen) >= 5:
                break
            seen.add(full)
            slug = slugify(text or urlparse(full).path or "page")
            try:
                await page.goto(full, wait_until="networkidle", timeout=45000)
                await page.wait_for_timeout(2000)
                p = OUT / f"nav-{slug}.png"
                await page.screenshot(path=str(p), full_page=True)
                report["screenshots"].append(str(p))
                report["nav_routes"].append({"text": text, "url": full, "screenshot": str(p)})
            except Exception as e:
                report["errors"].append(f"nav {full}: {type(e).__name__}: {str(e)[:120]}")

        await ctx.close()
        await browser.close()

    (OUT / "scrape-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    r = asyncio.run(scrape())
    print(json.dumps(
        {
            "title": r.get("title"),
            "screenshots_count": len(r["screenshots"]),
            "scroll_snapshots": r.get("scroll_snapshots"),
            "nav_routes": len(r["nav_routes"]),
            "errors": r["errors"],
        },
        indent=2,
    ))
