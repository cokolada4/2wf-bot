import logging
import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.permissions import is_admin

logger = logging.getLogger("discord_bot.moderation")

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Bulk delete a specified number of messages.")
    @app_commands.describe(amount="The number of messages to delete (1-100)")
    @is_admin()
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Please specify a positive number of messages to delete.", ephemeral=True)
            return

        if amount > 100:
            await interaction.response.send_message("You cannot delete more than 100 messages at once.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            await interaction.followup.send("This command can only be used in text channels.", ephemeral=True)
            return

        try:
            deleted = await channel.purge(limit=amount)
            num_deleted = len(deleted)

            if num_deleted < amount:
                await interaction.followup.send(
                    f"Successfully deleted {num_deleted} messages. (Note: Messages older than 14 days cannot be bulk deleted).",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(f"Successfully deleted {num_deleted} messages.", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("Bot lacks permission to manage/delete messages in this channel.", ephemeral=True)
        except discord.HTTPException as e:
            logger.error(f"Failed to clear messages: {e}")
            await interaction.followup.send(f"Failed to delete messages due to an error: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
