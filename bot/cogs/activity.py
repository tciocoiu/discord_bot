import discord
from discord import app_commands
from discord.ext import commands

from bot.db.engine import get_session_factory
from bot.services.activity import add_activity, fetch_guild_activity, format_member_name, wipe_guild_activity


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

    @app_commands.command(
        name="show-activity",
        description="Show activity points for all tracked members",
    )
    async def show_activity(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            members = await fetch_guild_activity(session, guild_id=interaction.guild.id)

        if not members:
            await interaction.response.send_message(
                "No activity data yet. Use `/add-activity` or run a loot spread with members.",
                ephemeral=True,
            )
            return

        lines = [
            f"**{format_member_name(m)}**: {m.activity_points} point(s)"
            for m in members
        ]
        body = "\n".join(lines)

        embed = discord.Embed(
            title="Activity Points",
            description=body[:4096],
            color=discord.Color.green(),
        )
        if len(body) > 4096:
            embed.set_footer(text="List truncated — too many members to show fully.")
        else:
            embed.set_footer(text=f"{len(members)} member(s) tracked")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="wipe",
        description="Reset all activity points and bad-luck streaks (server owner only)",
    )
    async def wipe(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the **server owner** can use this command.",
                ephemeral=True,
            )
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            count = await wipe_guild_activity(session, guild_id=interaction.guild.id)

        await interaction.response.send_message(
            f"Wiped activity for **{count}** tracked member(s). "
            "Loot history (`/show-logs`) is unchanged.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ActivityCog(bot))
