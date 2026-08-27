"""
================================================================================
ZARA - Interactive Features Cog (Roles & Tickets)
================================================================================
Provides:
1. Interactive Self-Assign Roles (Button Views & Dropdowns for Pings & Games)
2. Ticket System (Button Create Ticket -> Private Channel for User + Admins -> Close Button deletes channel)
================================================================================
"""

import asyncio
import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


# ==============================================================================
# PERSISTENT VIEWS: SELF-ASSIGN ROLES
# ==============================================================================

class NotificationRolesView(discord.ui.View):
    """Persistent button view for toggling Notification Ping roles."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    async def _toggle_role(self, interaction: discord.Interaction, role_name: str) -> None:
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            return

        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role:
            await interaction.response.send_message(f"❌ Role `{role_name}` not found on server.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role, reason="ZARA: Self-assign role removal")
            await interaction.response.send_message(f"🔕 Removed {role.mention} from your roles.", ephemeral=True)
        else:
            await interaction.user.add_roles(role, reason="ZARA: Self-assign role addition")
            await interaction.response.send_message(f"🔔 Added {role.mention} to your roles!", ephemeral=True)

    @discord.ui.button(
        label="Announcements Ping",
        style=discord.ButtonStyle.primary,
        emoji="📢",
        custom_id="zara_role_announcements",
    )
    async def announcements_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._toggle_role(interaction, "Announcements Ping")

    @discord.ui.button(
        label="Events Ping",
        style=discord.ButtonStyle.success,
        emoji="🎉",
        custom_id="zara_role_events",
    )
    async def events_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._toggle_role(interaction, "Events Ping")


class GameRolesView(discord.ui.View):
    """Persistent button grid for toggling Gaming roles directly."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    async def _toggle_game_role(self, interaction: discord.Interaction, role_name: str) -> None:
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            return

        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role:
            await interaction.response.send_message(f"❌ Role `{role_name}` not found on server.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role, reason="ZARA: Game role toggle")
            await interaction.response.send_message(f"❌ Removed **{role.name}** from your roles.", ephemeral=True)
        else:
            await interaction.user.add_roles(role, reason="ZARA: Game role toggle")
            await interaction.response.send_message(f"✅ Added **{role.name}** to your roles!", ephemeral=True)

    @discord.ui.button(label="Valorant", style=discord.ButtonStyle.secondary, emoji="🎯", custom_id="zara_btn_val", row=0)
    async def val_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._toggle_game_role(interaction, "Valorant")

    @discord.ui.button(label="League of Legends", style=discord.ButtonStyle.secondary, emoji="⚔️", custom_id="zara_btn_lol", row=0)
    async def lol_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._toggle_game_role(interaction, "League of Legends")

    @discord.ui.button(label="Apex Legends", style=discord.ButtonStyle.secondary, emoji="🏆", custom_id="zara_btn_apex", row=0)
    async def apex_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._toggle_game_role(interaction, "Apex Legends")

    @discord.ui.button(label="Minecraft", style=discord.ButtonStyle.secondary, emoji="⛏️", custom_id="zara_btn_mc", row=1)
    async def mc_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._toggle_game_role(interaction, "Minecraft")

    @discord.ui.button(label="Roblox", style=discord.ButtonStyle.secondary, emoji="🧱", custom_id="zara_btn_roblox", row=1)
    async def roblox_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._toggle_game_role(interaction, "Roblox")

    @discord.ui.button(label="Genshin Impact", style=discord.ButtonStyle.secondary, emoji="✨", custom_id="zara_btn_genshin", row=1)
    async def genshin_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._toggle_game_role(interaction, "Genshin Impact")

    @discord.ui.button(label="Mobile Legends", style=discord.ButtonStyle.secondary, emoji="🛡️", custom_id="zara_btn_mlbb", row=2)
    async def mlbb_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._toggle_game_role(interaction, "Mobile Legends")


# ==============================================================================
# PERSISTENT VIEWS: TICKET CREATION & MANAGEMENT
# ==============================================================================

class CloseTicketView(discord.ui.View):
    """Button inside an active ticket channel allowing user/staff to close & delete it."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close & Delete Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="zara_ticket_close_btn",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not isinstance(interaction.channel, discord.TextChannel) or not interaction.guild:
            return

        await interaction.response.send_message("⚠️ Closing and deleting ticket in **5 seconds**...", ephemeral=False)

        # Log ticket closure to #bot-actions-log
        actions_channel = discord.utils.get(interaction.guild.text_channels, name="bot-actions-log")
        if actions_channel:
            embed = discord.Embed(
                title="🎟️ Ticket Closed & Deleted",
                description=f"Ticket channel `{interaction.channel.name}` closed by {interaction.user.mention}.",
                color=discord.Color.dark_red(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.add_field(name="Closed By", value=f"{interaction.user.mention} (`{interaction.user}`)", inline=True)
            embed.add_field(name="Channel", value=f"`{interaction.channel.name}`", inline=True)
            embed.set_footer(text="ZARA Ticket Manager (Ephemeral / Not Archived)")
            try:
                await actions_channel.send(embed=embed)
            except Exception:
                pass

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to delete channel: {e}", ephemeral=True)


class CreateTicketView(discord.ui.View):
    """Persistent button view posted in #create-a-ticket."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Support / Report Ticket",
        style=discord.ButtonStyle.primary,
        emoji="📩",
        custom_id="zara_create_ticket_btn",
    )
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            return

        guild = interaction.guild
        user = interaction.user

        # Prevent duplicate tickets by checking existing channels
        ticket_channel_name = f"ticket-{user.name.lower().replace(' ', '-')}"
        existing = discord.utils.get(guild.text_channels, name=ticket_channel_name)
        if existing:
            await interaction.response.send_message(
                f"❌ You already have an open ticket: {existing.mention}. Please resolve or close it first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Target category: STAFF HEADQUARTERS or WELCOME category
        staff_cat = discord.utils.get(guild.categories, name="⁺‧₊ ✧ STAFF HEADQUARTERS ✧ ₊‧⁺")

        # Permission overwrites: Accessible ONLY to creator and Admins/Executive/Owner (VIP NOT included)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
        }

        # Add staff roles (Admin, Executive, Owner)
        for role_name in ["Owner", "Executive", "Administrator", "Moderator"]:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                )

        try:
            ticket_channel = await guild.create_text_channel(
                name=ticket_channel_name,
                category=staff_cat,
                overwrites=overwrites,
                topic=f"Private ticket created by {user} (ID: {user.id}). Closes & deletes automatically upon resolution.",
                reason=f"ZARA Ticket: Created for {user}",
            )

            # Post introductory ticket embed inside the created channel
            welcome_embed = discord.Embed(
                title=f"🎟️ Private Ticket — {user.display_name}",
                description=(
                    f"Hello {user.mention}! 👋\n\n"
                    "Thank you for reaching out. Please describe your issue, question, or report in detail below.\n"
                    "Our **Administrators & Staff** have been notified and will assist you shortly.\n\n"
                    "> ⚠️ **Note:** Once resolved, click the red **Close & Delete Ticket** button below. "
                    "The channel will be permanently deleted without archival."
                ),
                color=discord.Color.purple(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            welcome_embed.set_thumbnail(url=user.display_avatar.url)
            welcome_embed.set_footer(text="ZARA Support Engine")

            await ticket_channel.send(
                content=f"{user.mention} | Staff notification",
                embed=welcome_embed,
                view=CloseTicketView(),
            )

            # Log to #bot-actions-log
            actions_channel = discord.utils.get(guild.text_channels, name="bot-actions-log")
            if actions_channel:
                log_embed = discord.Embed(
                    title="🎟️ Ticket Opened",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                )
                log_embed.add_field(name="Creator", value=f"{user.mention} (`{user}` / ID: `{user.id}`)", inline=True)
                log_embed.add_field(name="Channel", value=ticket_channel.mention, inline=True)
                try:
                    await actions_channel.send(embed=log_embed)
                except Exception:
                    pass

            await interaction.followup.send(f"✅ Your ticket has been created: {ticket_channel.mention}", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("❌ Bot lacks permission to create private ticket channels.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Discord API error: {e}", ephemeral=True)


# ==============================================================================
# INTERACTIVE COG SETUP
# ==============================================================================

class Interactive(commands.Cog):
    """Cog managing persistent UI views and setup commands for self-roles and tickets."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        # Register persistent views so buttons work across bot restarts
        self.bot.add_view(NotificationRolesView())
        self.bot.add_view(GameRolesView())
        self.bot.add_view(CreateTicketView())
        self.bot.add_view(CloseTicketView())

    @app_commands.command(name="setup_tickets", description="Post the interactive Create Ticket panel in #create-a-ticket.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction) -> None:
        ticket_channel = discord.utils.get(interaction.guild.text_channels, name="create-a-ticket")
        if not ticket_channel:
            await interaction.response.send_message("❌ Channel `#create-a-ticket` not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎫 ⁺‧₊ ✧ Community Support & Reports ✧ ₊‧⁺",
            description=(
                "Need help, want to report a rule violation, or have a private inquiry?\n\n"
                "Click the button below to open a **Private Support Ticket**.\n\n"
                "• 🔒 **Private & Secure:** Only you and the Staff Team (Admin/Owner) can view the ticket.\n"
                "• 🗑️ **Ephemeral Resolution:** When closed, the ticket channel is permanently deleted.\n\n"
                "*Please do not open tickets for casual banter.*"
            ),
            color=discord.Color.from_rgb(142, 68, 173),
        )
        embed.set_footer(text="ZARA Autonomous Administration")

        await ticket_channel.send(embed=embed, view=CreateTicketView())
        await interaction.response.send_message("✅ Ticket panel successfully deployed to #create-a-ticket!", ephemeral=True)

    @app_commands.command(name="setup_roles", description="Post the interactive Self-Assign Role panels in #roles-assignment.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_roles(self, interaction: discord.Interaction) -> None:
        roles_channel = discord.utils.get(interaction.guild.text_channels, name="roles-assignment")
        if not roles_channel:
            await interaction.response.send_message("❌ Channel `#roles-assignment` not found.", ephemeral=True)
            return

        # Notification Roles Embed
        pings_embed = discord.Embed(
            title="🔔 ⁺‧₊ ✧ Notification Pings ✧ ₊‧⁺",
            description="Click the buttons below to toggle server notification alerts:",
            color=discord.Color.gold(),
        )
        await roles_channel.send(embed=pings_embed, view=NotificationRolesView())

        # Gaming Roles Embed
        games_embed = discord.Embed(
            title="🎮 ⁺‧₊ ✧ Gaming Roles ✧ ₊‧⁺",
            description="Select the games you play from the dropdown menu to receive squad pings and access gaming discussion channels:",
            color=discord.Color.from_rgb(52, 152, 219),
        )
        await roles_channel.send(embed=games_embed, view=GameRolesView())

        await interaction.response.send_message("✅ Self-assign role panels deployed to #roles-assignment!", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Interactive(bot))
