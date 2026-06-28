from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import UserStats


async def add_activity(
    session: AsyncSession,
    *,
    guild_id: int,
    discord_user_id: int,
    display_name: str,
    amount: int,
) -> UserStats:
    person_key = str(discord_user_id)
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
        stats.discord_user_id = discord_user_id
        stats.activity_points += amount

    await session.commit()
    await session.refresh(stats)
    return stats
