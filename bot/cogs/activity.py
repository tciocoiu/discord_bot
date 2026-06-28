import discord
from discord import app_commands
from discord.ext import commands

from bot.db.engine import get_session_factory
from bot.services.activity import add_activity


class ActivityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="add-activity",
        description="Add activity points to boost a user's loot chance",
    )
    @app_commands.describe(
        user="The user to grant activity points",
        amount="Number of activity points to add",
        reason="Optional reason for the activity grant",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def add_activity_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 1000],
        reason: str | None = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            stats = await add_activity(
                session,
                guild_id=interaction.guild.id,
                discord_user_id=user.id,
                display_name=user.display_name,
                amount=amount,
            )

        msg = (
            f"Added **{amount}** activity point(s) to {user.mention}. "
            f"Total: **{stats.activity_points}**."
        )
        if reason:
            msg += f"\nReason: {reason}"

        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ActivityCog(bot))
