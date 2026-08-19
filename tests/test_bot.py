import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from bot.utils.config import ConfigManager, DEFAULT_CONFIG
from bot.utils.permissions import check_is_admin_user, is_admin
from bot.cogs.moderation import ModerationCog
from bot.cogs.admin import SetupGroup, AdminCog
from bot.cogs.temp_voice import TempVoiceCog
from bot.cogs.tickets import TicketStore, TicketDropdown, TicketControlView, TicketsCog

@pytest.fixture
def temp_config_file(tmp_path):
    config_file = tmp_path / "config.json"
    data = {
        "guild_id": 123456789,
        "admin_role_id": 999888777,
        "temp_voice": {
            "enabled": True,
            "generator_channel_id": 111222333,
            "category_id": 444555666,
            "name_format": "🔊 {username}'s Room"
        },
        "tickets": {
            "enabled": True,
            "category_id": 777888999,
            "support_role_id": 111999222,
            "types": {
                "support": {
                    "name": "Support",
                    "emoji": "🎫",
                    "description": "Get help"
                }
            }
        }
    }
    config_file.write_text(json.dumps(data), encoding="utf-8")
    return str(config_file)

def test_config_manager(temp_config_file):
    cfg = ConfigManager(filepath=temp_config_file)
    assert cfg.get("guild_id") == 123456789
    assert cfg.get("admin_role_id") == 999888777

    cfg.set("admin_role_id", 111222)
    assert cfg.get("admin_role_id") == 111222

    # Check update_nested
    cfg.update_nested(["temp_voice", "enabled"], False)
    assert cfg.get("temp_voice")["enabled"] is False

def test_permissions_check(temp_config_file):
    cfg = ConfigManager(filepath=temp_config_file)

    # Case 1: Member with Administrator permission
    member_admin = MagicMock(spec=discord.Member)
    member_admin.guild_permissions.administrator = True
    assert check_is_admin_user(member_admin, cfg) is True

    # Case 2: Member with admin role
    member_role = MagicMock(spec=discord.Member)
    member_role.guild_permissions.administrator = False
    role_mock = MagicMock()
    role_mock.id = 999888777
    member_role.roles = [role_mock]
    assert check_is_admin_user(member_role, cfg) is True

    # Case 3: Unauthorized member
    member_normal = MagicMock(spec=discord.Member)
    member_normal.guild_permissions.administrator = False
    other_role = MagicMock()
    other_role.id = 123
    member_normal.roles = [other_role]
    assert check_is_admin_user(member_normal, cfg) is False

@pytest.mark.asyncio
async def test_moderation_clear():
    bot = MagicMock()
    cog = ModerationCog(bot)

    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()

    # Channel mock
    channel = AsyncMock(spec=discord.TextChannel)
    channel.purge.return_value = [MagicMock(), MagicMock()]
    interaction.channel = channel

    await cog.clear.callback(cog, interaction, amount=2)
    channel.purge.assert_called_once_with(limit=2)
    interaction.followup.send.assert_called_with("Successfully deleted 2 messages.", ephemeral=True)

@pytest.mark.asyncio
async def test_temp_voice(tmp_path):
    bot = MagicMock()
    bot.config = ConfigManager(filepath=str(tmp_path / "cfg.json"))
    bot.config.set("guild_id", 1234)
    bot.config.set("temp_voice", {
        "enabled": True,
        "generator_channel_id": 100,
        "category_id": 200,
        "name_format": "🔊 {username}'s Room"
    })

    cog = TempVoiceCog(bot)
    cog.data_path = str(tmp_path / "temp_channels.json")

    # Member joining generator
    member = AsyncMock(spec=discord.Member)
    member.bot = False
    member.display_name = "TestUser"
    guild = AsyncMock(spec=discord.Guild)
    member.guild = guild

    generator_channel = MagicMock(spec=discord.VoiceChannel)
    generator_channel.id = 100

    created_vc = AsyncMock(spec=discord.VoiceChannel)
    created_vc.id = 500
    guild.create_voice_channel.return_value = created_vc

    before = MagicMock(spec=discord.VoiceState)
    before.channel = None
    after = MagicMock(spec=discord.VoiceState)
    after.channel = generator_channel

    await cog.on_voice_state_update(member, before, after)

    guild.create_voice_channel.assert_called_once()
    member.move_to.assert_called_once_with(created_vc, reason="Moved into created temporary voice channel")
    assert 500 in cog.active_channels

def test_ticket_store(tmp_path):
    data_file = str(tmp_path / "tickets.json")
    store = TicketStore(filepath=data_file)

    assert store.has_open_ticket(123, "support") is False
    store.create_ticket(111, 123, "support")
    assert store.has_open_ticket(123, "support") is True
    assert store.get_ticket(111)["owner_id"] == 123

    store.update_ticket(111, "status", "closed")
    assert store.has_open_ticket(123, "support") is False
