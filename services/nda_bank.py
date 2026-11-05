"""NDA question bank loader.

Questions live in plain JSON files under ``data/nda/``. Every ``*.json`` file in
that folder is loaded at startup, so adding a new year/paper means dropping a new
file in the folder - no code change needed.

File format (a JSON list):

    [
      {
        "id": "NDA-2023-I-M-001",
        "subject": "maths",            // "maths" or "gat"
        "section": "Algebra",          // topic, free text ("English" is used for the GAT English split)
        "year": 2023,                  // optional
        "paper": "NDA I 2023",         // optional, shown in the question header
        "source": "UPSC NDA I 2023 Maths Q12",   // optional
        "question": "Question text",
        "options": ["A text", "B text", "C text", "D text"],
        "answer": "B",                 // "A"-"D" (letter) or 0-3 (index)
        "explanation": "Optional solution"
      }
    ]

Entries whose ``source`` starts with ``SAMPLE`` are treated as demo questions and
flagged in the UI so they are never mistaken for real PYQs.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "nda"
VALID_SUBJECTS = ("maths", "gat")
_LETTERS = "ABCD"


@dataclass(frozen=True)
class NdaQuestion:
    qid: str
    subject: str
    section: str
    year: Optional[int]
    paper: str
    source: str
    question: str
    options: Tuple[str, ...]
    answer: int
    explanation: str

    @property
    def is_sample(self) -> bool:
        return self.source.upper().startswith("SAMPLE")


def _parse_answer(raw) -> Optional[int]:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if 0 <= raw <= 3 else None
    if isinstance(raw, str):
        text = raw.strip().upper()
        if text in _LETTERS and len(text) == 1:
            return _LETTERS.index(text)
        if text.isdigit() and 0 <= int(text) <= 3:
            return int(text)
    return None


def _parse_question(item: dict, origin: str) -> Optional[NdaQuestion]:
    if not isinstance(item, dict):
        logger.warning("%s: entry is not an object, skipped", origin)
        return None

    qid = str(item.get("id", "")).strip()
    subject = str(item.get("subject", "")).strip().lower()
    text = str(item.get("question", "")).strip()
    options = item.get("options")
    answer = _parse_answer(item.get("answer"))

    if not qid:
        logger.warning("%s: entry without id skipped", origin)
        return None
    if subject not in VALID_SUBJECTS:
        logger.warning("%s: %s has invalid subject %r (use maths/gat)", origin, qid, subject)
        return None
    if not text:
        logger.warning("%s: %s has empty question", origin, qid)
        return None
    if not isinstance(options, list) or len(options) != 4 or not all(
        str(o).strip() for o in options
    ):
        logger.warning("%s: %s must have exactly 4 non-empty options", origin, qid)
        return None
    if answer is None:
        logger.warning("%s: %s has invalid answer (use A-D or 0-3)", origin, qid)
        return None

    year = item.get("year")
    try:
        year = int(year) if year not in (None, "") else None
    except (TypeError, ValueError):
        year = None

    return NdaQuestion(
        qid=qid,
        subject=subject,
        section=str(item.get("section", "")).strip() or "General",
        year=year,
        paper=str(item.get("paper", "")).strip(),
        source=str(item.get("source", "")).strip(),
        question=text,
        options=tuple(str(o).strip() for o in options),
        answer=answer,
        explanation=str(item.get("explanation", "")).strip(),
    )


class NdaBank:
    def __init__(self) -> None:
        self._questions: Dict[str, NdaQuestion] = {}
        self.loaded = False

    def load(self, data_dir: Path = DATA_DIR) -> int:
        """(Re)load every JSON file in data_dir. Returns number of valid questions."""
        questions: Dict[str, NdaQuestion] = {}
        files = sorted(Path(data_dir).glob("*.json")) if Path(data_dir).exists() else []
        if not files:
            logger.warning("No NDA question files found in %s", data_dir)

        for path in files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.error("Could not read %s: %s", path.name, exc)
                continue
            if isinstance(payload, dict):
                payload = payload.get("questions", [])
            if not isinstance(payload, list):
                logger.error("%s: top level must be a list of questions", path.name)
                continue
            for item in payload:
                q = _parse_question(item, path.name)
                if q is None:
                    continue
                if q.qid in questions:
                    logger.warning("%s: duplicate id %s skipped", path.name, q.qid)
                    continue
                questions[q.qid] = q

        self._questions = questions
        self.loaded = True
        logger.info("NDA question bank loaded: %d questions", len(questions))
        return len(questions)

    def ensure_loaded(self) -> None:
        if not self.loaded:
            self.load()

    def all(self) -> List[NdaQuestion]:
        self.ensure_loaded()
        return list(self._questions.values())

    def by_subject(self, subject: str) -> List[NdaQuestion]:
        return [q for q in self.all() if q.subject == subject]

    def counts(self) -> Dict[str, int]:
        result = {s: 0 for s in VALID_SUBJECTS}
        for q in self.all():
            result[q.subject] += 1
        return result

    def sample_count(self) -> int:
        return sum(1 for q in self.all() if q.is_sample)


bank = NdaBank()
