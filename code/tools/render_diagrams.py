"""Render the diagrams in diagrams.html to PNG files in docs/diagrams/.

Uses Playwright with any local Chromium-based browser (set BROWSER_PATH),
falling back to Playwright's own Chromium.
"""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)
BROWSER = os.environ.get("BROWSER_PATH", "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe")


def launch(p):
    if Path(BROWSER).exists():
        return p.chromium.launch(executable_path=BROWSER, headless=True)
    return p.chromium.launch(headless=True)


if __name__ == "__main__":
    with sync_playwright() as p:
        b = launch(p)
        pg = b.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=2)
        pg.goto((Path(__file__).parent / "diagrams.html").as_uri())
        for name in ["workflow", "decomposition", "ioflow", "architecture"]:
            pg.locator(f"#{name}").screenshot(path=str(OUT / f"{name}.png"))
            print("wrote", name)
        b.close()
