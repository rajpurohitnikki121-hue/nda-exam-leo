"""NDA exam engine: paper building, timing and marking. Pure Python (no Telegram imports)."""

import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from services.nda_bank import NdaBank, NdaQuestion

# ---- Official NDA pattern ---------------------------------------------------
# Paper I   Mathematics            : 120 questions, 2.5 marks each, 150 minutes
# Paper II  General Ability (GAT)  : 150 questions, 4 marks each,   150 minutes
# Negative marking: one third of the marks for every wrong answer (0.83 / 1.33).
MARKS = {"maths": 2.5, "gat": 4.0}
PENALTY = {"maths": 0.83, "gat": 1.33}
FULL_COUNT = {"maths": 120, "gat": 150}
FULL_MINUTES = {"maths": 150, "gat": 150}
SUBJECT_LABEL = {"maths": "Maths", "gat": "GAT"}
PAPER_LABEL = {"maths": "Maths", "gat": "GAT", "mixed": "Maths + GAT"}
GAT_ENGLISH_FULL = 50  # English part of the GAT paper
GAT_GK_FULL = 100  # General Knowledge part of the GAT paper


@dataclass
class PaperPlan:
    questions: List[NdaQuestion]
    requested: int
    full: bool

    @property
    def shortage(self) -> bool:
        return len(self.questions) < self.requested


def _seconds_for(questions: List[NdaQuestion], full: bool) -> int:
    """Exam time: full paper = official time, custom = same pace per question."""
    secs = 0.0
    for subject in ("maths", "gat"):
        n = sum(1 for q in questions if q.subject == subject)
        if not n:
            continue
        minutes = FULL_MINUTES[subject]
        per_q = minutes * 60 / FULL_COUNT[subject]
        secs += n * per_q
    return max(60, int(round(secs)))


def build_plan(bank: NdaBank, paper: str, count: int, rng: Optional[random.Random] = None) -> PaperPlan:
    """Pick questions for a test.

    paper : "maths" | "gat" | "mixed"
    count : number of questions, or 0 for the full official paper.
    """
    rng = rng or random.Random()
    full = count == 0

    if paper in ("maths", "gat"):
        pool = bank.by_subject(paper)
        if full:
            requested = FULL_COUNT[paper]
            if paper == "gat":
                picked = _pick_gat_full(pool, rng)
            else:
                picked = rng.sample(pool, min(requested, len(pool)))
        else:
            requested = count
            picked = rng.sample(pool, min(count, len(pool)))
    else:  # mixed
        maths_pool = bank.by_subject("maths")
        gat_pool = bank.by_subject("gat")
        if full:
            requested = FULL_COUNT["maths"] + FULL_COUNT["gat"]
            picked = rng.sample(maths_pool, min(FULL_COUNT["maths"], len(maths_pool)))
            picked += _pick_gat_full(gat_pool, rng)
        else:
            requested = count
            pool = maths_pool + gat_pool
            picked = rng.sample(pool, min(count, len(pool)))

    return PaperPlan(questions=picked, requested=requested, full=full)


def _pick_gat_full(pool: List[NdaQuestion], rng: random.Random) -> List[NdaQuestion]:
    """50 English + 100 GK like the real paper (fills from the other part if short)."""
    english = [q for q in pool if q.section.lower() == "english"]
    others = [q for q in pool if q.section.lower() != "english"]
    eng_pick = rng.sample(english, min(GAT_ENGLISH_FULL, len(english)))
    gk_pick = rng.sample(others, min(GAT_GK_FULL, len(others)))
    missing = FULL_COUNT["gat"] - len(eng_pick) - len(gk_pick)
    if missing > 0:
        left = [q for q in pool if q not in eng_pick and q not in gk_pick]
        extra = rng.sample(left, min(missing, len(left)))
        # extras are GK/English leftovers; keep English first, then the rest
        eng_pick += [q for q in extra if q.section.lower() == "english"]
        gk_pick += [q for q in extra if q.section.lower() != "english"]
    return eng_pick + gk_pick


@dataclass
class ExamSession:
    user_id: int
    paper: str
    negative: bool
    plan: PaperPlan
    duration_s: int
    answers: Dict[int, int] = field(default_factory=dict)  # question index -> chosen option
    pos: int = 0
    chat_id: int = 0
    message_id: int = 0
    started_at: float = field(default_factory=time.monotonic)
    ended_at: Optional[float] = None
    finished: bool = False

    @property
    def questions(self) -> List[NdaQuestion]:
        return self.plan.questions

    @property
    def total(self) -> int:
        return len(self.plan.questions)

    @property
    def deadline(self) -> float:
        return self.started_at + self.duration_s

    def remaining(self) -> int:
        return max(0, int(self.deadline - time.monotonic()))

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def time_taken(self) -> int:
        end = self.ended_at if self.ended_at is not None else time.monotonic()
        return int(min(end, self.deadline) - self.started_at)


def new_session(user_id: int, paper: str, negative: bool, plan: PaperPlan) -> ExamSession:
    return ExamSession(
        user_id=user_id,
        paper=paper,
        negative=negative,
        plan=plan,
        duration_s=_seconds_for(plan.questions, plan.full),
    )


@dataclass
class SubjectScore:
    total: int = 0
    correct: int = 0
    wrong: int = 0
    skipped: int = 0
    gained: float = 0.0
    lost: float = 0.0
    max_marks: float = 0.0

    @property
    def score(self) -> float:
        return round(self.gained - self.lost, 2)


@dataclass
class ExamResult:
    per_subject: Dict[str, SubjectScore]
    correct: int
    wrong: int
    skipped: int
    gained: float
    lost: float
    max_marks: float
    time_taken_s: int
    missed_indices: List[int]  # wrong + skipped question indices (for review)

    @property
    def total(self) -> int:
        return self.correct + self.wrong + self.skipped

    @property
    def score(self) -> float:
        return round(self.gained - self.lost, 2)

    @property
    def percentage(self) -> float:
        return round(self.score / self.max_marks * 100, 2) if self.max_marks else 0.0

    @property
    def accuracy(self) -> float:
        attempted = self.correct + self.wrong
        return round(self.correct / attempted * 100, 1) if attempted else 0.0


def compute_result(session: ExamSession) -> ExamResult:
    per_subject: Dict[str, SubjectScore] = {}
    correct = wrong = skipped = 0
    gained = lost = max_marks = 0.0
    missed: List[int] = []

    for idx, q in enumerate(session.questions):
        sub = per_subject.setdefault(q.subject, SubjectScore())
        marks = MARKS[q.subject]
        sub.total += 1
        sub.max_marks += marks
        max_marks += marks

        chosen = session.answers.get(idx)
        if chosen is None:
            sub.skipped += 1
            skipped += 1
            missed.append(idx)
        elif chosen == q.answer:
            sub.correct += 1
            sub.gained += marks
            correct += 1
            gained += marks
        else:
            sub.wrong += 1
            wrong += 1
            missed.append(idx)
            if session.negative:
                sub.lost += PENALTY[q.subject]
                lost += PENALTY[q.subject]

    for sub in per_subject.values():
        sub.gained = round(sub.gained, 2)
        sub.lost = round(sub.lost, 2)
        sub.max_marks = round(sub.max_marks, 2)

    return ExamResult(
        per_subject=per_subject,
        correct=correct,
        wrong=wrong,
        skipped=skipped,
        gained=round(gained, 2),
        lost=round(lost, 2),
        max_marks=round(max_marks, 2),
        time_taken_s=session.time_taken(),
        missed_indices=missed,
    )


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"
