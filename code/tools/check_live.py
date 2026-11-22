"""Open the deployed app in a fresh (logged-out) headless browser and check it
really works: banner shows, no API-key box, and an interview can start.

Usage: py code/tools/check_live.py [url]
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.render_diagrams import launch  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "https://mockmate-pe-b13-42.streamlit.app"
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots" / "live_app.png"

with sync_playwright() as p:
    b = launch(p)
    pg = b.new_page(viewport={"width": 1440, "height": 1100})
    pg.goto(URL, timeout=90000)
    app = None
    for _ in range(60):  # the app runs inside an iframe on streamlit.app
        for fr in pg.frames:
            try:
                if fr.get_by_text("MockMate").count() and fr.get_by_role("button", name="Start new interview").count():
                    app = fr
            except Exception:
                pass
        if app:
            break
        wake = pg.get_by_role("button", name="Yes, get this app back up!")
        if wake.count():
            wake.click()
        time.sleep(3)
    if not app:
        pg.screenshot(path=str(OUT))
        sys.exit("FAIL: app UI not found (see live_app.png)")
    if app.get_by_text("Gemini API key").count():
        sys.exit("FAIL: key box shown - secret not set")
    app.get_by_role("button", name="Start new interview").click()
    app.get_by_text("Question 1 of").first.wait_for(timeout=120000)
    print("OK:", app.locator(".mm-q").first.inner_text())
    pg.screenshot(path=str(OUT))
    b.close()
