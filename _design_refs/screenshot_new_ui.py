"""Screenshot UI mới để đối chiếu với Lumeflow refs."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path(__file__).parent / "new_ui"
OUT.mkdir(exist_ok=True)

ROUTES = [
    ("/studio", "studio-1440.png"),
    ("/studio/history", "history-1440.png"),
    ("/studio/library", "library-1440.png"),
    ("/studio/text-to-video", "text-to-video.png"),
    ("/studio/voice", "voice.png"),
]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()
        for route, name in ROUTES:
            url = f"http://localhost:3000{route}"
            print(f"  - {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(1200)
                await page.screenshot(path=str(OUT / name), full_page=True)
                print(f"    saved {name}")
            except Exception as e:
                print(f"    fail {name}: {e}")
        # Mobile snapshot of /studio
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto("http://localhost:3000/studio", wait_until="domcontentloaded")
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(OUT / "studio-mobile.png"), full_page=True)
        await browser.close()
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
