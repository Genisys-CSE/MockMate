"""The MockMate 4-prompt chain.

P1 Planner  -> P2 Evaluator -> P3 Follow-up -> (P2 again on the follow-up answer) -> P4 Report
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel

from . import guards, llm
from .prompts import evaluator, final


# ---------- output schemas (sent to Gemini as response_schema) ----------
class Question(BaseModel):
    question: str
    topic: str
    difficulty: str
    key_points: list[str]


class Plan(BaseModel):
    role_ok: bool
    questions: list[Question]


class Scores(BaseModel):
    correctness: int
    depth: int
    structure: int
    clarity: int


class Evidence(BaseModel):
    criterion: str
    quote: str
    comment: str


class Evaluation(BaseModel):
    valid_answer: bool
    injection_detected: bool
    scores: Scores
    evidence: list[Evidence]
    weakest_area: str
    strengths: list[str]
    improvements: list[str]


class FollowUp(BaseModel):
    follow_up: str
    targets: str
    why: str


# ---------- P1 ----------
def plan_questions(role: str, round_type: str, difficulty: str = "Medium", n_questions: int = 5) -> dict:
    p = final("P1")
    system, user = p.render(role=role, round=round_type, difficulty=difficulty, n_questions=n_questions)
    r = llm.generate(system, user, temperature=p.temperature, schema=Plan)
    out = r.parsed or {"role_ok": False, "questions": []}
    out["_meta"] = {"prompt": "P1", "model": r.model, "latency_s": r.latency_s, "error": r.error}
    return out


# ---------- P2 ----------
def _parse_v1_text(text: str) -> dict:
    """v1 returns free text; pull a 1-5 score out with a regex (best effort)."""
    m = re.search(r"score\D{0,15}([1-5])(?:\s*/\s*5|\s*out of 5)?", text, re.I) or re.search(
        r"\b([1-5])\s*/\s*5\b", text
    )
    return {"overall": int(m.group(1)) if m else None}


def evaluate_answer(
    role: str,
    round_type: str,
    question: str,
    answer: str,
    key_points: list[str] | None = None,
    version: str = "v4",
    model: str | None = None,
) -> dict:
    """Score one answer. version = v1 | v2 | v3 | v4 (final)."""
    err = guards.pre_check_answer(answer)
    if err and version == "v4":
        ev = {
            "valid_answer": False,
            "injection_detected": False,
            "scores": {c: 1 for c in guards.CRITERIA},
            "evidence": [],
            "weakest_area": "correctness",
            "strengths": [],
            "improvements": [err],
            "blocked_before_api": True,
        }
        ev = guards.finalise_scores(ev)
        ev["_meta"] = {"prompt": "P2", "version": "v4", "model": None, "latency_s": 0, "error": None}
        return ev

    answer = guards.clip_answer(answer or "")
    p = evaluator(version)
    system, user = p.render(
        role=role,
        round=round_type,
        question=question,
        answer=answer,
        key_points="; ".join(key_points or []) or "not given",
    )
    if version == "v1":
        r = llm.generate(system, user, temperature=p.temperature, model=model)
        out = _parse_v1_text(r.text)
        out["json_valid"] = llm.try_json(r.text) is not None
    elif version == "v2":
        r = llm.generate(system, user, temperature=p.temperature, model=model)
        parsed = llm.try_json(r.text)
        out = parsed if isinstance(parsed, dict) else {}
        out["json_valid"] = isinstance(parsed, dict) and "scores" in parsed
    elif version == "v3":
        r = llm.generate(system, user, temperature=p.temperature, json_mode=True, model=model)
        parsed = r.parsed if isinstance(r.parsed, dict) else llm.try_json(r.text)
        out = parsed if isinstance(parsed, dict) else {}
        out["json_valid"] = isinstance(parsed, dict) and "scores" in parsed
    else:  # v4 final
        is_gemma = (model or "").startswith("gemma")
        r = llm.generate(
            system, user, temperature=p.temperature, schema=None if is_gemma else Evaluation, model=model
        )
        parsed = r.parsed if isinstance(r.parsed, dict) else llm.try_json(r.text)
        out = parsed if isinstance(parsed, dict) else {}
        out["json_valid"] = isinstance(parsed, dict) and "scores" in parsed
        if out["json_valid"]:
            out = guards.verify_quotes(out, answer)
            out = guards.finalise_scores(out)

    if version in ("v2", "v3") and out.get("json_valid"):
        s = out.get("scores", {})
        vals = [v for v in s.values() if isinstance(v, (int, float))]
        out["overall"] = round(sum(vals) / len(vals), 2) if vals else None
        if version == "v3":  # v3 asked for quotes too: measure how many are real
            ev = out.get("evidence", []) or []
            out["quotes_total"] = len(ev)
            out["quotes_verbatim"] = sum(guards.quote_in_answer(e.get("quote", ""), answer) for e in ev)
    out["_raw"] = r.text
    out["_meta"] = {"prompt": "P2", "version": version, "model": r.model, "latency_s": r.latency_s, "error": r.error}
    return out


# ---------- P3 ----------
def generate_follow_up(role: str, round_type: str, question: str, answer: str, evaluation: dict) -> dict:
    weak = evaluation.get("weakest_area", "depth")
    comment = next(
        (e.get("comment", "") for e in evaluation.get("evidence", []) if e.get("criterion") == weak),
        "; ".join(evaluation.get("improvements", [])[:1]),
    )
    p = final("P3")
    system, user = p.render(
        role=role,
        round=round_type,
        question=question,
        answer=guards.clip_answer(answer or ""),
        valid_answer=str(evaluation.get("valid_answer", True)).lower(),
        weakest_area=weak,
        weak_comment=comment or "none",
    )
    r = llm.generate(system, user, temperature=p.temperature, schema=FollowUp)
    out = r.parsed or {"follow_up": "", "targets": weak, "why": ""}
    out["_meta"] = {"prompt": "P3", "model": r.model, "latency_s": r.latency_s, "error": r.error}
    return out


# ---------- P4 ----------
def _slim(ev: dict) -> dict:
    keep = ["valid_answer", "injection_detected", "scores", "overall", "evidence", "weakest_area", "strengths", "improvements"]
    return {k: ev.get(k) for k in keep if k in ev}


def write_report(role: str, round_type: str, transcript: list[dict]) -> dict:
    """transcript: [{question, topic, answer, evaluation, follow_up, follow_up_answer, follow_up_evaluation}]"""
    slim = []
    for i, t in enumerate(transcript, 1):
        item = {
            "no": i,
            "topic": t.get("topic", ""),
            "question": t.get("question", ""),
            "answer": t.get("answer", ""),
            "evaluation": _slim(t.get("evaluation", {})),
        }
        if t.get("follow_up"):
            item["follow_up"] = t["follow_up"]
            item["follow_up_answer"] = t.get("follow_up_answer", "")
            if t.get("follow_up_evaluation"):
                item["follow_up_evaluation"] = _slim(t["follow_up_evaluation"])
        slim.append(item)
    p = final("P4")
    system, user = p.render(role=role, round=round_type, transcript_json=json.dumps(slim, indent=1, ensure_ascii=False))
    r = llm.generate(system, user, temperature=p.temperature)
    return {"report_md": r.text, "_meta": {"prompt": "P4", "model": r.model, "latency_s": r.latency_s, "error": r.error}}
