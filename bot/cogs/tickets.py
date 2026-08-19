import os
import json
import asyncio
import logging
import discord
from discord import ui
from discord.ext import commands
from bot.utils.config import ConfigManager
from bot.utils.permissions import check_is_admin_user

logger = logging.getLogger("discord_bot.tickets")

TICKETS_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "tickets.json")

class TicketStore:
    def __init__(self, filepath: str = TICKETS_DATA_PATH):
        self.filepath = filepath
        self.tickets = {}  # channel_id_str: {owner_id, ticket_type, status, claimed_by}
        self.load()

    def load(self):
        if not os.path.exists(self.filepath):
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            self.save()
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.tickets = json.load(f)
        except Exception as e:
            logger.error(f"Error loading tickets data: {e}")
            self.tickets = {}

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            temp_path = f"{self.filepath}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.tickets, f, indent=4)
            os.replace(temp_path, self.filepath)
        except Exception as e:
            logger.error(f"Error saving tickets data: {e}")

    def create_ticket(self, channel_id: int, owner_id: int, ticket_type: str):
        self.tickets[str(channel_id)] = {
            "owner_id": owner_id,
            "type": ticket_type,
            "status": "open",
            "claimed_by": None
        }
        self.save()

    def get_ticket(self, channel_id: int):
        return self.tickets.get(str(channel_id))

    def update_ticket(self, channel_id: int, key: str, value):
        cid = str(channel_id)
        if cid in self.tickets:
            self.tickets[cid][key] = value
            self.save()

    def remove_ticket(self, channel_id: int):
        cid = str(channel_id)
        if cid in self.tickets:
            del self.tickets[cid]
            self.save()

    def has_open_ticket(self, owner_id: int, ticket_type: str) -> bool:
        for t in self.tickets.values():
            if t.get("owner_id") == owner_id and t.get("type") == ticket_type and t.get("status") == "open":
                return True
        return False

ticket_store = TicketStore()

class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_claim_btn", emoji="✋")
    async def claim_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        member = interaction.user
        channel = interaction.channel
        config: ConfigManager = interaction.client.config

        ticket_data = ticket_store.get_ticket(channel.id)
        if not ticket_data:
            await interaction.response.send_message("This channel is not a recognized ticket channel.", ephemeral=True)
            return

        # Check staff/admin permissions
        tickets_cfg = config.get("tickets", {})
        support_role_id = tickets_cfg.get("support_role_id")
        has_support_role = support_role_id and any(r.id == int(support_role_id) for r in member.roles)
        is_admin = check_is_admin_user(member, config)

        if not (has_support_role or is_admin):
            await interaction.response.send_message("Only staff members can claim tickets.", ephemeral=True)
            return

        if ticket_data.get("claimed_by"):
            claimer = guild.get_member(ticket_data["claimed_by"])
            claimer_name = claimer.display_name if claimer else f"<@{ticket_data['claimed_by']}>"
            await interaction.response.send_message(f"This ticket has already been claimed by {claimer_name}.", ephemeral=True)
            return

        ticket_store.update_ticket(channel.id, "claimed_by", member.id)

        embed = discord.Embed(
            description=f"✋ Ticket has been claimed by {member.mention}.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.secondary, custom_id="ticket_close_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        config: ConfigManager = interaction.client.config
        member = interaction.user

        ticket_data = ticket_store.get_ticket(channel.id)
        if not ticket_data:
            await interaction.response.send_message("This channel is not a recognized ticket channel.", ephemeral=True)
            return

        # Check permissions: ticket creator or staff/admin
        is_owner = member.id == ticket_data["owner_id"]
        tickets_cfg = config.get("tickets", {})
        support_role_id = tickets_cfg.get("support_role_id")
        has_support_role = support_role_id and any(r.id == int(support_role_id) for r in member.roles)
        is_admin = check_is_admin_user(member, config)

        if not (is_owner or has_support_role or is_admin):
            await interaction.response.send_message("You do not have permission to close this ticket.", ephemeral=True)
            return

        if ticket_data.get("status") == "closed":
            await interaction.response.send_message("This ticket is already closed.", ephemeral=True)
            return

        ticket_store.update_ticket(channel.id, "status", "closed")

        # Remove send message permission for the creator
        owner = interaction.guild.get_member(ticket_data["owner_id"])
        if owner:
            try:
                await channel.set_permissions(owner, send_messages=False, read_messages=True)
            except discord.HTTPException:
                pass

        embed = discord.Embed(
            description=f"🔒 Ticket closed by {member.mention}.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    @ui.button(label="Delete Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_delete_btn", emoji="🗑️")
    async def delete_ticket(self, interaction: discord.Interaction, button: ui.Button):
        channel = interaction.channel
        config: ConfigManager = interaction.client.config
        member = interaction.user

        ticket_data = ticket_store.get_ticket(channel.id)
        if not ticket_data:
            await interaction.response.send_message("This channel is not a recognized ticket channel.", ephemeral=True)
            return

        tickets_cfg = config.get("tickets", {})
        support_role_id = tickets_cfg.get("support_role_id")
        has_support_role = support_role_id and any(r.id == int(support_role_id) for r in member.roles)
        is_admin = check_is_admin_user(member, config)

        if not (has_support_role or is_admin or member.id == ticket_data["owner_id"]):
            await interaction.response.send_message("You do not have permission to delete this ticket.", ephemeral=True)
            return

        await interaction.response.send_message("Deleting ticket channel in 5 seconds...")
        ticket_store.remove_ticket(channel.id)
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket deleted by {member.display_name}")
        except discord.HTTPException as e:
            logger.error(f"Failed to delete ticket channel {channel.id}: {e}")

class TicketDropdown(ui.Select):
    def __init__(self, config: ConfigManager):
        self.config = config
        tickets_cfg = config.get("tickets", {})
        types_cfg = tickets_cfg.get("types", {})

        options = []
        for key, t_data in types_cfg.items():
            options.append(
                discord.SelectOption(
                    label=t_data.get("name", key.capitalize()),
                    value=key,
                    emoji=t_data.get("emoji", "🎫"),
                    description=t_data.get("description", "")[:100]
                )
            )

        if not options:
            options = [
                discord.SelectOption(label="Support", value="support", emoji="🎫", description="Get help from staff")
            ]

        super().__init__(
            placeholder="Select a ticket category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_select_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]
        guild = interaction.guild
        member = interaction.user

        # Prevent duplicate tickets of the same type for the user
        if ticket_store.has_open_ticket(member.id, ticket_type):
            await interaction.response.send_message(
                f"You already have an open ticket for category **{ticket_type}**. Please close it before opening a new one.",
                ephemeral=True
            )
            return

        tickets_cfg = self.config.get("tickets", {})
        category_id = tickets_cfg.get("category_id")
        category = None
        if category_id:
            try:
                category = guild.get_channel(int(category_id))
            except (ValueError, TypeError):
                category = None

        support_role_id = tickets_cfg.get("support_role_id")
        support_role = None
        if support_role_id:
            try:
                support_role = guild.get_role(int(support_role_id))
            except (ValueError, TypeError):
                support_role = None

        # Build Permission Overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
            member: discord.PermissionOverwrite(read_messages=True, view_channel=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, view_channel=True, send_messages=True, manage_channels=True, manage_permissions=True)
        }

        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, view_channel=True, send_messages=True, attach_files=True)

        admin_role_id = self.config.get("admin_role_id")
        if admin_role_id:
            try:
                admin_role = guild.get_role(int(admin_role_id))
                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, view_channel=True, send_messages=True, attach_files=True)
            except (ValueError, TypeError):
                pass

        # Channel name format
        clean_username = "".join(c for c in member.name if c.isalnum() or c in "-_").lower() or "user"
        channel_name = f"ticket-{clean_username}"

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category if isinstance(category, discord.CategoryChannel) else None,
                overwrites=overwrites,
                reason=f"Ticket created by {member.display_name}"
            )

            ticket_store.create_ticket(ticket_channel.id, member.id, ticket_type)

            type_info = tickets_cfg.get("types", {}).get(ticket_type, {})
            type_name = type_info.get("name", ticket_type.capitalize())

            embed = discord.Embed(
                title=f"Ticket - {type_name}",
                description=f"Welcome {member.mention}! Please describe your issue or question in detail. A staff member will assist you shortly.",
                color=discord.Color.green()
            )
            embed.add_field(name="Category", value=type_name, inline=True)
            embed.add_field(name="Created By", value=member.mention, inline=True)

            control_view = TicketControlView()
            await ticket_channel.send(content=f"{member.mention}", embed=embed, view=control_view)

            await interaction.response.send_message(
                f"Your ticket has been created: {ticket_channel.mention}",
                ephemeral=True
            )

        except discord.HTTPException as e:
            logger.error(f"Error creating ticket channel: {e}")
            await interaction.response.send_message("Failed to create ticket channel. Please contact an administrator.", ephemeral=True)

class TicketDropdownView(ui.View):
    def __init__(self, config: ConfigManager):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown(config))

class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent views so buttons/dropdowns work after bot restarts
        self.bot.add_view(TicketDropdownView(self.bot.config))
        self.bot.add_view(TicketControlView())

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
