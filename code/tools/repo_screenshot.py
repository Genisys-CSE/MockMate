"""Screenshot the public GitHub repo page (logged out) for Section 5."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.render_diagrams import launch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
with sync_playwright() as p:
    b = launch(p)
    pg = b.new_page(viewport={"width": 1280, "height": 1000}, device_scale_factor=1.25)
    pg.goto("https://github.com/Genisys-CSE/MockMate", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)
    pg.screenshot(path=str(ROOT / "docs" / "screenshots" / "repo.png"), clip={"x": 0, "y": 0, "width": 1190, "height": 1000})
    print("saved repo.png")
    b.close()
