# MockMate - AI mock-interview coach for placement prep

**Team PE-B13-42 · MockMate** · Bennett University · SCSE4041 Prompt Engineering mini-project · Problem C10 (Mock interview question and feedback tool)

🔗 **Prototype:** https://mockmate-pe-b13-42.streamlit.app (no login needed)

## What it does
Placement-year students practise interviews alone or with friends and get vague feedback. MockMate runs a mock interview with a **4-prompt chain** on Google Gemini:

| Step | Prompt (file) | Input → Output |
|---|---|---|
| 1 | **P1 Question Planner** (`prompts/final/P1_planner.txt`) | job role, round type, difficulty → questions + key points of a strong answer (JSON) |
| 2 | **P2 Answer Evaluator** (`prompts/final/P2_evaluator.txt`) | question + student answer → 1-5 scores for correctness, depth, structure, clarity, with **verbatim quotes** as evidence (JSON) |
| 3 | **P3 Follow-up Generator** (`prompts/final/P3_followup.txt`) | answer + weakest area → one probing follow-up question (JSON). The follow-up answer is scored again by P2 |
| 4 | **P4 Report Writer** (`prompts/final/P4_report.txt`) | full transcript + scores → feedback report with a 7-day practice plan (Markdown) |

Checks done in code (`code/mockmate/guards.py`): empty answers are blocked before any API call; every evidence quote is matched against the student's answer and removed if it is not there (no-fabrication rule); the overall score and weakest area are computed in code.

The app also has a **Prompt lab** tab that runs the Milestone 1 baseline prompt (v1) and the final prompt (v4) on the same answer side by side.

## Repository layout
```
README.md          this file
CHANGELOG.md       dated changes since Milestone 1
prompts/
  v1/ v2/ v3/      older versions of the Evaluator prompt
  final/           P1-P4 final prompts (loaded by the app at runtime)
code/
  app.py           Streamlit app
  mockmate/        prompt loader, Gemini wrapper, guards, chain
  run_iterations.py  v1-v4 prompt experiment (repeated runs)
  run_tests.py     18-case test suite
  tools/           scripts that build the diagrams and PDFs
test-data/         test inputs, raw model outputs, experiment results
docs/              diagrams, screenshots, Milestone 2 PDF, technical report
```

## How to run it yourself
```bash
pip install -r requirements.txt
# put a free key from https://aistudio.google.com in a file called .env:
#   GEMINI_API_KEY=your_key
streamlit run code/app.py
py code/run_tests.py        # re-run the test suite
py code/run_iterations.py   # re-run the prompt experiment
```
The `.env` file is git-ignored. On Streamlit Cloud the key is stored in the app's Secrets, never in the repo.

## Models
- Main: **Gemini 3.5 Flash-Lite** (Google Gemini API, free tier), temperature per prompt (P1 0.7, P2 0.2, P3 0.5, P4 0.4), JSON response schemas for P1-P3.
- Cross-model check: the final evaluator prompt was also run on the open-weights **Gemma 4 31B** (`test-data/iterations/summary.json`).

## Team
| Member | Enrollment no. | Role |
|---|---|---|
| Yug Chaturvedi (leader) | S24CSEU1260 | Prompt design (P1-P4, Evaluator v1-v4) |
| Aditi Tripathi | S24CSEU1268 | Testing and evaluation (test suite, iteration experiment) |
| Shivraj Singh Bhati | S24CSEU0511 | App development and deployment (Streamlit, Gemini integration, guards) |
| Aryan Singh | S24CSEU1256 | Documentation and diagrams (diagrams, M2 PDF, technical report, README) |

## Responsible use
All questions and answers used in testing are made up by the team. Do not type real personal data into the app. Scores are practice feedback from a language model, not an official assessment; a mentor should review important decisions. AI tools (Gemini for the product, an AI coding assistant for parts of the code and docs) were used during development; the team reviewed and is responsible for all submitted work.
