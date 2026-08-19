import functools
import discord
from discord import app_commands
from bot.utils.config import ConfigManager

def check_is_admin_user(member: discord.Member, config: ConfigManager) -> bool:
    """
    Checks if a member has admin rights based on:
    1. Having Discord Administrator permission.
    2. Having the configured admin role ID.
    """
    if not isinstance(member, discord.Member):
        return False

    # Check Discord Administrator permission
    if member.guild_permissions.administrator:
        return True

    # Check configured admin_role_id
    admin_role_id = config.get("admin_role_id")
    if admin_role_id and any(role.id == int(admin_role_id) for role in member.roles):
        return True

    return False

def is_admin():
    """
    A slash command check decorator for admin-only commands.
    Checks if the user has Administrator permissions or the configured admin role.
    If unauthorized, responds with an ephemeral error message.
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "You do not have permission to use this command.", ephemeral=True
                )
            return False

        config: ConfigManager = interaction.client.config

        if check_is_admin_user(interaction.user, config):
            return True

        if not interaction.response.is_done():
            await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
        return False

    return app_commands.check(predicate)
