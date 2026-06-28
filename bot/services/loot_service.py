import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import Config
from bot.db.models import LootAssignment, LootSession, UserStats
from bot.services.loot_engine import LootResult, Participant, distribute_loot, parse_lines, parse_participant


async def get_or_create_stats(
    session: AsyncSession,
    guild_id: int,
    participants: list[tuple[str, str, int | None]],
) -> dict[str, UserStats]:
    keys = [p[0] for p in participants]
    result = await session.execute(
        select(UserStats).where(
            UserStats.guild_id == guild_id,
            UserStats.person_key.in_(keys),
        )
    )
    existing = {s.person_key: s for s in result.scalars().all()}

    for person_key, display_name, discord_user_id in participants:
        if person_key not in existing:
            stats = UserStats(
                guild_id=guild_id,
                person_key=person_key,
                display_name=display_name,
                discord_user_id=discord_user_id,
            )
            session.add(stats)
            existing[person_key] = stats
        else:
            stats = existing[person_key]
            stats.display_name = display_name
            if discord_user_id is not None:
                stats.discord_user_id = discord_user_id

    await session.flush()
    return existing


def build_participants(
    raw_people: list[str],
    stats_map: dict[str, UserStats],
) -> list[Participant]:
    participants: list[Participant] = []
    for raw in raw_people:
        person_key, display_name, discord_user_id = parse_participant(raw)
        stats = stats_map.get(person_key)
        participants.append(
            Participant(
                person_key=person_key,
                display_name=display_name,
                discord_user_id=discord_user_id,
                miss_streak=stats.miss_streak if stats else 0,
                activity_points=stats.activity_points if stats else 0,
            )
        )
    return participants


async def run_loot_spread(
    session: AsyncSession,
    *,
    guild_id: int,
    channel_id: int,
    created_by_id: int,
    people_text: str,
    loot_text: str,
    config: Config,
    activity_bonus: int = 0,
) -> tuple[LootSession, list[LootResult], list[Participant], list[tuple[str, int]]]:
    raw_people = parse_lines(people_text)
    loot_items = parse_lines(loot_text)
    if not raw_people:
        raise ValueError("People list cannot be empty")
    if not loot_items:
        raise ValueError("Loot list cannot be empty")

    parsed = [parse_participant(p) for p in raw_people]
    stats_map = await get_or_create_stats(session, guild_id, parsed)
    participants = build_participants(raw_people, stats_map)

    results = distribute_loot(participants, loot_items, config)

    winners = {r.person_key for r in results}
    for p in participants:
        stats = stats_map[p.person_key]
        if p.person_key in winners:
            stats.loot_count += sum(1 for r in results if r.person_key == p.person_key)
            stats.miss_streak = 0
        else:
            stats.miss_streak += 1

    loot_session = LootSession(
        guild_id=guild_id,
        channel_id=channel_id,
        created_by_id=created_by_id,
        people_json=json.dumps(raw_people),
        loot_json=json.dumps(loot_items),
    )
    session.add(loot_session)
    await session.flush()

    for result in results:
        session.add(
            LootAssignment(
                session_id=loot_session.id,
                person_key=result.person_key,
                display_name=result.display_name,
                discord_user_id=result.discord_user_id,
                loot_item=result.loot_item,
            )
        )

    activity_grants: list[tuple[str, int]] = []
    if activity_bonus > 0:
        seen_keys: set[str] = set()
        for result in results:
            if result.person_key in seen_keys:
                continue
            seen_keys.add(result.person_key)
            stats_map[result.person_key].activity_points += activity_bonus
            activity_grants.append((result.display_name, activity_bonus))

    await session.commit()
    await session.refresh(loot_session)
    return loot_session, results, participants, activity_grants


def format_results_embed_data(results: list[LootResult], participants: list[Participant]) -> tuple[str, str]:
    by_person: dict[str, list[str]] = defaultdict(list)
    for r in results:
        by_person[r.display_name].append(r.loot_item)

    lines = []
    for name, items in sorted(by_person.items()):
        lines.append(f"**{name}**: {', '.join(items)}")

    winner_keys = {r.person_key for r in results}
    empty = [p.display_name for p in participants if p.person_key not in winner_keys]
    empty_line = ", ".join(empty) if empty else "None"

    return "\n".join(lines), empty_line


async def fetch_loot_logs(
    session: AsyncSession,
    *,
    guild_id: int,
    limit: int = 10,
    user_id: int | None = None,
) -> list[LootSession]:
    query = (
        select(LootSession)
        .where(LootSession.guild_id == guild_id)
        .options(selectinload(LootSession.assignments))
        .order_by(LootSession.created_at.desc())
        .limit(limit)
    )

    if user_id is not None:
        person_key = str(user_id)
        query = query.where(
            exists().where(
                LootAssignment.session_id == LootSession.id,
                LootAssignment.person_key == person_key,
            )
        )

    result = await session.execute(query)
    return list(result.scalars().unique().all())


async def fetch_loot_assignments_past_week(
    session: AsyncSession,
    *,
    guild_id: int,
    days: int = 7,
) -> list[tuple[LootAssignment, LootSession]]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(LootAssignment, LootSession)
        .join(LootSession, LootAssignment.session_id == LootSession.id)
        .where(
            LootSession.guild_id == guild_id,
            LootSession.created_at >= since,
        )
        .order_by(LootSession.created_at.desc(), LootAssignment.id.desc())
    )
    return list(result.all())


def format_weekly_loot_log(rows: list[tuple[LootAssignment, LootSession]]) -> str:
    by_person: dict[str, list[str]] = defaultdict(list)
    for assignment, _session in rows:
        by_person[assignment.display_name].append(assignment.loot_item)

    lines = []
    for name, items in sorted(by_person.items()):
        lines.append(f"**{name}**: {', '.join(items)}")
    return "\n".join(lines)
