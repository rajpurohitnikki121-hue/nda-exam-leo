"""NDA exam engine: paper building, timing and marking. Pure Python (no Telegram imports)."""

import random
import re
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
# ---- SSC CGL Tier-1 pattern: 4 sections x 25 Q, +2 each, -0.50 per wrong, 60 min total ----
SSC_ORDER = ("ssc_reasoning", "ssc_gs", "ssc_quant", "ssc_english")  # same order as the real paper
SSC_PAPER_SUBJECT = {
    "sscreasoning": "ssc_reasoning",
    "sscgs": "ssc_gs",
    "sscquant": "ssc_quant",
    "sscenglish": "ssc_english",
}
for _s in SSC_ORDER:
    MARKS[_s] = 2.0
    PENALTY[_s] = 0.5
    FULL_COUNT[_s] = 25
    FULL_MINUTES[_s] = 15
SSC_FULL_COUNT = 100
SUBJECT_LABEL.update(
    {"ssc_reasoning": "Reasoning", "ssc_gs": "General Awareness", "ssc_quant": "Quant", "ssc_english": "English"}
)
SUBJECT_ICON = {
    "maths": "📐", "gat": "🧠",
    "ssc_reasoning": "🧩", "ssc_gs": "🌍", "ssc_quant": "📐", "ssc_english": "📝",
}
PAPER_LABEL.update(
    {
        "ssc": "SSC Mixed (Reasoning+GA+Quant+English)",
        "sscreasoning": "SSC Reasoning",
        "sscgs": "SSC General Awareness",
        "sscquant": "SSC Quant (Maths)",
        "sscenglish": "SSC English",
    }
)
# ---- Banking Prelims (IBPS / SBI style): English 30 + Quant 35 + Reasoning 35 = 100 Q, 60 min,
# +1 per correct, -0.25 per wrong. Banking/General Awareness (bank_ga) is a separate practice
# section (Mains-style: 50 Q, 35 min).
BANK_ORDER = ("bank_english", "bank_quant", "bank_reasoning")  # prelims papers
BANK_SUBJECTS = BANK_ORDER + ("bank_ga",)
BANK_PAPER_SUBJECT = {
    "bankenglish": "bank_english",
    "bankquant": "bank_quant",
    "bankreasoning": "bank_reasoning",
    "bankga": "bank_ga",
}
for _s, _n, _m in (("bank_english", 30, 20), ("bank_quant", 35, 20), ("bank_reasoning", 35, 20), ("bank_ga", 50, 35)):
    MARKS[_s] = 1.0
    PENALTY[_s] = 0.25
    FULL_COUNT[_s] = _n
    FULL_MINUTES[_s] = _m
BANK_FULL_COUNT = 100
SUBJECT_LABEL.update(
    {
        "bank_english": "English",
        "bank_quant": "Quant",
        "bank_reasoning": "Reasoning",
        "bank_ga": "Banking & General Awareness",
    }
)
SUBJECT_ICON.update({"bank_english": "📝", "bank_quant": "📐", "bank_reasoning": "🧩", "bank_ga": "🏦"})
PAPER_LABEL.update(
    {
        "bank": "Banking Prelims (English+Quant+Reasoning)",
        "bankenglish": "Banking English",
        "bankquant": "Banking Quant",
        "bankreasoning": "Banking Reasoning",
        "bankga": "Banking & General Awareness",
    }
)
# ---- Rajasthan CET, SENIOR SECONDARY (12th) level: 120 Q, 240 marks (2 each), 150 min, 1/3 negative ----
# The board does not fix section-wise quotas; the split below follows the *indicative* weightage published
# by coaching sources (Rajasthan GK ~55%, Science+Current affairs ~17%, Maths+Reasoning ~16%,
# Hindi+English ~14%, Computer ~5%) scaled to 120 questions. Check the official RSSB notice.
CET_ORDER = ("cet_gk", "cet_raj", "cet_lang", "cet_reasoning", "cet_computer")
CET_PAPER_SUBJECT = {
    "cetgk": "cet_gk",
    "cetraj": "cet_raj",
    "cetlang": "cet_lang",
    "cetreasoning": "cet_reasoning",
    "cetcomputer": "cet_computer",
}
# "1/3 negative marking" = one third of a question's marks (2 marks -> 0.67). Change here if the board
# means a flat 1/3 mark: CET_PENALTY = 1 / 3
CET_PENALTY = 2 / 3
for _s, _n in zip(CET_ORDER, (20, 58, 17, 19, 6)):
    MARKS[_s] = 2.0
    PENALTY[_s] = CET_PENALTY
    FULL_COUNT[_s] = _n
    FULL_MINUTES[_s] = _n * 1.25  # 150 min for 120 Q
CET_FULL_COUNT = 120
SUBJECT_LABEL.update(
    {
        "cet_gk": "GK & Science",
        "cet_raj": "Rajasthan GK",
        "cet_lang": "Hindi & English",
        "cet_reasoning": "Reasoning & Maths",
        "cet_computer": "Computer",
    }
)
SUBJECT_ICON.update(
    {"cet_gk": "🌍", "cet_raj": "🏜️", "cet_lang": "📝", "cet_reasoning": "🧩", "cet_computer": "💻"}
)
PAPER_LABEL.update(
    {
        "cet": "Rajasthan CET 12th level",
        "cetgk": "CET GK & Science",
        "cetraj": "CET Rajasthan GK",
        "cetlang": "CET Hindi & English",
        "cetreasoning": "CET Reasoning & Maths",
        "cetcomputer": "CET Computer",
    }
)
SINGLE_PAPER_SUBJECT = {**SSC_PAPER_SUBJECT, **BANK_PAPER_SUBJECT, **CET_PAPER_SUBJECT}
EXAM_SUBJECTS = {"nda": ("maths", "gat"), "ssc": SSC_ORDER, "bank": BANK_SUBJECTS, "cet": CET_ORDER}
SECTION_PREFIXES = {"nda": "s_", "ssc": "t_", "bank": "b_", "cet": "r_"}

GAT_ENGLISH_FULL = 50  # English part of the GAT paper
GAT_GK_FULL = 100  # General Knowledge part of the GAT paper

# Sections that are NOT part of the real NDA papers: only usable in section-wise practice.
EXTRA_SECTIONS = {"reasoning"}
MIN_SECTION_Q = 3
SECTION_PREFIX = "s_"  # paper key for section-wise practice, e.g. "s_physics"


def section_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def exam_of_paper(paper: str) -> str:
    """"nda" | "ssc" | "bank" for any paper key (mixed, single section or topic-wise)."""
    if paper == "ssc" or paper in SSC_PAPER_SUBJECT or paper.startswith(SECTION_PREFIXES["ssc"]):
        return "ssc"
    if paper == "bank" or paper in BANK_PAPER_SUBJECT or paper.startswith(SECTION_PREFIXES["bank"]):
        return "bank"
    if paper == "cet" or paper in CET_PAPER_SUBJECT or paper.startswith(SECTION_PREFIXES["cet"]):
        return "cet"
    return "nda"


def is_ssc_paper(paper: str) -> bool:
    return exam_of_paper(paper) == "ssc"


def _exam_of_section(paper: str) -> Optional[str]:
    for exam, prefix in SECTION_PREFIXES.items():
        if paper.startswith(prefix) and len(paper) > len(prefix):
            return exam
    return None


def is_section_paper(paper: str) -> bool:
    return _exam_of_section(paper) is not None


def section_pool(bank: NdaBank, paper: str) -> List[NdaQuestion]:
    exam = _exam_of_section(paper)
    if exam is None:
        return []
    slug = paper[len(SECTION_PREFIXES[exam]):]
    return [
        q
        for q in bank.all()
        if q.subject in EXAM_SUBJECTS[exam] and q.section and section_slug(q.section) == slug
    ]


def list_sections(bank: NdaBank, exam: str = "nda") -> List[tuple]:
    """[(paper_key, display_name, subject, count)] for one exam, sorted by subject then name."""
    subjects = EXAM_SUBJECTS[exam]
    found: Dict[str, list] = {}
    for q in bank.all():
        if q.subject not in subjects or not q.section:
            continue
        slug = section_slug(q.section)
        if slug not in found:
            found[slug] = [q.section, q.subject, 0]
        found[slug][2] += 1
    rows = [
        (SECTION_PREFIXES[exam] + slug, v[0], v[1], v[2])
        for slug, v in found.items()
        if v[2] >= MIN_SECTION_Q  # tiny topics stay hidden until they have enough questions
    ]
    rows.sort(key=lambda r: (subjects.index(r[2]), r[1].lower()))
    return rows


def paper_label(bank: NdaBank, paper: str) -> str:
    if paper in PAPER_LABEL:
        return PAPER_LABEL[paper]
    if is_section_paper(paper):
        pool = section_pool(bank, paper)
        if pool:
            tag = {"ssc": "SSC", "bank": "Banking", "cet": "CET"}.get(exam_of_paper(paper), "section")
            return f"{pool[0].section} ({tag})"
    return paper


def is_valid_paper(bank: NdaBank, paper: str) -> bool:
    return paper in PAPER_LABEL or (is_section_paper(paper) and bool(section_pool(bank, paper)))


def _balanced(
    pools: List[List[NdaQuestion]], subjects: tuple, total: int, rng: random.Random, seen
) -> List[NdaQuestion]:
    """Share of each section follows the real paper (weights = full-paper question counts)."""
    weights = [FULL_COUNT[s] for s in subjects]
    wsum = sum(weights)
    raw = [total * w / wsum for w in weights]
    quotas = [int(x) for x in raw]
    left = total - sum(quotas)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - quotas[i]), rng.random()))
    for i in order[:left]:
        quotas[i] += 1
    picked: List[NdaQuestion] = []
    deficit = 0
    for quota, pool in zip(quotas, pools):
        take = min(quota, len(pool))
        picked += _sample(pool, take, rng, seen)
        deficit += quota - take
    if deficit:
        chosen = {q.qid for q in picked}
        rest = [q for pool in pools for q in pool if q.qid not in chosen]
        picked += _sample(rest, deficit, rng, seen)
    picked.sort(key=lambda q: subjects.index(q.subject))
    return picked


def _paper_pool(bank: NdaBank, subject: str) -> List[NdaQuestion]:
    """Real-paper pool: leaves out practice-only sections such as Reasoning."""
    return [q for q in bank.by_subject(subject) if q.section.lower() not in EXTRA_SECTIONS]


@dataclass
class PaperPlan:
    questions: List[NdaQuestion]
    requested: int
    full: bool
    repeated: int = 0  # how many picked questions the user has seen before

    @property
    def shortage(self) -> bool:
        return len(self.questions) < self.requested


def _seconds_for(questions: List[NdaQuestion], full: bool) -> int:
    """Exam time: full paper = official time, custom = same pace per question."""
    secs = 0.0
    for subject in FULL_COUNT:
        n = sum(1 for q in questions if q.subject == subject)
        if not n:
            continue
        minutes = FULL_MINUTES[subject]
        per_q = minutes * 60 / FULL_COUNT[subject]
        secs += n * per_q
    return max(60, int(round(secs)))


def _sample(pool: List[NdaQuestion], k: int, rng: random.Random, seen) -> List[NdaQuestion]:
    """Random pick that prefers questions the user has not seen yet."""
    k = min(k, len(pool))
    fresh = [q for q in pool if q.qid not in seen]
    # Hard-level questions (ids starting "CETH-") are served first, easy ones fill the gap.
    hard = [q for q in fresh if q.qid.startswith("CETH-")]
    if 0 < len(hard) < len(fresh):
        easy = [q for q in fresh if not q.qid.startswith("CETH-")]
        if len(hard) >= k:
            return rng.sample(hard, k)
        picked = hard + rng.sample(easy, min(k - len(hard), len(easy)))
        if len(picked) >= k:
            rng.shuffle(picked)
            return picked
    if len(fresh) >= k:
        return rng.sample(fresh, k)
    repeats = [q for q in pool if q.qid in seen]
    picked = fresh + rng.sample(repeats, k - len(fresh))
    rng.shuffle(picked)
    return picked


def build_plan(
    bank: NdaBank,
    paper: str,
    count: int,
    rng: Optional[random.Random] = None,
    seen=None,
) -> PaperPlan:
    """Pick questions for a test. `seen` = question ids this user already got (they are avoided)."""
    seen = frozenset(seen or ())
    plan = _build_plan(bank, paper, count, rng, seen)
    plan.repeated = sum(1 for q in plan.questions if q.qid in seen)
    return plan


def _build_plan(bank: NdaBank, paper: str, count: int, rng, seen) -> PaperPlan:
    """Pick questions for a test.

    paper : "maths" | "gat" | "mixed"
    count : number of questions, or 0 for the full official paper.
    """
    rng = rng or random.Random()
    full = count == 0

    if paper in SINGLE_PAPER_SUBJECT:  # one section of SSC / Banking (full = real section size)
        subject = SINGLE_PAPER_SUBJECT[paper]
        pool = bank.by_subject(subject)
        requested = FULL_COUNT[subject] if full else count
        return PaperPlan(questions=_sample(pool, requested, rng, seen), requested=requested, full=full)

    if paper == "ssc":  # SSC mixed: Reasoning + GA + Quant + English, equal share
        pools = [bank.by_subject(s) for s in SSC_ORDER]
        requested = SSC_FULL_COUNT if full else count
        return PaperPlan(
            questions=_balanced(pools, SSC_ORDER, requested, rng, seen), requested=requested, full=full
        )

    if paper == "cet":  # Rajasthan CET: weights follow the 20/58/17/19/6 split
        pools = [bank.by_subject(s) for s in CET_ORDER]
        requested = CET_FULL_COUNT if full else count
        return PaperPlan(
            questions=_balanced(pools, CET_ORDER, requested, rng, seen), requested=requested, full=full
        )

    if paper == "bank":  # Banking prelims: English 30 / Quant 35 / Reasoning 35
        pools = [bank.by_subject(s) for s in BANK_ORDER]
        requested = BANK_FULL_COUNT if full else count
        return PaperPlan(
            questions=_balanced(pools, BANK_ORDER, requested, rng, seen), requested=requested, full=full
        )

    if is_section_paper(paper):  # section-wise practice: count 0 = every question of that section
        pool = section_pool(bank, paper)
        requested = len(pool) if full else count
        return PaperPlan(questions=_sample(pool, requested, rng, seen), requested=requested, full=False)

    if paper in ("maths", "gat"):
        pool = _paper_pool(bank, paper)
        if full:
            requested = FULL_COUNT[paper]
            if paper == "gat":
                picked = _pick_gat_full(pool, rng, seen)
            else:
                picked = _sample(pool, requested, rng, seen)
        else:
            requested = count
            picked = _sample(pool, count, rng, seen)
    else:  # mixed
        maths_pool = _paper_pool(bank, "maths")
        gat_pool = _paper_pool(bank, "gat")
        if full:
            requested = FULL_COUNT["maths"] + FULL_COUNT["gat"]
            picked = _sample(maths_pool, FULL_COUNT["maths"], rng, seen)
            picked += _pick_gat_full(gat_pool, rng, seen)
        else:
            requested = count
            pool = maths_pool + gat_pool
            picked = _sample(pool, count, rng, seen)

    return PaperPlan(questions=picked, requested=requested, full=full)


def _pick_gat_full(pool: List[NdaQuestion], rng: random.Random, seen) -> List[NdaQuestion]:
    """50 English + 100 GK like the real paper (fills from the other part if short)."""
    english = [q for q in pool if q.section.lower() == "english"]
    others = [q for q in pool if q.section.lower() != "english"]
    eng_pick = _sample(english, GAT_ENGLISH_FULL, rng, seen)
    gk_pick = _sample(others, GAT_GK_FULL, rng, seen)
    missing = FULL_COUNT["gat"] - len(eng_pick) - len(gk_pick)
    if missing > 0:
        left = [q for q in pool if q not in eng_pick and q not in gk_pick]
        extra = _sample(left, missing, rng, seen)
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
