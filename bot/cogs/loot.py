import discord
from discord import app_commands
from discord.ext import commands

from bot.config import Config
from bot.db.engine import get_session_factory
from bot.services.loot_service import (
    fetch_loot_assignments_past_week,
    fetch_loot_logs,
    format_results_embed_data,
    format_weekly_loot_log,
    run_loot_spread,
)


class SpreadLootModal(discord.ui.Modal, title="Spread Loot"):
    people_input = discord.ui.TextInput(
        label="People (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="Alice\n@Bob\nCharlie",
        required=True,
        max_length=4000,
    )
    loot_input = discord.ui.TextInput(
        label="Loot (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="Sword of Truth\n500 gold\nRare gem",
        required=True,
        max_length=4000,
    )
    activity_input = discord.ui.TextInput(
        label="Activity points per winner (optional)",
        style=discord.TextStyle.short,
        placeholder="5",
        required=False,
        max_length=4,
    )
    reason_input = discord.ui.TextInput(
        label="Reason (optional)",
        style=discord.TextStyle.short,
        placeholder="Weekly raid",
        required=False,
        max_length=200,
    )

    def __init__(self, config: Config):
        super().__init__()
        self.config = config

    def _parse_activity_bonus(self) -> int | None:
        raw = str(self.activity_input.value or "").strip()
        if not raw:
            return 0
        try:
            amount = int(raw)
        except ValueError:
            return None
        if not 1 <= amount <= 1000:
            return None
        return amount

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        people_text = str(self.people_input.value)
        loot_text = str(self.loot_input.value)
        activity_bonus = self._parse_activity_bonus()
        if activity_bonus is None:
            await interaction.followup.send(
                "Activity points must be a whole number between 1 and 1000, or leave blank.",
                ephemeral=True,
            )
            return

        reason = str(self.reason_input.value or "").strip()

        if interaction.guild is None:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            try:
                loot_session, results, participants, activity_grants = await run_loot_spread(
                    session,
                    guild_id=interaction.guild.id,
                    channel_id=interaction.channel.id if interaction.channel else 0,
                    created_by_id=interaction.user.id,
                    people_text=people_text,
                    loot_text=loot_text,
                    config=self.config,
                    activity_bonus=activity_bonus,
                )
            except ValueError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return

        distribution, empty = format_results_embed_data(results, participants)

        embed = discord.Embed(
            title="Loot Spread Results",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Distribution", value=distribution[:1024] or "None", inline=False)
        embed.add_field(name="No loot this round", value=empty[:1024], inline=False)

        if activity_grants:
            grant_lines = [f"**{name}**: +{pts}" for name, pts in activity_grants]
            activity_value = "\n".join(grant_lines)
            if reason:
                activity_value += f"\n*Reason:* {reason}"
            embed.add_field(name="Activity granted", value=activity_value[:1024], inline=False)

        embed.set_footer(text=f"Session #{loot_session.id}")

        await interaction.followup.send(embed=embed)


class LootCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

    @app_commands.command(name="spread-loot", description="Spread loot among people using weighted random")
    async def spread_loot(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(SpreadLootModal(self.config))

    @app_commands.command(name="log", description="View recent loot spread history")
    @app_commands.describe(
        limit="Number of sessions to show (max 25)",
        user="Filter to sessions where this user received loot",
    )
    async def log(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 25] = 10,
        user: discord.Member | None = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as db_session:
            sessions = await fetch_loot_logs(
                db_session,
                guild_id=interaction.guild.id,
                limit=limit,
                user_id=user.id if user else None,
            )

        if not sessions:
            await interaction.response.send_message("No loot sessions found.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Loot Spread Log",
            color=discord.Color.blue(),
        )

        for loot_session in sessions:
            summary_parts = []
            for assignment in loot_session.assignments:
                summary_parts.append(f"{assignment.display_name}: {assignment.loot_item}")
            summary = "\n".join(summary_parts[:5])
            if len(loot_session.assignments) > 5:
                summary += f"\n... +{len(loot_session.assignments) - 5} more"

            timestamp = loot_session.created_at.strftime("%Y-%m-%d %H:%M UTC") if loot_session.created_at else "?"
            embed.add_field(
                name=f"Session #{loot_session.id} — {timestamp}",
                value=summary[:1024] or "No assignments",
                inline=False,
            )

        filter_note = f" (filtered: {user.display_name})" if user else ""
        embed.set_footer(text=f"Showing {len(sessions)} session(s){filter_note}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="show-logs",
        description="Show all loot distributed in the past 7 days",
    )
    async def show_logs(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as db_session:
            rows = await fetch_loot_assignments_past_week(
                db_session,
                guild_id=interaction.guild.id,
            )

        if not rows:
            await interaction.response.send_message(
                "No loot was distributed in the past 7 days.",
                ephemeral=True,
            )
            return

        body = format_weekly_loot_log(rows)
        total_items = len(rows)
        unique_sessions = len({session.id for _assignment, session in rows})

        embed = discord.Embed(
            title="Loot Log — Past 7 Days",
            description=body[:4096] or "None",
            color=discord.Color.purple(),
        )
        footer = f"{total_items} item(s) across {unique_sessions} session(s)"
        if len(body) > 4096:
            footer += " — list truncated"
        embed.set_footer(text=footer)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot, config: Config) -> None:
    await bot.add_cog(LootCog(bot, config))
