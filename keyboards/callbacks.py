from typing import Optional
from aiogram.filters.callback_data import CallbackData


class ExamCB(CallbackData, prefix="ex"):
    action: str  # "sel"
    exam_id: int


class SubjectCB(CallbackData, prefix="sb"):
    action: str  # "sel"
    subject_id: int


class ScopeCB(CallbackData, prefix="sc"):
    action: str  # "sel"
    scope: str  # "chap" or "full"


class ChapterCB(CallbackData, prefix="ch"):
    action: str  # "sel"
    chapter_id: int


class CompCB(CallbackData, prefix="cp"):
    action: str  # "sel"
    comp: str  # "typ" or "mix"
    sub_type_id: int = 0


class ModeCB(CallbackData, prefix="md"):
    action: str  # "sel"
    mode: str  # "timed" or "untimed"
    timer: int = 0  # 30, 45, 60 or section timer seconds


class QuizAnsCB(CallbackData, prefix="qa"):
    q_id: int
    opt: int


class QuizNavCB(CallbackData, prefix="qn"):
    action: str  # "next", "sol", "quit"


class AdminBroadcastCB(CallbackData, prefix="ab"):
    step: str  # "exam", "sub", "ch", "count", "send", "cancel"
    exam_id: int = 0
    subject_id: int = 0
    chapter_id: int = 0
    count: int = 0


class NavCB(CallbackData, prefix="nv"):
    to: str  # "menu", "exams", "subjects", "scope", "chapters", "comp", "modes", "cancel", "stats", "lb"


class NdaCB(CallbackData, prefix="nda"):
    a: str  # action: home, info, paper, cnt, go, ans, nav, rev
    v: str = ""  # value, e.g. "maths", "maths:25", "maths:25:1", "3:2", "next"


class FsubCB(CallbackData, prefix="fs"):
    a: str  # "check"
