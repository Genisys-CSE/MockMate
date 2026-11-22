# Changelog

All notable changes since Milestone 1. Dates are in IST.

## 2026-11-22 - Milestone 2 build
- Added the repository with the required layout (`prompts/`, `code/`, `test-data/`, `docs/`).
- Added prompt versions of the Answer Evaluator: `v1` (Milestone 1 baseline), `v2` (rubric + JSON format), `v3` (few-shot score anchors, quoted evidence, temperature 0.2, JSON mode), `v4` final (content-over-style rule, verbatim-quote rule, injection guard, invalid-answer handling, response schema).
- Added the final 4-prompt chain: `P1_planner`, `P2_evaluator`, `P3_followup`, `P4_report` in `prompts/final/`.
- Added `code/mockmate/` (prompt loader, Gemini wrapper with retry, guards, chain) - prompts are loaded from the `.txt` files at runtime.
- Added code guards: empty answers blocked before the API call; every evidence quote is checked against the student's answer and removed if not found; overall score and weakest area computed in code.
- Added the Streamlit app `code/app.py` (mock interview flow + "Prompt lab" that runs v1 and v4 side by side).
- Added `code/run_iterations.py` (v1-v4 experiment, repeated runs) and `code/run_tests.py` (18-case test suite); saved inputs and raw outputs in `test-data/`.
- Switched model from Gemini 2.5 Flash (planned in M1, no longer offered to new API keys) to Gemini 3.5 Flash-Lite (the free tier gives Flash models only 20 requests/day, Flash-Lite 500/day; 3.1 Flash-Lite is the automatic fallback); added a cross-model check of the final evaluator on the open-weights Gemma 4 31B.
- Added diagrams, the Milestone 2 PDF and the technical report in `docs/`.

## 2026-10-09 - Milestone 1
- Submitted the Milestone 1 proposal: problem C10 (mock interview question and feedback tool), 4-prompt chain plan, baseline prompt and sample output, mentor feedback (score agreement with a senior, polished-vs-casual test, no-fabrication rule).
