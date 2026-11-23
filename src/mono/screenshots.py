"""Render the shared HTML as README PNG sheets using Chromium."""

import shutil

from mono.paths import IMAGES
from mono.site import SITE

SHEETS = {"hero": 220, "grid": 300, "design": 560, "features": 600}


def render():
    from playwright.sync_api import sync_playwright

    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if not chromium:
        raise RuntimeError("Chromium not found; run inside nix develop")
    if not (SITE / "index.html").is_file():
        raise RuntimeError("Run uv run site before screenshots")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=chromium)
        try:
            page = browser.new_page(
                viewport={"width": 880, "height": 700}, device_scale_factor=2, color_scheme="light"
            )
            IMAGES.mkdir(parents=True, exist_ok=True)
            for sheet, height in SHEETS.items():
                for theme in ("light", "dark"):
                    page.set_viewport_size({"width": 880, "height": height})
                    page.goto((SITE / "index.html").as_uri() + f"?poster={sheet}&theme={theme}")
                    page.evaluate("document.fonts.ready")
                    bounds = page.locator(f'[data-sheet="{sheet}"]').bounding_box()
                    if bounds is None or bounds["y"] + bounds["height"] > height:
                        raise ValueError(f"{sheet} exceeds its {height}px sheet: {bounds}")
                    page.screenshot(path=str(IMAGES / f"specimen-{sheet}-{theme}.png"))
        finally:
            browser.close()


def main():
    render()
