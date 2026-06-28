from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class LootSession(Base):
    __tablename__ = "loot_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    created_by_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    people_json: Mapped[str] = mapped_column(Text)
    loot_json: Mapped[str] = mapped_column(Text)

    assignments: Mapped[list["LootAssignment"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class LootAssignment(Base):
    __tablename__ = "loot_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("loot_sessions.id", ondelete="CASCADE"), index=True)
    person_key: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    discord_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    loot_item: Mapped[str] = mapped_column(String(500))

    session: Mapped["LootSession"] = relationship(back_populates="assignments")


class UserStats(Base):
    __tablename__ = "user_stats"
    __table_args__ = (UniqueConstraint("guild_id", "person_key", name="uq_guild_person"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    person_key: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), default="")
    discord_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    loot_count: Mapped[int] = mapped_column(Integer, default=0)
    miss_streak: Mapped[int] = mapped_column(Integer, default=0)
    activity_points: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
