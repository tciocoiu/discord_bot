import json

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import LootAssignment, LootSession, UserStats
from bot.services.loot_engine import parse_lines, parse_participant
from bot.services.loot_service import get_or_create_stats


async def add_activity_points(
    session: AsyncSession,
    *,
    guild_id: int,
    person_key: str,
    display_name: str,
    discord_user_id: int | None,
    amount: int,
) -> UserStats:
    result = await session.execute(
        select(UserStats).where(
            UserStats.guild_id == guild_id,
            UserStats.person_key == person_key,
        )
    )
    stats = result.scalar_one_or_none()
    if stats is None:
        stats = UserStats(
            guild_id=guild_id,
            person_key=person_key,
            display_name=display_name,
            discord_user_id=discord_user_id,
            activity_points=amount,
        )
        session.add(stats)
    else:
        stats.display_name = display_name
        if discord_user_id is not None:
            stats.discord_user_id = discord_user_id
        stats.activity_points += amount

    await session.flush()
    return stats


async def run_activity_grant(
    session: AsyncSession,
    *,
    guild_id: int,
    channel_id: int,
    created_by_id: int,
    people_text: str,
    amount: int,
    reason: str = "",
) -> tuple[LootSession, list[tuple[str, int, int]]]:
    raw_people = parse_lines(people_text)
    if not raw_people:
        raise ValueError("People list cannot be empty")
    if not 1 <= amount <= 1000:
        raise ValueError("Activity points must be between 1 and 1000")

    parsed = [parse_participant(p) for p in raw_people]
    await get_or_create_stats(session, guild_id, parsed)

    grants: list[tuple[str, str, int | None, int, int]] = []
    for person_key, display_name, discord_user_id in parsed:
        stats = await add_activity_points(
            session,
            guild_id=guild_id,
            person_key=person_key,
            display_name=display_name,
            discord_user_id=discord_user_id,
            amount=amount,
        )
        grants.append((person_key, display_name, discord_user_id, amount, stats.activity_points))

    loot_session = LootSession(
        guild_id=guild_id,
        channel_id=channel_id,
        created_by_id=created_by_id,
        people_json=json.dumps(raw_people),
        loot_json=json.dumps(
            {
                "kind": "activity",
                "amount": amount,
                "reason": reason,
            }
        ),
    )
    session.add(loot_session)
    await session.flush()

    for person_key, display_name, discord_user_id, grant_amount, _total in grants:
        session.add(
            LootAssignment(
                session_id=loot_session.id,
                person_key=person_key,
                display_name=display_name,
                discord_user_id=discord_user_id,
                loot_item=f"+{grant_amount} activity",
            )
        )

    await session.commit()
    await session.refresh(loot_session)

    summary = [(display_name, grant_amount, total) for _, display_name, _, grant_amount, total in grants]
    return loot_session, summary


async def fetch_guild_activity(
    session: AsyncSession,
    *,
    guild_id: int,
) -> list[UserStats]:
    result = await session.execute(
        select(UserStats)
        .where(UserStats.guild_id == guild_id)
        .order_by(UserStats.activity_points.desc(), UserStats.display_name.asc())
    )
    return list(result.scalars().all())


def format_member_name(stats: UserStats) -> str:
    if stats.discord_user_id is not None:
        return f"<@{stats.discord_user_id}>"
    return stats.display_name


async def wipe_guild_activity(session: AsyncSession, *, guild_id: int) -> int:
    """Reset activity points and miss streaks. Loot history is unchanged."""
    result = await session.execute(
        update(UserStats)
        .where(UserStats.guild_id == guild_id)
        .values(activity_points=0, miss_streak=0)
    )
    await session.commit()
    return result.rowcount or 0
