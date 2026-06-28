import discord
from discord import app_commands
from discord.ext import commands

COMMANDS = [
    {
        "name": "/spread-loot",
        "who": "Everyone",
        "desc": "Spread loot among people. Optionally grant activity points to each winner.",
    },
    {
        "name": "/show-logs",
        "who": "Everyone",
        "desc": "See all loot given out in the past 7 days.",
    },
    {
        "name": "/wipe",
        "who": "Server owner only",
        "desc": "Reset all activity points and bad-luck streaks. Loot logs stay.",
    },
    {
        "name": "/show-activity",
        "who": "Everyone",
        "desc": "See activity points for all tracked members.",
    },
    {
        "name": "/add-activity",
        "who": "Admins (Manage Server)",
        "desc": "Give activity points to a member (boosts loot chance).",
    },
    {
        "name": "/help",
        "who": "Everyone",
        "desc": "Show this command list.",
    },
    {
        "name": "/set-boss-alerts",
        "who": "Admins (Manage Server)",
        "desc": "Set the channel for boss timer alerts.",
    },
    {
        "name": "/add-boss",
        "who": "Admins (Manage Server)",
        "desc": "Add a boss to the timer panel.",
    },
    {
        "name": "/remove-boss",
        "who": "Admins (Manage Server)",
        "desc": "Remove a boss from the timer panel.",
    },
    {
        "name": "/list-bosses",
        "who": "Everyone",
        "desc": "Show all bosses and their current timer status.",
    },
    {
        "name": "/boss-panel",
        "who": "Admins (Manage Server)",
        "desc": "Post the boss timer button panel (click to start 4h timer).",
    },
]


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="List all bot commands")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        lines = []
        for cmd in COMMANDS:
            lines.append(f"**{cmd['name']}** — {cmd['desc']}\n*Who:* {cmd['who']}")

        embed = discord.Embed(
            title="Loot Bot Commands",
            description="\n\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
