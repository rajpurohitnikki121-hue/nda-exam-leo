"""NDA exam practice: bot sends questions one by one, marks the test at the end.

Flow:  /nda  ->  Paper (Maths / GAT / Mixed)  ->  Question count (10 / 25 / 50 / Full paper)
       ->  Negative marking ON / OFF  ->  test  ->  result (+ review of mistakes)
"""

import asyncio
import html
import logging
import time
from typing import Dict, List, Optional

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from keyboards.callbacks import NavCB, NdaCB
from services import nda_engine as engine
from services.nda_bank import NdaQuestion, bank

logger = logging.getLogger(__name__)
router = Router(name="nda_router")

LETTERS = "ABCD"
COUNT_CHOICES = (10, 25, 50)

# One active test per user. LAST keeps the finished test for "Review mistakes".
ACTIVE: Dict[int, engine.ExamSession] = {}
LAST: Dict[int, engine.ExamSession] = {}
TIMERS: Dict[int, asyncio.Task] = {}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _e(text: str) -> str:
    return html.escape(text, quote=False)


def _full_info(paper: str) -> str:
    if paper == "maths":
        return "120 Q · 150 min"
    if paper == "gat":
        return "150 Q · 150 min"
    return "270 Q · 300 min"


async def _edit(cb: types.CallbackQuery, text: str, kb: Optional[InlineKeyboardMarkup] = None) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


def _bank_line() -> str:
    counts = bank.counts()
    line = f"📚 Question bank: Maths <b>{counts['maths']}</b> · GAT <b>{counts['gat']}</b>"
    if bank.sample_count():
        line += f"\n⚠️ <i>{bank.sample_count()} demo SAMPLE questions loaded (asli PYQ add hone baaki hain)</i>"
    return line


# --------------------------------------------------------------------------- #
# Home / paper / count / negative-marking screens
# --------------------------------------------------------------------------- #
def _home_text() -> str:
    return (
        "🎖️ <b>NDA Exam Practice</b>\n"
        "Bot khud questions bhejega, end me marks denge.\n\n"
        "📐 <b>Maths</b> — 120 Q × 2.5 = 300 marks\n"
        "🧠 <b>GAT</b> — 150 Q × 4 = 600 marks\n"
        "🔀 <b>Mixed</b> — dono papers ke questions\n\n"
        f"{_bank_line()}\n\n"
        "👇 <i>Paper choose karo:</i>"
    )


def _home_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📐 Maths", callback_data=NdaCB(a="paper", v="maths").pack()))
    b.row(InlineKeyboardButton(text="🧠 GAT", callback_data=NdaCB(a="paper", v="gat").pack()))
    b.row(InlineKeyboardButton(text="🔀 Mixed (Maths + GAT)", callback_data=NdaCB(a="paper", v="mixed").pack()))
    b.row(InlineKeyboardButton(text="📊 Marking scheme", callback_data=NdaCB(a="info").pack()))
    b.row(InlineKeyboardButton(text="🏠 Main Menu", callback_data=NavCB(to="menu").pack()))
    return b.as_markup()


def _count_kb(paper: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        *[
            InlineKeyboardButton(text=f"{n} Q", callback_data=NdaCB(a="cnt", v=f"{paper}:{n}").pack())
            for n in COUNT_CHOICES
        ]
    )
    b.row(
        InlineKeyboardButton(
            text=f"📄 Full NDA paper ({_full_info(paper)})",
            callback_data=NdaCB(a="cnt", v=f"{paper}:0").pack(),
        )
    )
    b.row(InlineKeyboardButton(text="⬅️ Back", callback_data=NdaCB(a="home").pack()))
    return b.as_markup()


def _neg_kb(paper: str, count: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✅ Negative marking ON (NDA style)",
            callback_data=NdaCB(a="go", v=f"{paper}:{count}:1").pack(),
        )
    )
    b.row(
        InlineKeyboardButton(
            text="🚫 Negative marking OFF",
            callback_data=NdaCB(a="go", v=f"{paper}:{count}:0").pack(),
        )
    )
    b.row(InlineKeyboardButton(text="⬅️ Back", callback_data=NdaCB(a="paper", v=paper).pack()))
    return b.as_markup()


SCHEME_TEXT = (
    "📊 <b>NDA Marking Scheme</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "📐 <b>Maths</b>: 120 Q · sahi <b>+2.5</b> · galat <b>−0.83</b> · 300 marks · 2.5 ghante\n"
    "🧠 <b>GAT</b>: 150 Q · sahi <b>+4</b> · galat <b>−1.33</b> · 600 marks · 2.5 ghante\n"
    "   (50 English + 100 General Knowledge)\n\n"
    "• Skip kiya hua question: <b>0 marks</b>, koi penalty nahi\n"
    "• Negative marking ON/OFF test start karte waqt choose kar sakte ho\n"
    "• Custom test me time utni hi speed se milta hai jitni full paper me "
    "(Maths 1.25 min/Q, GAT 1 min/Q)"
)


@router.message(Command("nda"))
async def cmd_nda(message: types.Message) -> None:
    bank.ensure_loaded()
    await message.answer(_home_text(), reply_markup=_home_kb())


@router.callback_query(NdaCB.filter(F.a == "home"))
async def cb_home(cb: types.CallbackQuery) -> None:
    bank.ensure_loaded()
    await _edit(cb, _home_text(), _home_kb())
    await cb.answer()


@router.callback_query(NdaCB.filter(F.a == "info"))
async def cb_info(cb: types.CallbackQuery) -> None:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="⬅️ Back", callback_data=NdaCB(a="home").pack()))
    await _edit(cb, SCHEME_TEXT, b.as_markup())
    await cb.answer()


@router.callback_query(NdaCB.filter(F.a == "paper"))
async def cb_paper(cb: types.CallbackQuery, callback_data: NdaCB) -> None:
    paper = callback_data.v
    if paper not in engine.PAPER_LABEL:
        await cb.answer()
        return
    text = (
        f"{'📐' if paper == 'maths' else '🧠' if paper == 'gat' else '🔀'} "
        f"<b>{engine.PAPER_LABEL[paper]}</b>\n\n"
        "Kitne questions ka test dena hai?\n"
        f"<i>Full paper = real NDA pattern ({_full_info(paper)}).</i>"
    )
    await _edit(cb, text, _count_kb(paper))
    await cb.answer()


@router.callback_query(NdaCB.filter(F.a == "cnt"))
async def cb_count(cb: types.CallbackQuery, callback_data: NdaCB) -> None:
    try:
        paper, count_s = callback_data.v.split(":")
        count = int(count_s)
    except ValueError:
        await cb.answer()
        return
    if paper not in engine.PAPER_LABEL:
        await cb.answer()
        return
    label = "Full paper" if count == 0 else f"{count} questions"
    text = (
        f"<b>{engine.PAPER_LABEL[paper]}</b> · {label}\n\n"
        "Negative marking chahiye?\n"
        "<i>ON: galat answer pe marks kat-te hain (Maths −0.83, GAT −1.33).</i>"
    )
    await _edit(cb, text, _neg_kb(paper, count))
    await cb.answer()


# --------------------------------------------------------------------------- #
# Starting a test
# --------------------------------------------------------------------------- #
@router.callback_query(NdaCB.filter(F.a == "go"))
async def cb_go(cb: types.CallbackQuery, callback_data: NdaCB, bot: Bot) -> None:
    try:
        paper, count_s, neg_s = callback_data.v.split(":")
        count = int(count_s)
        negative = neg_s == "1"
    except ValueError:
        await cb.answer()
        return
    if paper not in engine.PAPER_LABEL:
        await cb.answer()
        return

    bank.ensure_loaded()
    plan = engine.build_plan(bank, paper, count)
    if not plan.questions:
        await cb.answer("Is paper ke questions abhi bank me nahi hain.", show_alert=True)
        return

    uid = cb.from_user.id
    _discard_active(uid)

    session = engine.new_session(uid, paper, negative, plan)
    session.chat_id = cb.message.chat.id
    session.message_id = cb.message.message_id
    ACTIVE[uid] = session
    TIMERS[uid] = asyncio.create_task(_timer_watch(bot, session))

    intro = (
        f"🚀 <b>Test shuru!</b>  {engine.PAPER_LABEL[paper]} · {session.total} Q · "
        f"⏱ {engine.format_duration(session.duration_s)} · "
        f"Negative marking {'ON' if negative else 'OFF'}"
    )
    if plan.shortage:
        intro += (
            f"\n⚠️ <i>Bank me sirf {session.total} question mile "
            f"(maange gaye: {plan.requested}).</i>"
        )
    await cb.answer("Test shuru ho gaya!")
    text, kb = _render_question(session)
    await _edit(cb, f"{intro}\n\n{text}", kb)


def _discard_active(uid: int) -> None:
    old = ACTIVE.pop(uid, None)
    if old:
        old.finished = True
    task = TIMERS.pop(uid, None)
    if task and task is not asyncio.current_task():
        task.cancel()


async def _timer_watch(bot: Bot, session: engine.ExamSession) -> None:
    try:
        await asyncio.sleep(session.remaining())
    except asyncio.CancelledError:
        return
    await finish_session(bot, session, auto=True)


# --------------------------------------------------------------------------- #
# Question screen
# --------------------------------------------------------------------------- #
def _render_question(session: engine.ExamSession) -> tuple:
    idx = session.pos
    q: NdaQuestion = session.questions[idx]
    chosen = session.answers.get(idx)

    tags = [engine.SUBJECT_LABEL[q.subject], q.section]
    header = f"<b>Q {idx + 1}/{session.total}</b> · " + " · ".join(_e(t) for t in tags if t)
    if q.is_sample:
        header += " · 🧪 SAMPLE"
    elif q.paper:
        header += f" · 📌 {_e(q.paper)}"

    status = (
        f"⏳ {engine.format_duration(session.remaining())} left · "
        f"✅ {len(session.answers)}/{session.total} answered"
    )
    options = "\n".join(f"<b>{LETTERS[i]})</b> {_e(opt)}" for i, opt in enumerate(q.options))
    text = f"{header}\n{status}\n\n{_e(q.question)}\n\n{options}"

    b = InlineKeyboardBuilder()
    b.row(
        *[
            InlineKeyboardButton(
                text=("✅ " if chosen == i else "") + LETTERS[i],
                callback_data=NdaCB(a="ans", v=f"{idx}:{i}").pack(),
            )
            for i in range(4)
        ]
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Prev", callback_data=NdaCB(a="nav", v="prev").pack()),
        InlineKeyboardButton(
            text="⏭ Skip" if chosen is None else "➡️ Next",
            callback_data=NdaCB(a="nav", v="next").pack(),
        ),
    )
    b.row(
        InlineKeyboardButton(text="🧹 Clear", callback_data=NdaCB(a="nav", v="clr").pack()),
        InlineKeyboardButton(text="🏁 Submit", callback_data=NdaCB(a="nav", v="sub").pack()),
    )
    return text, b.as_markup()


async def _get_active(cb: types.CallbackQuery, bot: Bot) -> Optional[engine.ExamSession]:
    session = ACTIVE.get(cb.from_user.id)
    if session is None or session.finished:
        await cb.answer("Ye test khatam ho chuka hai. /nda se naya shuru karo.", show_alert=True)
        return None
    if session.expired():
        await cb.answer("⏰ Time up! Test submit ho raha hai.", show_alert=True)
        await finish_session(bot, session, auto=True)
        return None
    return session


async def _show(cb: types.CallbackQuery, session: engine.ExamSession) -> None:
    text, kb = _render_question(session)
    await _edit(cb, text, kb)


@router.callback_query(NdaCB.filter(F.a == "ans"))
async def cb_answer(cb: types.CallbackQuery, callback_data: NdaCB, bot: Bot) -> None:
    session = await _get_active(cb, bot)
    if not session:
        return
    try:
        idx_s, opt_s = callback_data.v.split(":")
        idx, opt = int(idx_s), int(opt_s)
    except ValueError:
        await cb.answer()
        return
    if idx != session.pos or not (0 <= opt <= 3):
        await cb.answer()
        return

    session.answers[idx] = opt
    await cb.answer(f"Option {LETTERS[opt]} marked")
    if session.pos < session.total - 1:
        session.pos += 1
    await _show(cb, session)


@router.callback_query(NdaCB.filter(F.a == "nav"))
async def cb_nav(cb: types.CallbackQuery, callback_data: NdaCB, bot: Bot) -> None:
    session = await _get_active(cb, bot)
    if not session:
        return
    action = callback_data.v

    if action == "next":
        if session.pos < session.total - 1:
            session.pos += 1
        else:
            await cb.answer("Ye last question hai. Submit karne ke liye 🏁 dabao.")
            return
        await cb.answer()
        await _show(cb, session)

    elif action == "prev":
        if session.pos == 0:
            await cb.answer("Ye pehla question hai.")
            return
        session.pos -= 1
        await cb.answer()
        await _show(cb, session)

    elif action == "clr":
        if session.answers.pop(session.pos, None) is None:
            await cb.answer("Is question ka koi answer marked nahi hai.")
            return
        await cb.answer("Answer clear")
        await _show(cb, session)

    elif action == "sub":
        unanswered = session.total - len(session.answers)
        b = InlineKeyboardBuilder()
        b.row(
            InlineKeyboardButton(text="✅ Haan, submit", callback_data=NdaCB(a="nav", v="yes").pack()),
            InlineKeyboardButton(text="↩️ Wapas jao", callback_data=NdaCB(a="nav", v="back").pack()),
        )
        await _edit(
            cb,
            "🏁 <b>Test submit karna hai?</b>\n\n"
            f"✅ Answered: <b>{len(session.answers)}</b>\n"
            f"⏭ Unanswered: <b>{unanswered}</b>\n"
            f"⏳ Time left: <b>{engine.format_duration(session.remaining())}</b>",
            b.as_markup(),
        )
        await cb.answer()

    elif action == "back":
        await cb.answer()
        await _show(cb, session)

    elif action == "yes":
        await cb.answer("Submitted")
        await finish_session(bot, session, auto=False)

    else:
        await cb.answer()


# --------------------------------------------------------------------------- #
# Finishing, result and review
# --------------------------------------------------------------------------- #
def _format_result(session: engine.ExamSession, res: engine.ExamResult, auto: bool) -> str:
    lines = [
        "⏰ <b>Time up! Test auto-submit ho gaya</b>" if auto else "🏁 <b>Test Result</b>",
        f"📚 {engine.PAPER_LABEL[session.paper]} · {session.total} Q · "
        f"Negative marking {'ON' if session.negative else 'OFF'}",
        "━━━━━━━━━━━━━━━━━━",
        f"✅ Sahi: <b>{res.correct}</b>",
        f"❌ Galat: <b>{res.wrong}</b>",
        f"⏭ Skip: <b>{res.skipped}</b>",
        f"🎯 Accuracy: <b>{res.accuracy}%</b> (attempted me se)",
        "━━━━━━━━━━━━━━━━━━",
        f"➕ Marks mile: <b>+{res.gained:g}</b>",
        f"➖ Negative: <b>−{res.lost:g}</b>",
        f"🏆 <b>Score: {res.score:g} / {res.max_marks:g}</b>  ({res.percentage:g}%)",
        f"⏱ Time: {engine.format_duration(res.time_taken_s)} / "
        f"{engine.format_duration(session.duration_s)}",
    ]
    if len(res.per_subject) > 1:
        lines.append("━━━━━━━━━━━━━━━━━━")
        for subject, s in res.per_subject.items():
            lines.append(
                f"{'📐' if subject == 'maths' else '🧠'} {engine.SUBJECT_LABEL[subject]}: "
                f"<b>{s.score:g}/{s.max_marks:g}</b>  "
                f"(✅{s.correct} ❌{s.wrong} ⏭{s.skipped})"
            )
    if any(q.is_sample for q in session.questions):
        lines.append("\n🧪 <i>Is test me demo SAMPLE questions the, asli NDA PYQ nahi.</i>")
    return "\n".join(lines)


def _result_kb(res: engine.ExamResult) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if res.missed_indices:
        b.row(
            InlineKeyboardButton(
                text=f"📝 Review galat/skip ({len(res.missed_indices)})",
                callback_data=NdaCB(a="rev").pack(),
            )
        )
    b.row(InlineKeyboardButton(text="🔁 Naya test", callback_data=NdaCB(a="home").pack()))
    return b.as_markup()


async def finish_session(bot: Bot, session: engine.ExamSession, auto: bool = False) -> None:
    if session.finished:
        return
    session.finished = True
    session.ended_at = time.monotonic()

    uid = session.user_id
    if ACTIVE.get(uid) is session:
        del ACTIVE[uid]
    task = TIMERS.pop(uid, None)
    if task and task is not asyncio.current_task():
        task.cancel()
    LAST[uid] = session

    res = engine.compute_result(session)
    try:
        await bot.edit_message_text(
            chat_id=session.chat_id,
            message_id=session.message_id,
            text="🏁 <b>Test submit ho gaya.</b> Result neeche hai 👇",
            reply_markup=None,
        )
    except Exception:  # message may be gone/unchanged - not important
        pass
    await bot.send_message(
        session.chat_id, _format_result(session, res, auto), reply_markup=_result_kb(res)
    )


@router.callback_query(NdaCB.filter(F.a == "rev"))
async def cb_review(cb: types.CallbackQuery) -> None:
    session = LAST.get(cb.from_user.id)
    if session is None:
        await cb.answer("Review ke liye koi finished test nahi mila.", show_alert=True)
        return
    res = engine.compute_result(session)
    await cb.answer()

    MAX_ITEMS = 40
    blocks: List[str] = []
    for idx in res.missed_indices[:MAX_ITEMS]:
        q = session.questions[idx]
        chosen = session.answers.get(idx)
        options = "\n".join(f"{LETTERS[i]}) {_e(o)}" for i, o in enumerate(q.options))
        yours = "⏭ Skipped" if chosen is None else f"{LETTERS[chosen]} ❌"
        block = (
            f"<b>Q{idx + 1}.</b> {_e(q.question)}\n{options}\n"
            f"Tumhara answer: {yours} · Sahi: <b>{LETTERS[q.answer]} ✅</b>"
        )
        if q.explanation:
            block += f"\n💡 {_e(q.explanation)}"
        blocks.append(block[:3800])

    chunks: List[str] = []
    current = ""
    for block in blocks:
        if current and len(current) + len(block) + 2 > 3800:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{block}" if current else block
    if current:
        chunks.append(current)

    for n, chunk in enumerate(chunks):
        if n == 0:
            chunk = f"📝 <b>Review — galat / skip kiye hue questions</b>\n\n{chunk}"
        await cb.message.answer(chunk)
    if len(res.missed_indices) > MAX_ITEMS:
        await cb.message.answer(f"<i>(Sirf pehle {MAX_ITEMS} questions dikhaye gaye.)</i>")


# --------------------------------------------------------------------------- #
# Admin helper
# --------------------------------------------------------------------------- #
@router.message(Command("nda_bank"))
async def cmd_bank(message: types.Message) -> None:
    if not message.from_user or not settings.is_admin(message.from_user.id):
        return
    n = bank.load()  # reload from data/nda/*.json
    counts = bank.counts()
    by_year: Dict[str, int] = {}
    for q in bank.all():
        key = "SAMPLE" if q.is_sample else str(q.year or "no year")
        by_year[key] = by_year.get(key, 0) + 1
    years = "\n".join(f"• {k}: {v}" for k, v in sorted(by_year.items()))
    await message.answer(
        f"📚 <b>NDA bank reloaded</b>: {n} questions\n"
        f"Maths: {counts['maths']} · GAT: {counts['gat']}\n\n{years}"
    )
