import os
import sys
import asyncio
import logging
import discord
from discord.ext import commands
from bot.utils.config import ConfigManager
from bot.utils.logging import setup_logging

logger = setup_logging()

class ModularDiscordBot(commands.Bot):
    def __init__(self, config: ConfigManager, *args, **kwargs):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.voice_states = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            *args,
            **kwargs
        )
        self.config = config
        self.guild_id = self.config.get("guild_id")

    async def setup_hook(self) -> None:
        if not self.guild_id:
            logger.critical("No valid 'guild_id' configured in config.json! Bot refusing to start.")
            raise RuntimeError("Missing or invalid 'guild_id' in configuration.")

        try:
            self.guild_id = int(self.guild_id)
        except (ValueError, TypeError):
            logger.critical(f"Invalid guild_id type/format: {self.guild_id}")
            raise RuntimeError(f"Invalid guild_id: {self.guild_id}")

        target_guild = discord.Object(id=self.guild_id)

        # Cogs to load
        cogs = [
            "bot.cogs.admin",
            "bot.cogs.moderation",
            "bot.cogs.temp_voice",
            "bot.cogs.tickets",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension: {cog}")
            except Exception as e:
                logger.error(f"Failed to load extension {cog}: {e}")

        # Copy global commands to single guild & sync to guild only
        self.tree.copy_global_to(guild=target_guild)
        synced = await self.tree.sync(guild=target_guild)
        logger.info(f"Synced {len(synced)} slash command(s) to guild ID {self.guild_id}")

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if self.guild_id and interaction.guild_id != self.guild_id:
            logger.warning(f"Ignoring interaction from unauthorized guild_id: {interaction.guild_id}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "This bot is not configured to operate on this server.", ephemeral=True
                )
            return
        await super().on_interaction(interaction)

    async def on_ready(self) -> None:
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")

def create_bot(config_path: str = None) -> ModularDiscordBot:
    config = ConfigManager(filepath=config_path) if config_path else ConfigManager()
    bot = ModularDiscordBot(config=config)
    return bot

def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.critical("DISCORD_TOKEN environment variable is not set!")
        sys.exit(1)

    config = ConfigManager()
    if not config.get("guild_id"):
        logger.critical("No valid 'guild_id' configured in config.json! Refusing to start.")
        sys.exit(1)

    bot = ModularDiscordBot(config=config)
    bot.run(token)

if __name__ == "__main__":
    main()
