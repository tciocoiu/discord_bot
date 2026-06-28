import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.db.engine import get_session_factory
from bot.services import boss_timers

logger = logging.getLogger(__name__)


class BossesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_load(self) -> None:
        self.panel_refresh_loop.start()

    def cog_unload(self) -> None:
        self.panel_refresh_loop.cancel()

    @tasks.loop(seconds=1)
    async def panel_refresh_loop(self) -> None:
        try:
            await boss_timers.refresh_panels_with_active_timers(self.bot)
        except Exception:
            logger.exception("Boss panel refresh loop failed")

    @panel_refresh_loop.before_loop
    async def before_panel_refresh_loop(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="list-bosses", description="Show all bosses and their timer status")
    async def list_bosses(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            bosses = await boss_timers.list_bosses(session, interaction.guild.id)

        embed = boss_timers.build_boss_list_embed(bosses)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="set-boss-alerts", description="Set the channel for boss timer alerts")
    @app_commands.describe(channel="Channel for 10-minute warnings and boss-up messages")
    @app_commands.default_permissions(manage_guild=True)
    async def set_boss_alerts(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            await boss_timers.set_alert_channel(session, interaction.guild.id, channel.id)

        await interaction.response.send_message(
            f"Boss alerts will be posted in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="add-boss", description="Add a boss to the timer panel")
    @app_commands.describe(name="Boss name")
    @app_commands.default_permissions(manage_guild=True)
    async def add_boss_cmd(self, interaction: discord.Interaction, name: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            try:
                boss = await boss_timers.add_boss(session, interaction.guild.id, name)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

        await boss_timers.refresh_panel(self.bot, interaction.guild.id)
        await interaction.response.send_message(
            f"Added boss **{boss.name}**. Run `/boss-panel` if you need a new panel.",
            ephemeral=True,
        )

    @app_commands.command(name="remove-boss", description="Remove a boss from the timer panel")
    @app_commands.describe(name="Boss name")
    @app_commands.default_permissions(manage_guild=True)
    async def remove_boss_cmd(self, interaction: discord.Interaction, name: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            try:
                removed = await boss_timers.remove_boss(session, interaction.guild.id, name)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

        await boss_timers.refresh_panel(self.bot, interaction.guild.id)
        await interaction.response.send_message(
            f"Removed boss **{removed}**.",
            ephemeral=True,
        )

    @app_commands.command(name="boss-panel", description="Post or refresh the boss timer button panel")
    @app_commands.default_permissions(manage_guild=True)
    async def boss_panel(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "This command must be used in a text channel.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            bosses = await boss_timers.list_bosses(session, interaction.guild.id)

        embed = boss_timers.build_panel_embed(interaction.guild, bosses)
        view = boss_timers.build_panel_view(self.bot, interaction.guild.id, bosses)
        self.bot.add_view(view)

        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()

        async with session_factory() as session:
            await boss_timers.save_panel(
                session,
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                message_id=message.id,
            )

        await interaction.followup.send(
            "Boss panel posted. Click a button when a boss is killed to start the 4h timer.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BossesCog(bot))
