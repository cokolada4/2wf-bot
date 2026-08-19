import os
import json
import asyncio
import logging
import discord
from discord.ext import commands

logger = logging.getLogger("discord_bot.temp_voice")

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "temp_channels.json")

class TempVoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_path = DATA_PATH
        self.active_channels = set()  # set of int channel IDs
        self._lock = asyncio.Lock()
        self.load_active_channels()

    def load_active_channels(self):
        if not os.path.exists(self.data_path):
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            self.save_active_channels()
            return

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.active_channels = set(data.get("channels", []))
        except Exception as e:
            logger.error(f"Error loading temp channels data: {e}")
            self.active_channels = set()

    def save_active_channels(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            temp_path = f"{self.data_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump({"channels": list(self.active_channels)}, f, indent=4)
            os.replace(temp_path, self.data_path)
        except Exception as e:
            logger.error(f"Error saving temp channels data: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        # Startup cleanup for abandoned temporary channels
        await self.cleanup_abandoned_channels()

    async def cleanup_abandoned_channels(self):
        async with self._lock:
            guild_id = self.bot.config.get("guild_id")
            if not guild_id:
                return

            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return

            temp_cfg = self.bot.config.get("temp_voice", {})
            generator_id = temp_cfg.get("generator_channel_id")
            if generator_id:
                try:
                    generator_id = int(generator_id)
                except (ValueError, TypeError):
                    generator_id = None

            to_remove = set()
            for channel_id in list(self.active_channels):
                if generator_id and channel_id == generator_id:
                    to_remove.add(channel_id)
                    continue

                channel = guild.get_channel(channel_id)
                if channel is None:
                    to_remove.add(channel_id)
                elif isinstance(channel, discord.VoiceChannel):
                    if len(channel.members) == 0:
                        try:
                            logger.info(f"Deleting empty abandoned temp channel {channel.name} ({channel.id}) on startup")
                            await channel.delete(reason="Temp voice channel empty on bot startup")
                            to_remove.add(channel_id)
                        except discord.HTTPException as e:
                            logger.error(f"Failed to delete empty temp channel {channel.id}: {e}")

            if to_remove:
                self.active_channels -= to_remove
                self.save_active_channels()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        temp_cfg = self.bot.config.get("temp_voice", {})
        if not temp_cfg.get("enabled", True):
            return

        generator_id = temp_cfg.get("generator_channel_id")
        if not generator_id:
            return

        try:
            generator_id = int(generator_id)
        except (ValueError, TypeError):
            return

        # 1. Member joined generator channel
        if after.channel and after.channel.id == generator_id:
            async with self._lock:
                await self.create_temp_channel(member, temp_cfg)

        # 2. Member left a voice channel (check if it was a temp channel and is now empty)
        if before.channel and before.channel.id != generator_id:
            if before.channel.id in self.active_channels:
                async with self._lock:
                    # Re-check channel from guild to ensure accurate member count
                    channel = member.guild.get_channel(before.channel.id)
                    if channel and len(channel.members) == 0:
                        try:
                            logger.info(f"Deleting empty temp channel {channel.name} ({channel.id})")
                            await channel.delete(reason="Temporary voice channel empty")
                        except discord.HTTPException as e:
                            logger.error(f"Failed to delete temp channel {channel.id}: {e}")
                        finally:
                            self.active_channels.discard(before.channel.id)
                            self.save_active_channels()

    async def create_temp_channel(self, member: discord.Member, temp_cfg: dict):
        guild = member.guild
        category_id = temp_cfg.get("category_id")
        category = None
        if category_id:
            try:
                category = guild.get_channel(int(category_id))
            except (ValueError, TypeError):
                category = None

        name_format = temp_cfg.get("name_format", "🔊 {username}'s Room")
        channel_name = name_format.format(username=member.display_name)

        try:
            new_channel = await guild.create_voice_channel(
                name=channel_name,
                category=category if isinstance(category, discord.CategoryChannel) else None,
                reason=f"Temporary voice channel for {member.display_name}"
            )
            self.active_channels.add(new_channel.id)
            self.save_active_channels()

            # Automatically move member into new channel
            await member.move_to(new_channel, reason="Moved into created temporary voice channel")
            logger.info(f"Created temp channel {new_channel.name} ({new_channel.id}) for {member.display_name}")

        except discord.HTTPException as e:
            logger.error(f"Error creating temp voice channel for {member.display_name}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(TempVoiceCog(bot))
