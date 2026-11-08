from typing import List, Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Chapter, Exam, Subject, SubType
from .callbacks import (
    AdminBroadcastCB,
    ChapterCB,
    CompCB,
    ExamCB,
    ModeCB,
    NavCB,
    NdaCB,
    QuizAnsCB,
    QuizNavCB,
    ScopeCB,
    SubjectCB,
)


def build_main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Main landing menu keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🎖️ NDA Exam Practice",
            callback_data=NdaCB(a="home").pack(),
        )
    )
    return builder.as_markup()


def build_exam_kb(exams: List[Exam]) -> InlineKeyboardMarkup:
    """Builds exam selection keyboard categorized by exam board."""
    builder = InlineKeyboardBuilder()

    # Category icons mapping
    category_icons = {
        "SSC Exams": "🏛️",
        "Banking Exams": "🏦",
        "Railways": "🚆",
        "UPSC CSAT": "🇮🇳",
        "UPSSSC PET": "📜",
    }

    # Group by category
    categories = {}
    for exam in exams:
        categories.setdefault(exam.category, []).append(exam)

    for cat_name, cat_exams in categories.items():
        icon = category_icons.get(cat_name, "📚")
        # Add category header or row of exams
        for exam in cat_exams:
            builder.row(
                InlineKeyboardButton(
                    text=f"{icon} {exam.name}",
                    callback_data=ExamCB(action="sel", exam_id=exam.id).pack(),
                )
            )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Main Menu",
            callback_data=NavCB(to="menu").pack(),
        )
    )
    return builder.as_markup()


def build_subject_kb(subjects: List[Subject]) -> InlineKeyboardMarkup:
    """Builds subject/section selection keyboard."""
    builder = InlineKeyboardBuilder()

    subject_icons = {
        "quant": "📐",
        "reason": "🧩",
        "eng": "📖",
        "ga": "🌍",
        "sci": "🔬",
        "math": "🔢",
        "hindi": "✍️",
    }

    for subj in subjects:
        # Determine icon based on code
        code_lower = subj.code.lower()
        icon = "📚"
        for k, v in subject_icons.items():
            if k in code_lower:
                icon = v
                break

        builder.row(
            InlineKeyboardButton(
                text=f"{icon} {subj.name}",
                callback_data=SubjectCB(action="sel", subject_id=subj.id).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Exams",
            callback_data=NavCB(to="exams").pack(),
        ),
        InlineKeyboardButton(
            text="🏠 Menu",
            callback_data=NavCB(to="menu").pack(),
        ),
    )
    return builder.as_markup()


def build_scope_kb() -> InlineKeyboardMarkup:
    """Builds scope selection keyboard: Chapter-wise vs Full Subject Section."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📖 Chapter-wise Practice",
            callback_data=ScopeCB(action="sel", scope="chap").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📝 Full-Subject Section Test",
            callback_data=ScopeCB(action="sel", scope="full").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Subjects",
            callback_data=NavCB(to="subjects").pack(),
        ),
        InlineKeyboardButton(
            text="🏠 Menu",
            callback_data=NavCB(to="menu").pack(),
        ),
    )
    return builder.as_markup()


def build_chapter_kb(chapters: List[Chapter]) -> InlineKeyboardMarkup:
    """Builds chapter selection keyboard."""
    builder = InlineKeyboardBuilder()

    for ch in chapters:
        builder.row(
            InlineKeyboardButton(
                text=f"📌 {ch.name}",
                callback_data=ChapterCB(action="sel", chapter_id=ch.id).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Scope",
            callback_data=NavCB(to="scope").pack(),
        ),
        InlineKeyboardButton(
            text="🏠 Menu",
            callback_data=NavCB(to="menu").pack(),
        ),
    )
    return builder.as_markup()


def build_composition_kb(sub_types: List[SubType]) -> InlineKeyboardMarkup:
    """Builds question composition keyboard: Type-wise vs Mix."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔀 Mix All Types (Combined)",
            callback_data=CompCB(action="sel", comp="mix", sub_type_id=0).pack(),
        )
    )

    if sub_types:
        for st in sub_types:
            builder.row(
                InlineKeyboardButton(
                    text=f"🎯 Type: {st.name}",
                    callback_data=CompCB(action="sel", comp="typ", sub_type_id=st.id).pack(),
                )
            )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Back to Chapters",
            callback_data=NavCB(to="chapters").pack(),
        ),
        InlineKeyboardButton(
            text="🏠 Menu",
            callback_data=NavCB(to="menu").pack(),
        ),
    )
    return builder.as_markup()


def build_mode_kb(is_full_section: bool = False, exam_code: str = "") -> InlineKeyboardMarkup:
    """Builds timer & mode engine keyboard."""
    builder = InlineKeyboardBuilder()

    # Untimed Practice
    builder.row(
        InlineKeyboardButton(
            text="💡 Untimed Practice (Instant Solutions & Tricks)",
            callback_data=ModeCB(action="sel", mode="untimed", timer=0).pack(),
        )
    )

    # Timed Options
    if is_full_section:
        if "bank" in exam_code.lower():
            builder.row(
                InlineKeyboardButton(
                    text="⏱️ 20-Min Sectional Timer (Banking Speed ~35s/Q)",
                    callback_data=ModeCB(action="sel", mode="timed", timer=1200).pack(),
                )
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="⏱️ 20-Min Sectional Timer (SSC Standard ~60s/Q)",
                    callback_data=ModeCB(action="sel", mode="timed", timer=1200).pack(),
                )
            )

    # Fast Drill Per-Question Timers
    builder.row(
        InlineKeyboardButton(
            text="⚡ 30s Fast Drill",
            callback_data=ModeCB(action="sel", mode="timed", timer=30).pack(),
        ),
        InlineKeyboardButton(
            text="⚡ 45s Standard Drill",
            callback_data=ModeCB(action="sel", mode="timed", timer=45).pack(),
        ),
        InlineKeyboardButton(
            text="⚡ 60s Deep Drill",
            callback_data=ModeCB(action="sel", mode="timed", timer=60).pack(),
        ),
    )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Back",
            callback_data=NavCB(to="comp" if not is_full_section else "scope").pack(),
        ),
        InlineKeyboardButton(
            text="🏠 Menu",
            callback_data=NavCB(to="menu").pack(),
        ),
    )
    return builder.as_markup()


def build_interactive_quiz_kb(
    q_id: int,
    options: List[str],
    selected_opt: Optional[int] = None,
    correct_opt: Optional[int] = None,
    has_next: bool = True,
) -> InlineKeyboardMarkup:
    """Builds interactive DM quiz question card with immediate tap feedback."""
    builder = InlineKeyboardBuilder()
    opt_letters = ["A", "B", "C", "D"]

    if selected_opt is None:
        # Not yet answered: Show option buttons
        for idx, opt_text in enumerate(options):
            letter = opt_letters[idx] if idx < 4 else f"{idx+1}"
            builder.row(
                InlineKeyboardButton(
                    text=f"{letter}. {opt_text}",
                    callback_data=QuizAnsCB(q_id=q_id, opt=idx).pack(),
                )
            )
        builder.row(
            InlineKeyboardButton(
                text="❌ Quit Practice",
                callback_data=QuizNavCB(action="quit").pack(),
            )
        )
    else:
        # Already answered: Show option status
        for idx, opt_text in enumerate(options):
            letter = opt_letters[idx] if idx < 4 else f"{idx+1}"
            if idx == correct_opt:
                prefix = "✅ "
            elif idx == selected_opt:
                prefix = "❌ "
            else:
                prefix = "◽ "

            builder.row(
                InlineKeyboardButton(
                    text=f"{prefix}{letter}. {opt_text}",
                    callback_data=f"ignore_{idx}",  # disabled
                )
            )

        # Navigation row
        nav_buttons = []
        if has_next:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Next Question ➡️",
                    callback_data=QuizNavCB(action="next").pack(),
                )
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="🏁 View Scorecard",
                    callback_data=QuizNavCB(action="next").pack(),
                )
            )

        builder.row(*nav_buttons)
        builder.row(
            InlineKeyboardButton(
                text="❌ End Quiz",
                callback_data=QuizNavCB(action="quit").pack(),
            )
        )

    return builder.as_markup()


def build_admin_broadcast_kb(
    step: str,
    items: list = None,
    exam_id: int = 0,
    subject_id: int = 0,
    chapter_id: int = 0,
) -> InlineKeyboardMarkup:
    """Builds dynamic wizard keyboard for channel broadcasting."""
    builder = InlineKeyboardBuilder()

    if step == "exam" and items:
        for ex in items:
            builder.row(
                InlineKeyboardButton(
                    text=f"📢 {ex.name}",
                    callback_data=AdminBroadcastCB(
                        step="sub", exam_id=ex.id, subject_id=0, chapter_id=0, count=0
                    ).pack(),
                )
            )
    elif step == "sub" and items:
        for sb in items:
            builder.row(
                InlineKeyboardButton(
                    text=f"📚 {sb.name}",
                    callback_data=AdminBroadcastCB(
                        step="ch", exam_id=exam_id, subject_id=sb.id, chapter_id=0, count=0
                    ).pack(),
                )
            )
    elif step == "ch" and items:
        builder.row(
            InlineKeyboardButton(
                text="🔀 All Chapters (Mixed Subject Polls)",
                callback_data=AdminBroadcastCB(
                    step="count", exam_id=exam_id, subject_id=subject_id, chapter_id=0, count=0
                ).pack(),
            )
        )
        for ch in items:
            builder.row(
                InlineKeyboardButton(
                    text=f"📌 {ch.name}",
                    callback_data=AdminBroadcastCB(
                        step="count", exam_id=exam_id, subject_id=subject_id, chapter_id=ch.id, count=0
                    ).pack(),
                )
            )
    elif step == "count":
        for count in [1, 3, 5, 10]:
            builder.row(
                InlineKeyboardButton(
                    text=f"🚀 Broadcast {count} Poll{'s' if count > 1 else ''} to Channel",
                    callback_data=AdminBroadcastCB(
                        step="send",
                        exam_id=exam_id,
                        subject_id=subject_id,
                        chapter_id=chapter_id,
                        count=count,
                    ).pack(),
                )
            )

    builder.row(
        InlineKeyboardButton(
            text="❌ Cancel Broadcast",
            callback_data=AdminBroadcastCB(step="cancel").pack(),
        )
    )
    return builder.as_markup()
