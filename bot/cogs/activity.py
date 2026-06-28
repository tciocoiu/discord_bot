import discord
from discord import app_commands
from discord.ext import commands

from bot.db.engine import get_session_factory
from bot.services.activity import fetch_guild_activity, format_member_name, run_activity_grant, wipe_guild_activity


class AddActivityModal(discord.ui.Modal, title="Add Activity"):
    people_input = discord.ui.TextInput(
        label="People (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="Bay\nVerm\n@Forest",
        required=True,
        max_length=4000,
    )
    amount_input = discord.ui.TextInput(
        label="Activity points per person",
        style=discord.TextStyle.short,
        placeholder="5",
        required=True,
        max_length=4,
    )
    reason_input = discord.ui.TextInput(
        label="Reason (optional)",
        style=discord.TextStyle.short,
        placeholder="Weekly raid",
        required=False,
        max_length=200,
    )

    def _parse_amount(self) -> int | None:
        raw = str(self.amount_input.value or "").strip()
        try:
            amount = int(raw)
        except ValueError:
            return None
        if not 1 <= amount <= 1000:
            return None
        return amount

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        amount = self._parse_amount()
        if amount is None:
            await interaction.followup.send(
                "Activity points must be a whole number between 1 and 1000.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
            await interaction.followup.send(
                "You need **Manage Server** to grant activity points.",
                ephemeral=True,
            )
            return

        people_text = str(self.people_input.value)
        reason = str(self.reason_input.value or "").strip()

        session_factory = get_session_factory()
        async with session_factory() as session:
            try:
                activity_session, grants = await run_activity_grant(
                    session,
                    guild_id=interaction.guild.id,
                    channel_id=interaction.channel.id if interaction.channel else 0,
                    created_by_id=interaction.user.id,
                    people_text=people_text,
                    amount=amount,
                    reason=reason,
                )
            except ValueError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return

        lines = [f"**{name}**: +{pts} (total **{total}**)" for name, pts, total in grants]
        body = "\n".join(lines)
        if reason:
            body += f"\n*Reason:* {reason}"

        embed = discord.Embed(
            title="Activity Granted",
            description=body[:4096],
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Session #{activity_session.id} — visible in /show-logs")

        await interaction.followup.send(embed=embed, ephemeral=True)


class ActivityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="add-activity",
        description="Add activity points to a list of people",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def add_activity_cmd(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(AddActivityModal())

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
            "History (`/show-logs`) is unchanged.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ActivityCog(bot))
