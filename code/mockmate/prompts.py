"""Load prompt files from the prompts/ folder.

Each prompt file has a small header (between --- lines) and two sections:
### SYSTEM and ### USER. The app and the test scripts both read the prompts
from these files, so the files in the repo are exactly what runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT / "prompts"

FINAL_FILES = {
    "P1": "final/P1_planner.txt",
    "P2": "final/P2_evaluator.txt",
    "P3": "final/P3_followup.txt",
    "P4": "final/P4_report.txt",
}

EVALUATOR_VERSIONS = {
    "v1": "v1/P2_evaluator_v1.txt",
    "v2": "v2/P2_evaluator_v2.txt",
    "v3": "v3/P2_evaluator_v3.txt",
    "v4": "final/P2_evaluator.txt",
}


@dataclass
class Prompt:
    path: Path
    meta: dict = field(default_factory=dict)
    system: str = ""
    user: str = ""

    @property
    def temperature(self) -> float | None:
        t = str(self.meta.get("temperature", "default")).strip()
        try:
            return float(t)
        except ValueError:
            return None  # "default" -> let the model use its default

    def render(self, **values) -> tuple[str, str]:
        """Fill {variables}. Plain replace is used so JSON braces in the
        few-shot examples are left untouched."""
        user = self.user
        for key, val in values.items():
            user = user.replace("{" + key + "}", str(val))
        system = "" if self.system.strip().lower() == "none" else self.system
        return system, user


def load_prompt(rel_path: str) -> Prompt:
    path = PROMPTS_DIR / rel_path
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    meta: dict = {}
    if text.startswith("---"):
        _, header, text = text.split("---", 2)
        for line in header.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    system, user = "", ""
    if "### SYSTEM" in text and "### USER" in text:
        system = text.split("### SYSTEM", 1)[1].split("### USER", 1)[0].strip()
        user = text.split("### USER", 1)[1].strip()
    else:
        user = text.strip()
    return Prompt(path=path, meta=meta, system=system, user=user)


def final(pid: str) -> Prompt:
    return load_prompt(FINAL_FILES[pid])


def evaluator(version: str) -> Prompt:
    return load_prompt(EVALUATOR_VERSIONS[version])
