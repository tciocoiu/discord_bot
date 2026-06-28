import asyncio
import logging

import discord
from discord.ext import commands

from bot.config import load_config
from bot.db.engine import create_tables, init_db
from bot.cogs import activity, bosses, help as help_cog, loot
from bot.services.boss_timers import restore_timers_on_startup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LootBot(commands.Bot):
    def __init__(self, config):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.config = config

    async def setup_hook(self) -> None:
        await create_tables()
        await loot.setup(self, self.config)
        await activity.setup(self)
        await bosses.setup(self)
        await help_cog.setup(self)
        await self.tree.sync()
        await restore_timers_on_startup(self)
        logger.info("Slash commands synced")


async def main() -> None:
    config = load_config()
    init_db(config)

    bot = LootBot(config)

    @bot.event
    async def on_ready() -> None:
        logger.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")

    await bot.start(config.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
