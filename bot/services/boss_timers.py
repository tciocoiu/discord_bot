import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db.engine import get_session_factory
from bot.db.models import BossDefinition, BossPanel, BossTimer, GuildSettings

logger = logging.getLogger(__name__)

RESPAWN_HOURS = 4
WARNING_MINUTES = 10
MAX_BOSSES_PER_PANEL = 25

_scheduled_tasks: dict[int, asyncio.Task] = {}


@dataclass(frozen=True)
class BossStatus:
    boss: BossDefinition
    is_ready: bool
    respawn_at: datetime | None
    remaining: timedelta | None


def boss_button_custom_id(guild_id: int, boss_id: int) -> str:
    return f"boss_timer:{guild_id}:{boss_id}"


def parse_boss_button_custom_id(custom_id: str) -> tuple[int, int] | None:
    if not custom_id.startswith("boss_timer:"):
        return None
    parts = custom_id.split(":")
    if len(parts) != 3:
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


def format_remaining(remaining: timedelta) -> str:
    total_seconds = int(remaining.total_seconds())
    if total_seconds <= 0:
        return "Ready"
    hours, rem = divmod(total_seconds, 3600)
    minutes, _ = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


async def get_guild_settings(session: AsyncSession, guild_id: int) -> GuildSettings | None:
    result = await session.execute(
        select(GuildSettings).where(GuildSettings.guild_id == guild_id)
    )
    return result.scalar_one_or_none()


async def set_alert_channel(session: AsyncSession, guild_id: int, channel_id: int) -> GuildSettings:
    settings = await get_guild_settings(session, guild_id)
    if settings is None:
        settings = GuildSettings(guild_id=guild_id, alert_channel_id=channel_id)
        session.add(settings)
    else:
        settings.alert_channel_id = channel_id
    await session.commit()
    await session.refresh(settings)
    return settings


async def add_boss(session: AsyncSession, guild_id: int, name: str) -> BossDefinition:
    name = name.strip()
    if not name:
        raise ValueError("Boss name cannot be empty")

    existing = await session.execute(
        select(BossDefinition).where(
            BossDefinition.guild_id == guild_id,
            BossDefinition.name == name,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Boss **{name}** already exists")

    count = await session.execute(
        select(BossDefinition).where(BossDefinition.guild_id == guild_id)
    )
    if len(list(count.scalars().all())) >= MAX_BOSSES_PER_PANEL:
        raise ValueError(f"Maximum {MAX_BOSSES_PER_PANEL} bosses per server")

    boss = BossDefinition(guild_id=guild_id, name=name)
    session.add(boss)
    await session.commit()
    await session.refresh(boss)
    return boss


async def remove_boss(session: AsyncSession, guild_id: int, name: str) -> str:
    name = name.strip()
    result = await session.execute(
        select(BossDefinition).where(
            BossDefinition.guild_id == guild_id,
            BossDefinition.name == name,
        )
    )
    boss = result.scalar_one_or_none()
    if boss is None:
        raise ValueError(f"Boss **{name}** not found")

    removed_name = boss.name
    await session.delete(boss)
    await session.commit()
    return removed_name


async def list_bosses(session: AsyncSession, guild_id: int) -> list[BossDefinition]:
    result = await session.execute(
        select(BossDefinition)
        .where(BossDefinition.guild_id == guild_id)
        .options(selectinload(BossDefinition.timer))
        .order_by(BossDefinition.name.asc())
    )
    return list(result.scalars().all())


async def get_boss_by_id(session: AsyncSession, boss_id: int) -> BossDefinition | None:
    result = await session.execute(
        select(BossDefinition)
        .where(BossDefinition.id == boss_id)
        .options(selectinload(BossDefinition.timer))
    )
    return result.scalar_one_or_none()


def compute_boss_status(boss: BossDefinition, now: datetime | None = None) -> BossStatus:
    now = now or datetime.now(timezone.utc)
    timer = boss.timer
    if timer is None or timer.respawn_at <= now:
        return BossStatus(boss=boss, is_ready=True, respawn_at=None, remaining=None)
    remaining = timer.respawn_at - now
    return BossStatus(boss=boss, is_ready=False, respawn_at=timer.respawn_at, remaining=remaining)


async def start_timer(
    session: AsyncSession,
    *,
    guild_id: int,
    boss_id: int,
    started_by_id: int,
) -> BossTimer:
    boss = await get_boss_by_id(session, boss_id)
    if boss is None or boss.guild_id != guild_id:
        raise ValueError("Boss not found")

    now = datetime.now(timezone.utc)
    respawn_at = now + timedelta(hours=RESPAWN_HOURS)

    if boss.timer is not None:
        boss.timer.started_by_id = started_by_id
        boss.timer.started_at = now
        boss.timer.respawn_at = respawn_at
        timer = boss.timer
    else:
        timer = BossTimer(
            guild_id=guild_id,
            boss_id=boss_id,
            started_by_id=started_by_id,
            started_at=now,
            respawn_at=respawn_at,
        )
        session.add(timer)

    await session.commit()
    await session.refresh(timer)
    return timer


async def save_panel(
    session: AsyncSession,
    *,
    guild_id: int,
    channel_id: int,
    message_id: int,
) -> None:
    result = await session.execute(
        select(BossPanel).where(BossPanel.guild_id == guild_id)
    )
    panel = result.scalar_one_or_none()
    if panel is None:
        panel = BossPanel(guild_id=guild_id, channel_id=channel_id, message_id=message_id)
        session.add(panel)
    else:
        panel.channel_id = channel_id
        panel.message_id = message_id
    await session.commit()


async def get_panel(session: AsyncSession, guild_id: int) -> BossPanel | None:
    result = await session.execute(
        select(BossPanel).where(BossPanel.guild_id == guild_id)
    )
    return result.scalar_one_or_none()


async def get_all_panels(session: AsyncSession) -> list[BossPanel]:
    result = await session.execute(select(BossPanel))
    return list(result.scalars().all())


def build_panel_embed(guild: discord.Guild, bosses: list[BossDefinition]) -> discord.Embed:
    now = datetime.now(timezone.utc)
    embed = discord.Embed(
        title="Boss Timers",
        description="Click a boss button when it is killed to start a 4-hour respawn timer.",
        color=discord.Color.dark_red(),
    )

    if not bosses:
        embed.add_field(name="No bosses", value="An admin can add bosses with `/add-boss`.", inline=False)
        return embed

    lines = []
    for boss in bosses:
        status = compute_boss_status(boss, now)
        if status.is_ready:
            lines.append(f"**{boss.name}** — Ready")
        elif status.respawn_at:
            ts = int(status.respawn_at.timestamp())
            lines.append(f"**{boss.name}** — <t:{ts}:R> (<t:{ts}:t>)")

    embed.add_field(name="Status", value="\n".join(lines)[:1024], inline=False)
    return embed


def build_panel_view(bot: discord.Client, guild_id: int, bosses: list[BossDefinition]) -> discord.ui.View:
    view = BossPanelView(bot, guild_id)
    now = datetime.now(timezone.utc)

    for boss in bosses[:MAX_BOSSES_PER_PANEL]:
        status = compute_boss_status(boss, now)
        if status.is_ready:
            label = f"{boss.name} — Ready"
            style = discord.ButtonStyle.success
        else:
            label = f"{boss.name} — {format_remaining(status.remaining or timedelta())}"
            style = discord.ButtonStyle.secondary

        view.add_item(
            BossTimerButton(
                bot=bot,
                guild_id=guild_id,
                boss_id=boss.id,
                boss_name=boss.name,
                label=label[:80],
                style=style,
            )
        )
    return view


class BossTimerButton(discord.ui.Button):
    def __init__(
        self,
        *,
        bot: discord.Client,
        guild_id: int,
        boss_id: int,
        boss_name: str,
        label: str,
        style: discord.ButtonStyle,
    ):
        super().__init__(
            label=label,
            style=style,
            custom_id=boss_button_custom_id(guild_id, boss_id),
        )
        self._bot = bot
        self._guild_id = guild_id
        self._boss_id = boss_id
        self._boss_name = boss_name

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.guild.id != self._guild_id:
            await interaction.response.send_message(
                "This button is not valid in this server.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            boss = await get_boss_by_id(session, self._boss_id)
            if boss is None:
                await interaction.response.send_message("Boss not found.", ephemeral=True)
                return

            timer = await start_timer(
                session,
                guild_id=self._guild_id,
                boss_id=self._boss_id,
                started_by_id=interaction.user.id,
            )
            timer_id = timer.id

        schedule_alerts(self._bot, timer_id)
        await refresh_panel(self._bot, self._guild_id)

        await interaction.response.send_message(
            f"Started 4-hour timer for **{self._boss_name}**.",
            ephemeral=True,
        )


class BossPanelView(discord.ui.View):
    def __init__(self, bot: discord.Client, guild_id: int):
        super().__init__(timeout=None)
        self._bot = bot
        self._guild_id = guild_id


def _cancel_timer_tasks(timer_id: int) -> None:
    task = _scheduled_tasks.pop(timer_id, None)
    if task and not task.done():
        task.cancel()


async def _send_alert(bot: discord.Client, channel_id: int, content: str) -> None:
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            logger.warning("Could not fetch alert channel %s", channel_id)
            return
    if isinstance(channel, discord.abc.Messageable):
        await channel.send(content)


async def _get_timer(session: AsyncSession, timer_id: int) -> BossTimer | None:
    result = await session.execute(
        select(BossTimer)
        .where(BossTimer.id == timer_id)
        .options(selectinload(BossTimer.boss))
    )
    return result.scalar_one_or_none()


async def refresh_panel(bot: discord.Client, guild_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        panel = await get_panel(session, guild_id)
        if panel is None:
            return
        bosses = await list_bosses(session, guild_id)

    guild = bot.get_guild(guild_id)
    if guild is None:
        return

    channel = bot.get_channel(panel.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(panel.channel_id)
        except discord.HTTPException:
            return

    if not isinstance(channel, discord.TextChannel):
        return

    try:
        message = await channel.fetch_message(panel.message_id)
    except discord.HTTPException:
        logger.warning("Could not fetch boss panel message for guild %s", guild_id)
        return

    embed = build_panel_embed(guild, bosses)
    view = build_panel_view(bot, guild_id, bosses)
    bot.add_view(view)
    try:
        await message.edit(embed=embed, view=view)
    except discord.HTTPException as exc:
        logger.warning("Could not edit boss panel for guild %s: %s", guild_id, exc)


async def _alert_worker(bot: discord.Client, timer_id: int) -> None:
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            timer = await _get_timer(session, timer_id)
            if timer is None:
                return
            settings = await get_guild_settings(session, timer.guild_id)
            boss_name = timer.boss.name
            guild_id = timer.guild_id
            alert_channel_id = settings.alert_channel_id if settings else None
            respawn_at = timer.respawn_at

        now = datetime.now(timezone.utc)
        warn_at = respawn_at - timedelta(minutes=WARNING_MINUTES)

        if warn_at > now:
            await asyncio.sleep((warn_at - now).total_seconds())
            async with session_factory() as session:
                timer = await _get_timer(session, timer_id)
                if timer is None or timer.respawn_at != respawn_at:
                    return
            if alert_channel_id:
                await _send_alert(
                    bot,
                    alert_channel_id,
                    f"⏰ **{boss_name}** respawns in {WARNING_MINUTES} minutes!",
                )

        now = datetime.now(timezone.utc)
        if respawn_at > now:
            await asyncio.sleep((respawn_at - now).total_seconds())

        async with session_factory() as session:
            timer = await _get_timer(session, timer_id)
            if timer is None or timer.respawn_at != respawn_at:
                return

        if alert_channel_id:
            await _send_alert(bot, alert_channel_id, f"✅ **{boss_name}** is up now!")

        await refresh_panel(bot, guild_id)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Boss timer alert worker failed for timer %s", timer_id)
    finally:
        _scheduled_tasks.pop(timer_id, None)


def schedule_alerts(bot: discord.Client, timer_id: int) -> None:
    _cancel_timer_tasks(timer_id)
    _scheduled_tasks[timer_id] = asyncio.create_task(_alert_worker(bot, timer_id))


async def restore_timers_on_startup(bot: discord.Client) -> None:
    session_factory = get_session_factory()
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        result = await session.execute(
            select(BossTimer)
            .where(BossTimer.respawn_at > now)
            .options(selectinload(BossTimer.boss))
        )
        active_timers = list(result.scalars().all())
        panels = await get_all_panels(session)
        guild_ids = {panel.guild_id for panel in panels}

    for timer in active_timers:
        schedule_alerts(bot, timer.id)

    for guild_id in guild_ids:
        await refresh_panel(bot, guild_id)

    logger.info(
        "Restored %s boss timer(s) and %s panel view(s)",
        len(active_timers),
        len(guild_ids),
    )
