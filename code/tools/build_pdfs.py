"""Build the Milestone 2 PDF, the technical report PDF and the form cheat sheet
from the same data files (prompts/, test-data/), so every number matches.

Usage:
  py code/tools/build_pdfs.py --reel-url URL --reel-seconds 120
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.render_diagrams import launch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
TD = ROOT / "test-data"
SUB = ROOT / "submission"  # local only (git-ignored): files to upload to the form
SUB.mkdir(exist_ok=True)

TEAM_ID = "PE-B13-42"
TEAM = "MockMate"
TITLE = "MockMate - AI Mock-Interview Coach for Placement Prep"
BATCH = "B13 - B24"
FACULTY = "Dr. Sonal Kukreja"
COURSE = "SCSE4041 Prompt Engineering - Mini Project, Milestone 2"
PROTOTYPE = "https://mockmate-pe-b13-42.streamlit.app"
REPO = "https://github.com/Genisys-CSE/MockMate"
MEMBERS = [
    ("Yug Chaturvedi (Team leader)", "S24CSEU1260", "Team lead, solution architect and prompt design lead",
     "Led the team and split the work; designed the 4-prompt chain (P1-P4) and the 1-5 rubric; wrote all four final prompts and "
     "Evaluator versions v1-v4 with few-shot anchors and guard rules; analysed the iteration results and decided each change; "
     "set the model choice (Flash-Lite + fallback); reviewed the final app, test results and this PDF before submission",
     "prompts/final/P1-P4, prompts/v1-v3, Section 2 (design + prompt sheets), Section 3 iteration log, CHANGELOG", 34),
    ("Aditi Tripathi", "S24CSEU1268", "Testing and evaluation",
     "Designed the 23 test cases with expected outputs; ran the v1-v4 experiment; recorded pass/fail and failure analysis",
     "code/run_tests.py, code/run_iterations.py, test-data/, Section 4", 22),
    ("Shivraj Singh Bhati", "S24CSEU0511", "App development and deployment",
     "Built the Streamlit app, Gemini wrapper with retry and fallback, code guards; deployed on Streamlit Cloud",
     "code/app.py, code/mockmate/, prototype link", 22),
    ("Aryan Singh", "S24CSEU1256", "Documentation and diagrams",
     "Drew the 4 diagrams; wrote README, Milestone 2 PDF and the technical report",
     "code/tools/diagrams.html, docs/, README.md, Sections 1, 5, 6", 22),
]

PROMPT_INFO = {
    "P1": dict(file="prompts/final/P1_planner.txt", name="Question Planner", step="Step 1 of 4",
               purpose="Write role- and round-specific interview questions with the key points of a strong answer.",
               settings="temperature 0.7, response_mime_type application/json + response_schema (Plan), thinking level low",
               variables=[("role", "job role chosen by the student"), ("round", "Technical / HR / Behavioural / Managerial"),
                          ("difficulty", "Easy / Medium / Hard"), ("n_questions", "number of questions (2-5)")],
               examples="0 (zero-shot; rules list the topics per round type)",
               output="JSON: {role_ok, questions:[{question, topic, difficulty, key_points[]}]}", sample="T1"),
    "P2": dict(file="prompts/final/P2_evaluator.txt", name="Answer Evaluator (v4, final)", step="Step 2 of 4 (re-used for the follow-up answer)",
               purpose="Score one answer 1-5 on correctness, depth, structure and clarity with verbatim quotes as evidence.",
               settings="temperature 0.2, response_mime_type application/json + response_schema (Evaluation), thinking level low",
               variables=[("role", "job role"), ("round", "round type"), ("question", "question from P1 (or the P3 follow-up)"),
                          ("key_points", "key points from P1 ('not given' for follow-ups / Prompt lab)"), ("answer", "student's typed answer (max 4000 chars)")],
               examples="2 (one weak answer scored 4/2/3/4, one strong answer scored 5/5/5/4)",
               output="JSON: {valid_answer, injection_detected, scores{4}, evidence[{criterion, quote, comment}], weakest_area, strengths[], improvements[]}; code then adds verified quotes, removed_quotes and overall",
               sample="T7"),
    "P3": dict(file="prompts/final/P3_followup.txt", name="Follow-up Generator", step="Step 3 of 4",
               purpose="Ask one follow-up question that probes the weakest area of the student's answer.",
               settings="temperature 0.5, response_mime_type application/json + response_schema (FollowUp), thinking level low",
               variables=[("role", "job role"), ("round", "round type"), ("question", "original question"), ("answer", "student's answer"),
                          ("valid_answer", "true/false from P2"), ("weakest_area", "lowest-scoring criterion (computed in code)"),
                          ("weak_comment", "P2's comment for that criterion")],
               examples="0 (rules map each weak area to a type of probe)",
               output="JSON: {follow_up, targets, why}", sample="T8"),
    "P4": dict(file="prompts/final/P4_report.txt", name="Feedback Report Writer", step="Step 4 of 4",
               purpose="Turn the whole interview into a short report with strengths, gaps and a 7-day practice plan.",
               settings="temperature 0.4, plain text (Markdown), thinking level low",
               variables=[("role", "job role"), ("round", "round type"),
                          ("transcript_json", "all questions, answers, P2 outputs and follow-ups as JSON")],
               examples="0 (fixed heading structure given in the rules)",
               output="Markdown with 6 fixed headings, under 450 words", sample="T9"),
}

ITER_TEXT = {
    "v1": ("Milestone 1 baseline: one-line role + \"Evaluate the answer. Give a score from 1 to 5, a short reason, and one follow-up question.\" No system prompt, default temperature.",
           "Starting point from Milestone 1."),
    "v2": ("Added a system role (placement interviewer), a 4-criterion rubric (correctness, depth, structure, clarity) and a JSON output format written in the prompt.",
           "v1 gave one vague number in free text, with no per-criterion breakdown, that could not be parsed as JSON (0/11)."),
    "v3": ("Added score anchors for 1/3/5 per criterion, 2 graded few-shot examples, the rule to quote the student's words as evidence, temperature 0.2 and JSON mode (response_mime_type).",
           "v2 had no shared meaning for each score and no evidence; mentor feedback asked for quoted evidence."),
    "v4": ("Final: content-over-style rule (Hinglish/grammar must not lower scores), verbatim-quote rule, answer wrapped in <student_answer> tags and treated as data (injection guard), invalid-answer rule (valid_answer=false), reference key points from P1, response schema; code checks every quote and computes the overall score.",
           "v3 still let wording change scores, could be pushed by instructions inside the answer and had no way to reject 'idk'; mentor asked for a no-fabrication rule."),
}


def esc(s) -> str:
    return html.escape(str(s))


def load(name):
    return json.loads((TD / name).read_text(encoding="utf-8"))


def prompt_text(rel):
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def split_prompt(rel):
    t = prompt_text(rel)
    if t.startswith("---"):
        t = t.split("---", 2)[2]
    sys_p = t.split("### SYSTEM", 1)[1].split("### USER", 1)[0].strip()
    usr = t.split("### USER", 1)[1].strip()
    return sys_p, usr


def iter_result(s: dict) -> str:
    def fmt(xs):
        return ", ".join("-" if x is None else (f"{x:g}" if isinstance(x, (int, float)) else str(x)) for x in xs)
    parts = [f"JSON valid {s['json_valid']}/{s['runs']} runs"]
    parts.append(f"partial answer x{len(s['partial_scores'])}: {fmt(s['partial_scores'])}" + (f" (range {s['partial_range']:g})" if s["partial_range"] is not None else ""))
    if s["style_gap"] is not None:
        parts.append(f"polished {fmt(s['polished_scores'])} vs casual {fmt(s['casual_scores'])} (gap {s['style_gap']:+g})")
    else:
        parts.append("polished vs casual: not measurable")
    parts.append(f"'idk' scored {fmt(s['idk_score'])}" + (" (flagged invalid)" if all(s["idk_flagged_invalid"]) and s["idk_flagged_invalid"] else ""))
    parts.append(f"injection answer scored {fmt(s['injection_score'])}" + (" (flagged)" if s["injection_flagged"] and all(s["injection_flagged"]) else ""))
    if s["quotes_total"]:
        parts.append(f"quotes verbatim {s['quotes_verbatim']}/{s['quotes_total']}")
    else:
        parts.append("no evidence quotes")
    return "; ".join(parts)


CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
body { font-family: "Segoe UI", Arial, sans-serif; color:#1F2937; font-size: 10.2pt; line-height: 1.42; }
h1 { font-size: 19pt; color:#312E81; margin: 0 0 6px; }
h2 { font-size: 15pt; color:#312E81; border-bottom: 2px solid #C7D2FE; padding-bottom: 4px; margin: 0 0 10px; }
h3 { font-size: 12pt; color:#3730A3; margin: 14px 0 6px; }
h4 { font-size: 10.5pt; margin: 10px 0 4px; }
.section { page-break-before: always; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 9pt; }
th { background:#EEF2FF; text-align:left; }
th, td { border: 1px solid #D1D5DB; padding: 4px 6px; vertical-align: top; }
pre { white-space: pre-wrap; word-wrap: break-word; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:6px;
      padding: 7px 9px; font-family: Consolas, "Courier New", monospace; font-size: 8.1pt; line-height: 1.32; margin: 4px 0 8px; }
.kv td:first-child { width: 24%; background:#F9FAFB; font-weight:600; }
.fig { text-align:center; margin: 8px 0 12px; page-break-inside: avoid; }
.fig img { max-width: 100%; border:1px solid #E5E7EB; border-radius:6px; }
.fig .cap { font-size: 8.8pt; color:#4B5563; margin-top: 3px; }
.pass { color:#047857; font-weight:700; } .fail { color:#B91C1C; font-weight:700; }
.cover { text-align:left; }
.cover .band { background: linear-gradient(120deg,#4F46E5,#7C3AED); color:#fff; padding: 22px 24px; border-radius: 12px; margin-bottom: 18px; }
.cover .band h1 { color:#fff; font-size: 24pt; margin:0; }
.cover .band p { margin: 6px 0 0; opacity:.95; font-size: 11.5pt; }
.small { font-size: 8.8pt; color:#4B5563; }
a { color:#3730A3; word-break: break-all; }
.note { background:#FFFBEB; border:1px solid #FDE68A; padding:6px 9px; border-radius:6px; font-size: 9pt; }
ul { margin: 4px 0 8px 18px; padding:0; } li { margin: 2px 0; }
"""


def build_html(ctx: dict, report_only=False) -> str:
    tests = ctx["tests"]
    summ = ctx["summ"]
    n_tests = len(tests)
    n_pass = sum(r["result"] == "Pass" for r in tests)
    n_edge = sum(r["type"] == "Edge" for r in tests)
    n_inv = sum(r["type"] == "Invalid" for r in tests)
    versions = ["v1", "v2", "v3", "v4"]
    open_key = [k for k in summ if k.startswith("v4_on_")][0]
    model = summ["_info"]["model"]
    reel = ctx["reel_url"]
    reel_txt = f'<a href="{esc(reel)}">{esc(reel)}</a> ({ctx["reel_seconds"]} s)' if reel else "to be added (recorded by the team)"

    tech_report = technical_report(ctx)
    if report_only:
        return f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{tech_report}</body></html>"

    h = [f"<html><head><meta charset='utf-8'><title>M2_{TEAM_ID}_MockMate</title><style>{CSS}</style></head><body>"]

    # ---------------- 1 cover ----------------
    rows = "".join(f"<tr><td>{esc(m[0])}</td><td>{m[1]}</td><td>{esc(m[2])}</td></tr>" for m in MEMBERS)
    h.append(f"""
<div class="cover">
<h2>1. Cover page</h2>
<div class="band"><h1>{esc(TITLE)}</h1><p>{esc(COURSE)}</p></div>
<table class="kv">
<tr><td>Team ID</td><td>{TEAM_ID}</td></tr>
<tr><td>Team name</td><td>{TEAM}</td></tr>
<tr><td>Project title</td><td>{esc(TITLE)}</td></tr>
<tr><td>Problem</td><td>C10 - Mock interview question and feedback tool (Problem Pool, Part C)</td></tr>
<tr><td>Batch</td><td>{BATCH}</td></tr>
<tr><td>Faculty</td><td>{FACULTY}</td></tr>
<tr><td>Prototype link</td><td><a href="{PROTOTYPE}">{PROTOTYPE}</a> (opens without login)</td></tr>
<tr><td>Repository link</td><td><a href="{REPO}">{REPO}</a> (public)</td></tr>
<tr><td>Reel link</td><td>{reel_txt}</td></tr>
<tr><td>Counts</td><td>{len(PROMPT_INFO)} final prompts · {n_tests} test inputs · {len(versions)} prompt versions</td></tr>
<tr><td>Submitted</td><td>22 November 2026</td></tr>
</table>
<h3>Team members</h3>
<table><tr><th>Name</th><th>Enrollment no.</th><th>Role</th></tr>{rows}</table>
</div>""")

    # ---------------- 2 design ----------------
    s4 = summ["v4"]
    s1 = summ["v1"]
    h.append(f"""
<div class="section">
<h2>2. Prompt and solution design</h2>
<h3>(a) Design summary</h3>
<p><b>Problem and users.</b> Pre-final and final-year B.Tech students practise placement interviews alone or with friends. The feedback they get is vague
("good answer", "speak more"), and mentors cannot review every student. They do not learn which part of an answer is weak or how to fix it.</p>
<p><b>Input and output.</b> The student gives a job role, a round type (Technical / HR / Behavioural / Managerial), a difficulty and then types an answer
to each question. MockMate returns, for every answer, four rubric scores (1-5) with the student's own words quoted as evidence, strengths, tips,
and one follow-up question on the weakest area; at the end it writes a feedback report with a score table and a 7-day practice plan.</p>
<p><b>How many prompts and why.</b> Four prompts in a chain (P1 Planner → P2 Evaluator → P3 Follow-up → P4 Report). Each step has one job, its
own output format and its own temperature: question writing needs some variety (0.7), scoring must be consistent (0.2), the report must stick to
the transcript (0.4). Splitting also lets us test each step on its own (Section 4). Three checks run in code instead of in a prompt, because code
is more reliable for them: empty answers are blocked before the API call, every evidence quote is matched against the answer and removed if it is
not there, and the overall score and weakest area are computed from the four scores.</p>
<p><b>Tool and model.</b> Google Gemini API through the <code>google-genai</code> Python SDK, model <b>{model}</b> (free tier: 500 requests/day; the
larger Flash models allow only 20/day, too few for a public demo), with <i>gemini-3.1-flash-lite</i> as automatic fallback. Gemini supports
system instructions and JSON response schemas, so P1-P3 always return valid JSON. The app is a Streamlit web app, so the evaluator can try it
in a browser with no login. For a cross-model check we also ran the final evaluator on the open-weights <b>Gemma 4 31B</b>.</p>
<p><b>What changed since Milestone 1.</b> (1) The baseline evaluator (v1) was improved through three versions to v4 with a rubric, score anchors,
two few-shot examples, quoted evidence, JSON schema and guard rules (Section 3). (2) Mentor feedback was built in: a polished-vs-casual test
(T10), a no-fabrication rule enforced in code, and an injection guard. (3) Model: Gemini 2.5 Flash, planned in M1, is no longer offered to new
API keys, so we moved to Gemini 3.5 Flash-Lite. (4) The planned open-source comparison was done with Gemma 4 31B instead of Llama/Mistral (same
API, no extra key). (5) The 30-answer agreement study with a senior's scores is not done yet and moves to Milestone 3.</p>

<h3 style="page-break-before: always">(b) Diagrams</h3>
<div class="fig"><img src="{(DOCS/'diagrams'/'workflow.png').as_uri()}"><div class="cap">Figure 1 - Prompt workflow</div></div>
<div class="fig"><img src="{(DOCS/'diagrams'/'decomposition.png').as_uri()}"><div class="cap">Figure 2 - Task decomposition</div></div>
<div class="fig"><img src="{(DOCS/'diagrams'/'ioflow.png').as_uri()}"><div class="cap">Figure 3 - Input-output flow</div></div>
<div class="fig"><img src="{(DOCS/'diagrams'/'architecture.png').as_uri()}"><div class="cap">Figure 4 - System architecture (app)</div></div>
<p class="small">No agents or retrieval (RAG) are used, so no agent-loop or RAG diagram is needed.</p>

<h3>(c) Prompt sheets</h3>
<p class="small">All prompts are pasted as text. The same files are in <code>prompts/final/</code> and are loaded by the app at runtime.</p>
""")
    for pid, info in PROMPT_INFO.items():
        sys_p, usr = split_prompt(info["file"])
        var_rows = "".join(f"<tr><td><code>{{{v}}}</code></td><td>{esc(d)}</td></tr>" for v, d in info["variables"])
        h.append(f"""
<div style="page-break-before: always"></div>
<h3>Prompt sheet {pid} - {esc(info['name'])}</h3>
<table class="kv">
<tr><td>Prompt ID and name</td><td>{pid} - {esc(info['name'])} (<code>{info['file']}</code>)</td></tr>
<tr><td>Step in the workflow</td><td>{esc(info['step'])}</td></tr>
<tr><td>Purpose</td><td>{esc(info['purpose'])}</td></tr>
<tr><td>Tool and model</td><td>Google Gemini API (google-genai SDK), {model}</td></tr>
<tr><td>Settings</td><td>{esc(info['settings'])}</td></tr>
<tr><td>Number of examples</td><td>{esc(info['examples'])}</td></tr>
<tr><td>Output format</td><td>{esc(info['output'])}</td></tr>
</table>
<h4>Full system prompt</h4><pre>{esc(sys_p)}</pre>
<h4>Full user prompt template</h4><pre>{esc(usr)}</pre>
<h4>What each variable holds</h4><table><tr><th>Variable</th><th>Holds</th></tr>{var_rows}</table>
<h4>Sample run (real input and actual output, test {info['sample']})</h4>
{sample_run(pid, info['sample'])}
""")
    h.append("</div>")

    # ---------------- 3 implementation ----------------
    mods = ctx["modules"]
    mod_rows = "".join(f"<tr><td>{esc(m[0])}</td><td>{esc(m[1])}</td><td><b>{m[2]}</b></td><td>{esc(m[3])}</td></tr>" for m in mods)
    it_rows = ""
    for v in versions:
        what, why = ITER_TEXT[v]
        it_rows += f"<tr><td><b>{v}</b></td><td>{esc(what)}</td><td>{esc(why)}</td><td>{esc(iter_result(summ[v]))}</td></tr>"
    so = summ[open_key]
    h.append(f"""
<div class="section">
<h2>3. Implementation</h2>
<h3>What is built</h3>
<ul>
<li>A deployed <b>Streamlit web app</b> (<a href="{PROTOTYPE}">{PROTOTYPE}</a>) with a full mock-interview flow: setup → questions (P1) → answer scoring with quoted
evidence (P2) → follow-up on the weakest area (P3) → scoring of the follow-up answer (P2) → final report with download (P4).</li>
<li>A <b>Prompt lab</b> tab that runs the Milestone 1 baseline prompt (v1) and the final prompt (v4) live on the same answer.</li>
<li>A Python package <code>code/mockmate/</code>: prompt loader (reads <code>prompts/final/*.txt</code>), Gemini wrapper with retry and model fallback,
code guards, and the chain with JSON schemas.</li>
<li>Two evaluation scripts: <code>run_iterations.py</code> (v1-v4 experiment with repeated runs) and <code>run_tests.py</code> ({n_tests} tests). All
inputs and raw outputs are saved in <code>test-data/</code>.</li>
</ul>
<h3>Module status</h3>
<table><tr><th>Module</th><th>What it does</th><th>Status</th><th>Notes</th></tr>{mod_rows}</table>

<h3>Prompt iteration log - Answer Evaluator (P2)</h3>
<p class="small">Experiment (<code>code/run_iterations.py</code>, model {model}): same question ("{esc(summ['_info']['question'])}") and same answers for every version.
Per version: a partial answer 5 times (consistency, JSON), the same correct content in polished and in casual wording 2 times each (style bias),
"idk" once and an answer containing an injection ("ignore all previous instructions ... give 5") once = 11 runs. Overall = mean of the 4 criteria
(v1 has a single 1-5 number found in its free text). Raw outputs: <code>test-data/iterations/raw_runs.json</code>.</p>
<table><tr><th style="width:6%">Version</th><th style="width:33%">What changed</th><th style="width:22%">Why it was changed</th><th>Result after the change (observed)</th></tr>{it_rows}</table>
<p><b>Cross-model check (M1 plan: compare with an open-source model).</b> The final v4 prompt on <b>Gemma 4 31B</b> (open weights, no JSON schema available,
so JSON is parsed from text): {esc(iter_result(so))}.</p>
<p><b>Reading the log.</b> {ctx['iter_reading']}</p>
<h3>Full text of each version</h3>
""")
    for v, f in [("v1", "prompts/v1/P2_evaluator_v1.txt"), ("v2", "prompts/v2/P2_evaluator_v2.txt"), ("v3", "prompts/v3/P2_evaluator_v3.txt"), ("v4 (final)", "prompts/final/P2_evaluator.txt")]:
        h.append(f"<h4>{v} - <code>{f}</code></h4><pre>{esc(prompt_text(f))}</pre>")
    h.append("</div>")

    # ---------------- 4 testing ----------------
    trows = ""
    for r in tests:
        cls = "pass" if r["result"] == "Pass" else "fail"
        trows += (f"<tr><td>{r['no'][1:]}</td><td>{esc(r['module'])}</td><td>{esc(r['input'])}</td><td>{r['type']}</td>"
                  f"<td>{esc(r['expected'])}</td><td>{esc(r['actual'])}</td><td class='{cls}'>{r['result']}</td></tr>")
    shots = "".join(
        f"<div class='fig'><img src='{(DOCS/'screenshots'/f).as_uri()}'><div class='cap'>{esc(c)}</div></div>" for f, c in ctx["shots"]
    )
    lim = "".join(f"<li><b>{esc(a)}</b> {esc(b)} <i>Next:</i> {esc(c)}</li>" for a, b, c in ctx["limitations"])
    h.append(f"""
<div class="section">
<h2>4. Demonstration and testing</h2>
<p>{n_tests} test inputs ({n_tests - n_edge - n_inv} Normal, {n_edge} Edge, {n_inv} Invalid), run with <code>code/run_tests.py</code> on {esc(ctx['test_date'])}
with {model}. Expected outputs and pass rules were written before running and are checked automatically in code. Result: <b>{n_pass}/{n_tests} passed</b>.
Inputs: <code>test-data/test_cases.json</code>; raw outputs: <code>test-data/outputs/T*.json</code>.</p>
<table><tr><th>Test no.</th><th>Module</th><th>Input (short)</th><th>Type</th><th>Expected output</th><th>Actual output (short)</th><th>Pass / Fail</th></tr>{trows}</table>
<p>{ctx['test_reading']}</p>
<h3>Screenshots of real runs</h3>
{shots}
<h3>Known limitations and what we will try next</h3>
<ul>{lim}</ul>
</div>""")

    # ---------------- 5 repository ----------------
    h.append(f"""
<div class="section">
<h2>5. Repository</h2>
<p>Public repository: <a href="{REPO}">{REPO}</a></p>
<div class="fig"><img src="{(DOCS/'screenshots'/'repo.png').as_uri()}"><div class="cap">Repository home page (public, no login needed)</div></div>
<h3>What changed since Milestone 1</h3>
<ul>
<li>Added the repository in the required layout: <code>prompts/</code> (v1, v2, v3, final), <code>code/</code>, <code>test-data/</code>, <code>docs/</code>, <code>README.md</code>, <code>CHANGELOG.md</code>.</li>
<li>Added the four final prompts and three older versions of the Evaluator prompt as text files; the app loads the final files at runtime.</li>
<li>Added the Streamlit app, the <code>mockmate</code> package (chain, guards, Gemini wrapper) and the two evaluation scripts.</li>
<li>Added all test inputs, raw model outputs and experiment results in <code>test-data/</code>, and the diagrams and this PDF in <code>docs/</code>.</li>
<li>Progress is recorded in dated commits and in <code>CHANGELOG.md</code>. The API key is kept in Streamlit Secrets and a git-ignored <code>.env</code>; no key is in the repo.</li>
</ul>
</div>""")

    # ---------------- 6 supporting document ----------------
    h.append(f"""<div class="section"><h2>6. Supporting document - Technical report</h2>
<p class="small">Same document as uploaded separately (MockMate_TechnicalReport.pdf).</p>{tech_report}</div>""")

    # ---------------- 7 contribution ----------------
    crow = "".join(f"<tr><td>{esc(m[0])}</td><td>{m[1]}</td><td>{esc(m[2])}</td><td>{esc(m[3])}</td><td>{esc(m[4])}</td><td>{m[5]}</td></tr>" for m in MEMBERS)
    h.append(f"""
<div class="section">
<h2>7. Team contribution</h2>
<table><tr><th>Member name</th><th>Enrollment no.</th><th>Role</th><th>Tasks done in Milestone 2</th><th>Evidence</th><th>Contribution (%)</th></tr>{crow}
<tr><td colspan="5" style="text-align:right"><b>Total</b></td><td><b>{sum(m[5] for m in MEMBERS)}</b></td></tr></table>
<p>All four members have reviewed and agreed to this contribution table. Each member can explain the part they claim.</p>
<p class="small">AI-assistance note: Gemini is the model inside the product. An AI coding assistant (Claude) generated most of the code, first drafts of the
prompts and this documentation under the team's direction; commits list it as co-author. The team chose the problem, rubric and tests, reviewed
and ran everything, and is responsible for the submitted work. All test data is made up; no real personal data was used.</p>
</div></body></html>""")
    return "".join(h)


def sample_run(pid: str, tid: str) -> str:
    raw = json.loads((TD / "outputs" / f"{tid}.json").read_text(encoding="utf-8"))
    cases = {c["no"]: c for c in load("test_cases.json") if "no" in c}
    inp = cases[tid]["input"]
    if pid == "P1":
        out = {k: v for k, v in raw.items() if not k.startswith("_")}
        out["questions"] = out.get("questions", [])[:3]
        return f"<p><b>Input:</b> {esc(inp)}</p><p><b>Actual output</b> (first 3 of {len(raw.get('questions', []))} questions):</p><pre>{esc(json.dumps(out, indent=1, ensure_ascii=False))}</pre>"
    if pid == "P2":
        a = load("test_cases.json")[-1]["answers"]["proc_partial"]
        out = {k: v for k, v in raw.items() if not k.startswith("_")}
        return (f"<p><b>Input:</b> role = Software Engineer Intern, round = Technical, question = \"What is the difference between a process and a thread?\", "
                f"key_points = not given, answer = \"{esc(a)}\"</p><p><b>Actual output</b> (after the code guards):</p><pre>{esc(json.dumps(out, indent=1, ensure_ascii=False))}</pre>")
    if pid == "P3":
        fu = {k: v for k, v in raw["follow_up"].items() if not k.startswith("_")}
        ev = raw["evaluation"]
        return (f"<p><b>Input:</b> the T7 question and answer, valid_answer = {str(ev.get('valid_answer')).lower()}, weakest_area = {ev.get('weakest_area')}, "
                f"weak_comment from P2.</p><p><b>Actual output:</b></p><pre>{esc(json.dumps(fu, indent=1, ensure_ascii=False))}</pre>")
    md = raw["report"]["report_md"]
    return f"<p><b>Input:</b> {esc(inp)} (transcript JSON with both answers and their P2 outputs).</p><p><b>Actual output</b> (Markdown):</p><pre>{esc(md)}</pre>"


def technical_report(ctx) -> str:
    tests = ctx["tests"]
    n_pass = sum(r["result"] == "Pass" for r in tests)
    summ = ctx["summ"]
    s1, s4 = summ["v1"], summ["v4"]
    fails = [r for r in tests if r["result"] == "Fail"]
    fail_txt = "; ".join(f"T{r['no'][1:]} ({r['input'][:45]}...)" if len(r['input']) > 45 else f"T{r['no'][1:]} ({r['input']})" for r in fails) or "none"
    lim = "".join(f"<li><b>{esc(a)}</b> {esc(b)}</li>" for a, b, _ in ctx["limitations"])
    return f"""
<h1 style="font-size:16pt">MockMate - Technical Report</h1>
<p class="small">Team {TEAM_ID} · {TEAM} · {COURSE} · Problem C10 · 22 November 2026</p>
<h3>TR-1 Purpose</h3>
<p>MockMate is a web app that runs a mock placement interview and gives structured, evidence-backed feedback on each typed answer, so a student
knows exactly which part of an answer is weak and how to practise. Prototype: {PROTOTYPE} · Code: {REPO}</p>
<h3>TR-2 Architecture</h3>
<p>A Streamlit front end (<code>code/app.py</code>) calls a small Python package (<code>code/mockmate/</code>). <code>prompts.py</code> loads the four prompt
files from <code>prompts/final/</code>; <code>chain.py</code> runs them in order with Pydantic response schemas; <code>guards.py</code> holds checks done in
code; <code>llm.py</code> wraps the Gemini API with retry on rate limits and a fallback model when the daily quota is used up. The API key is stored in
Streamlit Secrets. Pushing to GitHub redeploys the app on Streamlit Community Cloud.</p>
<h3>TR-3 Tools and models</h3>
<p>Google Gemini API (<code>google-genai</code> SDK), main model <b>{summ['_info']['model']}</b> (free tier, 500 requests/day), fallback gemini-3.1-flash-lite,
cross-model check on the open-weights Gemma 4 31B. Streamlit 1.67, Python 3.13, Playwright for screenshots and PDFs.</p>
<h3>TR-4 Prompt design</h3>
<table>
<tr><th>Prompt</th><th>Technique</th><th>Settings</th></tr>
<tr><td>P1 Planner</td><td>Role prompting, rules per round type, key points as a reference for scoring, refusal for fake roles</td><td>temp 0.7, JSON schema</td></tr>
<tr><td>P2 Evaluator</td><td>Rubric with 1/3/5 anchors, 2 few-shot graded examples, verbatim-quote rule, content-over-style rule, answer delimited and treated as data, invalid-answer rule</td><td>temp 0.2, JSON schema</td></tr>
<tr><td>P3 Follow-up</td><td>Targets the weakest criterion (computed in code), one question, no hints, easier re-ask after invalid answers</td><td>temp 0.5, JSON schema</td></tr>
<tr><td>P4 Report</td><td>Grounded only in the transcript JSON, fixed 6-heading structure, word limit</td><td>temp 0.4, Markdown</td></tr>
</table>
<p>Code guards: empty answer blocked before any API call; every quote checked against the answer and removed if not found; overall = mean of the 4 scores (0 if invalid); weakest area = lowest score.</p>
<h3>TR-5 Test results</h3>
<p><b>Prompt iteration (Evaluator, 11 runs per version).</b> v1 (baseline): {esc(iter_result(s1))}. v4 (final): {esc(iter_result(s4))}.</p>
<p><b>Test suite.</b> {n_pass}/{len(tests)} tests passed (Normal, Edge and Invalid inputs across all four prompts). Failed: {esc(fail_txt)}. Full table in the Milestone 2 PDF, Section 4.</p>
<h3>TR-6 Limitations</h3>
<ul>{lim}</ul>
<p>Scores are practice feedback from a language model, not an official assessment; agreement with human (senior) scores on 30 answers will be measured in Milestone 3.
Responsible use: all test answers are made up by the team, the app asks users not to type personal data, and no data is stored after the session.</p>
"""


def build(args):
    tests = load("test_results.json")
    summ = load("iterations/summary.json")
    ctx = {
        "tests": tests["rows"],
        "test_date": tests["date"],
        "summ": summ,
        "reel_url": args.reel_url,
        "reel_seconds": args.reel_seconds,
    }
    ctx.update(json.loads((Path(__file__).parent / "pdf_text.json").read_text(encoding="utf-8")))
    m2 = DOCS / f"M2_{TEAM_ID}_MockMate.pdf"
    tr = DOCS / f"{TEAM}_TechnicalReport.pdf"
    with sync_playwright() as p:
        b = launch(p)
        for path, report_only in [(m2, False), (tr, True)]:
            pg = b.new_page()
            hp = path.with_suffix(".html")
            hp.write_text(build_html(ctx, report_only), encoding="utf-8")
            pg.goto(hp.as_uri())
            pg.wait_for_timeout(800)
            pg.pdf(path=str(path), format="A4", print_background=True,
                   margin={"top": "14mm", "bottom": "14mm", "left": "13mm", "right": "13mm"},
                   display_header_footer=True, header_template="<span></span>",
                   footer_template=f"<div style='font-size:7pt;color:#6B7280;width:100%;text-align:center'>{TEAM_ID} · {TEAM} · page <span class='pageNumber'></span> of <span class='totalPages'></span></div>")
            hp.unlink()
            print("wrote", path.name, round(path.stat().st_size / 1024), "KB")
        b.close()
    for f in (m2, tr):
        (SUB / f.name).write_bytes(f.read_bytes())
    write_cheatsheet(ctx)


def write_cheatsheet(ctx):
    tests = ctx["tests"]
    working = [m[0] for m in ctx["modules"] if m[2] == "Working"]
    all_working = all(m[2] == "Working" for m in ctx["modules"])
    lines = [
        "# Milestone 2 form - answers (generated from the same data as the PDF)",
        "",
        f"Q1 Team ID: {TEAM_ID}",
        f"Q2 Team name: {TEAM}",
        f"Q3 Project title: {TITLE}",
        "Q4 Team leader name: Yug Chaturvedi",
        "Q5 Team leader enrollment no.: S24CSEU1260",
        "Q6 Group (batch): B13-24",
        "Q7 Enrollment numbers (one per line):",
        *[f"    {m[1]}" for m in MEMBERS],
        "Q8 Project type (max 2): Custom web or mobile app; Prompt chain / workflow  (pick the closest 2 options shown in the form)",
        f"Q9 Main AI tool and model: Gemini 3.5 Flash-Lite via Google Gemini API (google-genai SDK) in a Streamlit app",
        f"Q10 Number of prompts: {len(PROMPT_INFO)}",
        f"Q11 Prototype link: {PROTOTYPE}",
        f"Q12 Repository link: {REPO}",
        f"Q13 Reel link: {ctx['reel_url'] or '<<add your reel link>>'}",
        f"Q14 Reel length (seconds): {ctx['reel_seconds'] or '<<exact seconds, 90-150>>'}",
        "Q15 Supporting document type: Technical report",
        f"Q16 Upload: submission/{TEAM}_TechnicalReport.pdf",
        f"Q17 Number of test inputs: {len(tests)}",
        "Q18 Number of prompt versions: 4",
        f"Q19 Prototype status: {'All modules working' if all_working else 'Some modules working'}",
        "Q20 Names of working modules (one per line):",
        *[f"    {w}" for w in working],
        f"Q21 Upload: submission/M2_{TEAM_ID}_MockMate.pdf",
        "Q22 Main task of each member:",
        *[f"    {m[1]} - {m[0].replace(' (Team leader)', '')} - {m[2]}: {m[3]}" for m in MEMBERS],
        "Q23 Anything the evaluator should know: No login needed. Open the prototype link, pick a role in the left sidebar and press "
        "'Start new interview'. The 'Prompt lab' tab runs the Milestone 1 baseline prompt and the final prompt side by side. "
        "Free-tier API: if it is slow, wait a few seconds and submit again. If the page says the app has gone to sleep, click the wake-up button and wait about 30 seconds.",
        "Q24 Confirmation: tick only after all four members have agreed to the contribution table (Section 7).",
    ]
    (SUB / "FORM_ANSWERS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote submission/FORM_ANSWERS.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reel-url", default="")
    ap.add_argument("--reel-seconds", default="")
    build(ap.parse_args())
