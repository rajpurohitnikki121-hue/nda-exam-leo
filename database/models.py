import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_exam: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    attempts: Mapped[List["UserAttempt"]] = relationship(
        "UserAttempt", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.user_id}, username={self.username})>"


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., SSC, Banking, Railways

    subjects: Mapped[List["Subject"]] = relationship(
        "Subject", back_populates="exam", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Exam(code={self.code}, name={self.name})>"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="subjects")
    chapters: Mapped[List["Chapter"]] = relationship(
        "Chapter", back_populates="subject", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Subject(id={self.id}, name={self.name})>"


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)

    subject: Mapped["Subject"] = relationship("Subject", back_populates="chapters")
    sub_types: Mapped[List["SubType"]] = relationship(
        "SubType", back_populates="chapter", cascade="all, delete-orphan"
    )
    questions: Mapped[List["Question"]] = relationship(
        "Question", back_populates="chapter", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Chapter(id={self.id}, name={self.name})>"


class SubType(Base):
    __tablename__ = "sub_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)

    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="sub_types")
    questions: Mapped[List["Question"]] = relationship(
        "Question", back_populates="sub_type"
    )

    def __repr__(self) -> str:
        return f"<SubType(id={self.id}, name={self.name})>"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sub_type_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sub_types.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options_raw: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string of list of 4 options
    correct_option_id: Mapped[int] = mapped_column(Integer, nullable=False)  # 0, 1, 2, 3
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    shortcut_trick: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="Medium")  # Easy, Medium, Hard

    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="questions")
    sub_type: Mapped[Optional["SubType"]] = relationship("SubType", back_populates="questions")
    attempts: Mapped[List["UserAttempt"]] = relationship(
        "UserAttempt", back_populates="question", cascade="all, delete-orphan"
    )
    channel_polls: Mapped[List["ChannelPoll"]] = relationship(
        "ChannelPoll", back_populates="question", cascade="all, delete-orphan"
    )

    @property
    def options(self) -> List[str]:
        try:
            return json.loads(self.options_raw)
        except Exception:
            return []

    @options.setter
    def options(self, val: List[str]) -> None:
        self.options_raw = json.dumps(val, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<Question(id={self.id}, difficulty={self.difficulty})>"


class UserAttempt(Base):
    __tablename__ = "user_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected_option: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    time_taken: Mapped[float] = mapped_column(Float, default=0.0)  # seconds
    attempt_type: Mapped[str] = mapped_column(String(50), default="DM_PRACTICE")  # DM_PRACTICE, DM_TIMED, CHANNEL_POLL
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now(), index=True
    )

    user: Mapped["User"] = relationship("User", back_populates="attempts")
    question: Mapped["Question"] = relationship("Question", back_populates="attempts")

    def __repr__(self) -> str:
        return f"<UserAttempt(user={self.user_id}, q={self.question_id}, correct={self.is_correct})>"


class NdaSeen(Base):
    """Questions a user has already been shown in NDA tests (so new tests give fresh ones)."""

    __tablename__ = "nda_seen"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    qid: Mapped[str] = mapped_column(String(100), primary_key=True, autoincrement=False)
    seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChannelPoll(Base):
    __tablename__ = "channel_polls"

    poll_id: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now()
    )

    question: Mapped["Question"] = relationship("Question", back_populates="channel_polls")

    def __repr__(self) -> str:
        return f"<ChannelPoll(poll_id={self.poll_id}, q={self.question_id})>"
