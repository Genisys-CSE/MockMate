"""Checks that run in code, before and after the LLM calls.

- pre_check_answer: blocks empty answers before any API call.
- verify_quotes: the no-fabrication rule. Every evidence quote must appear in
  the student's answer; quotes that do not are removed and counted.
- finalise_scores: clamps scores to 1-5, computes the overall score and the
  weakest area in code instead of trusting the model's arithmetic.
"""
from __future__ import annotations

import re
import unicodedata

CRITERIA = ["correctness", "depth", "structure", "clarity"]
MAX_ANSWER_CHARS = 4000


def pre_check_answer(answer: str) -> str | None:
    """Return an error message if the answer should not be sent to the model."""
    if answer is None or not answer.strip():
        return "Your answer is empty. Type your answer (even a short attempt) and submit again."
    return None


def clip_answer(answer: str) -> str:
    return answer.strip()[:MAX_ANSWER_CHARS]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[^\w\s']", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def quote_in_answer(quote: str, answer: str) -> bool:
    q = _norm(quote).strip("'\" ")
    return bool(q) and q in _norm(answer)


def verify_quotes(evaluation: dict, answer: str) -> dict:
    kept, removed = [], []
    for ev in evaluation.get("evidence", []) or []:
        if quote_in_answer(ev.get("quote", ""), answer):
            ev["verified"] = True
            kept.append(ev)
        else:
            removed.append(ev)
    evaluation["evidence"] = kept
    evaluation["removed_quotes"] = removed
    return evaluation


def finalise_scores(evaluation: dict) -> dict:
    scores = evaluation.get("scores") or {}
    for c in CRITERIA:
        try:
            scores[c] = max(1, min(5, int(round(float(scores.get(c, 1))))))
        except (TypeError, ValueError):
            scores[c] = 1
    evaluation["scores"] = scores
    valid = evaluation.get("valid_answer", True)
    evaluation["overall"] = round(sum(scores.values()) / len(CRITERIA), 2) if valid else 0.0
    if evaluation.get("weakest_area") not in CRITERIA or (
        scores[evaluation["weakest_area"]] != min(scores.values())
    ):
        evaluation["weakest_area"] = min(CRITERIA, key=lambda c: scores[c])
    return evaluation
