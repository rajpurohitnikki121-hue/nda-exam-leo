"""Remembers which NDA questions each user has already seen (stored in the database)."""

import logging
from typing import Iterable, Set

from sqlalchemy import delete, select

from database.connection import get_db
from database.models import NdaSeen

logger = logging.getLogger(__name__)


async def get_seen(user_id: int) -> Set[str]:
    try:
        async with get_db() as session:
            rows = await session.execute(select(NdaSeen.qid).where(NdaSeen.user_id == user_id))
            return set(rows.scalars().all())
    except Exception:
        logger.exception("could not read seen questions")
        return set()


async def mark_seen(user_id: int, qids: Iterable[str]) -> None:
    qids = list(dict.fromkeys(qids))
    if not qids:
        return
    try:
        async with get_db() as session:
            rows = await session.execute(
                select(NdaSeen.qid).where(NdaSeen.user_id == user_id, NdaSeen.qid.in_(qids))
            )
            existing = set(rows.scalars().all())
            session.add_all([NdaSeen(user_id=user_id, qid=q) for q in qids if q not in existing])
    except Exception:
        logger.exception("could not save seen questions")


async def reset(user_id: int) -> int:
    async with get_db() as session:
        result = await session.execute(delete(NdaSeen).where(NdaSeen.user_id == user_id))
        return result.rowcount or 0
