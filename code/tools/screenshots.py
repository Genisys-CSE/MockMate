"""Drive the running Streamlit app with Playwright and save screenshots of real runs.

Usage: py code/tools/screenshots.py [base_url]
(default base_url http://localhost:8501)
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.render_diagrams import launch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"

PARTIAL_DEMO_ANSWER = None  # filled at runtime for the interview question


def wait_idle(pg, timeout=150):
    """Wait until Streamlit has no running spinner."""
    t0 = time.time()
    time.sleep(1.5)
    while time.time() - t0 < timeout:
        if pg.locator('[data-testid="stSpinner"]').count() == 0 and pg.locator('[data-testid="stStatusWidget"]').count() == 0:
            time.sleep(1.0)
            if pg.locator('[data-testid="stSpinner"]').count() == 0:
                return
        time.sleep(1)


def pick(pg, label, option):
    pg.get_by_label(label).first.click()
    pg.get_by_role("option", name=option).first.click()
    time.sleep(1)


def lab_run(pg, question, sample, name):
    pg.get_by_role("tab", name="Prompt lab").click()
    q = pg.get_by_label("Question", exact=True)
    q.fill(question)
    q.press("Enter")
    time.sleep(1)
    pick(pg, "Sample answer", sample)
    pg.get_by_role("button", name="Run v1 and v4").click()
    wait_idle(pg)
    pg.get_by_text("v4 - final prompt").first.wait_for(timeout=120000)
    time.sleep(2)
    pg.screenshot(path=str(OUT / name))
    print("saved", name)


def main():
    with sync_playwright() as p:
        b = launch(p)
        pg = b.new_page(viewport={"width": 1440, "height": 1250}, device_scale_factor=1.25)
        pg.goto(BASE)
        pg.get_by_text("MockMate").first.wait_for(timeout=60000)
        time.sleep(3)

        # S1 - same input as Test 7 (partial process-vs-thread answer)
        lab_run(pg, "What is the difference between a process and a thread?", "Partial answer", "S1_T7_prompt_lab.png")
        # S2 - same input type as Test 13 (prompt injection)
        lab_run(pg, "What is a deadlock and how can it be prevented?", "Injection attempt", "S2_T13_injection.png")

        # S3 - full interview: Test 1 setup (SWE Intern, Technical) -> P2 -> P3 (Test 8)
        pg.reload()
        pg.get_by_text("MockMate").first.wait_for(timeout=60000)
        time.sleep(3)
        pg.get_by_role("button", name="Start new interview").click()
        wait_idle(pg)
        pg.get_by_text("Question 1 of").first.wait_for(timeout=120000)
        question = pg.locator(".mm-q").first.inner_text()
        print("Q1:", question)
        from mockmate import llm  # noqa: E402

        demo = llm.generate(
            "",
            "Write a short, partly correct answer (2-3 sentences, simple English, no examples, no complexity) that a "
            "nervous final-year student might type in a mock interview for this question. Output only the answer.\n\n"
            + question,
            model=llm.OPEN_MODEL,
        ).text.strip()
        (OUT / "S3_demo_answer.txt").write_text(f"Question: {question}\nDemo answer: {demo}\n", encoding="utf-8")
        pg.get_by_label("Your answer").fill(demo)
        pg.get_by_role("button", name="Submit answer").click()
        wait_idle(pg, 200)
        pg.get_by_text("Follow-up question").first.wait_for(timeout=150000)
        time.sleep(2)
        pg.screenshot(path=str(OUT / "S3_T1_T8_interview.png"))
        print("saved S3")

        # S4 - skip the other questions and get the report
        for _ in range(5):
            if pg.get_by_role("button", name="Finish and get my report ➜").count():
                pg.get_by_role("button", name="Finish and get my report ➜").click()
                break
            pg.get_by_role("button", name="Next question ➜").click()
            wait_idle(pg)
            pg.get_by_role("button", name="Skip question").click()
            wait_idle(pg)
        wait_idle(pg, 200)
        pg.get_by_text("Overall summary").first.wait_for(timeout=150000)
        time.sleep(2)
        pg.screenshot(path=str(OUT / "S4_report.png"))
        print("saved S4")
        b.close()


if __name__ == "__main__":
    main()
