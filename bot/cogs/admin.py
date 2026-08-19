import logging
import discord
from discord import app_commands
from discord.ext import commands
from bot.utils.permissions import is_admin

logger = logging.getLogger("discord_bot.admin")

class SetupGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="setup", description="Administrative setup commands")

    @app_commands.command(name="admin-role", description="Configure the bot's Admin Role")
    @app_commands.describe(role="The role to set as the bot Admin Role")
    @is_admin()
    async def admin_role(self, interaction: discord.Interaction, role: discord.Role):
        bot = interaction.client
        bot.config.set("admin_role_id", role.id)
        await interaction.response.send_message(
            f"Successfully updated Admin Role to {role.mention} (ID: `{role.id}`).",
            ephemeral=True
        )

    @app_commands.command(name="ticket-panel", description="Post the ticket creation panel in the current channel")
    @is_admin()
    async def ticket_panel(self, interaction: discord.Interaction):
        # We will import TicketSelectView from cogs.tickets dynamically or use the view registered there
        from bot.cogs.tickets import TicketDropdownView

        tickets_cfg = interaction.client.config.get("tickets", {})
        if not tickets_cfg.get("enabled", True):
            await interaction.response.send_message("Ticket system is currently disabled in configuration.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📩 Support Tickets",
            description="Need help or wish to create a report? Select a ticket type from the menu below to open a private ticket channel.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Select an option below to get started.")

        view = TicketDropdownView(interaction.client.config)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Ticket panel posted successfully!", ephemeral=True)

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.tree.add_command(SetupGroup())

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
