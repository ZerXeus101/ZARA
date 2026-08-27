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
import contextlib
import datetime
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


# ==============================================================================
# SECURITY: SELF-ASSIGNABLE ROLE ALLOWLIST & VALIDATION
# ==============================================================================

# Permissions that must NEVER be present on a self-assignable role.
# If a role has any of these, users cannot self-assign it via buttons.
DANGEROUS_PERMISSIONS = frozenset({
    "administrator",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_webhooks",
    "manage_permissions",
    "ban_members",
    "kick_members",
    "moderate_members",
    "mention_everyone",
    "manage_messages",
    "manage_threads",
})

# Single Source of Truth: Load immutable self-assignable role mapping from server_structure.json.
# No Discord role IDs are hardcoded in this cog.
from types import MappingProxyType
from config_loader import (
    ConfigLoadError,
    SelfAssignableRole,
    load_self_assignable_roles,
    load_zara_role_id,
)

try:
    SELF_ASSIGNABLE_ROLES, SELF_ASSIGNABLE_ROLE_IDS = load_self_assignable_roles()
except ConfigLoadError as _err:
    print(f"[ZARA - SECURITY WARN] Could not load self-assignable roles from server_structure.json: {_err}")
    # Fail closed: empty immutable mappings ensure buttons safely refuse assignment
    SELF_ASSIGNABLE_ROLES: MappingProxyType[str, SelfAssignableRole] = MappingProxyType({})
    SELF_ASSIGNABLE_ROLE_IDS: frozenset[int] = frozenset()


def validate_self_assignable_role(
    role: Optional[discord.Role],
    guild: discord.Guild,
    allowlist: Optional[frozenset[int]] = None,
) -> Optional[str]:
    """Validate that a role is safe for self-assignment.

    Checks:
    1. Role must exist in guild.
    2. Role ID must be in the explicit allowlist.
    3. Role must not be @everyone.
    4. Role must not be managed by an integration/bot.
    5. Role must be below the bot's highest role.
    6. Role must not contain any dangerous permissions.

    Returns None if safe, or an error message string if the role must be rejected.
    Fails closed: any validation failure returns an error.
    """
    active_allowlist = allowlist if allowlist is not None else SELF_ASSIGNABLE_ROLE_IDS

    if role is None:
        return "Configured role not found on this server."

    # Must be in the explicit allowlist derived from server_structure.json
    if role.id not in active_allowlist:
        return f"**Security Blocked:** Role `{role.name}` (ID: `{role.id}`) is not in the self-assignable allowlist."

    # Must not be @everyone
    if role.is_default():
        return "Cannot self-assign the @everyone role."

    # Must not be a managed/integration role (bots, boosts, integrations)
    if role.managed:
        return f"Role `{role.name}` is managed by an integration and cannot be self-assigned."

    # Must be below the bot's highest role (bot must be able to assign it)
    bot_member = guild.me
    if bot_member and role >= bot_member.top_role:
        return f"Role `{role.name}` is above or equal to ZARA's highest role and cannot be assigned."

    # Must not contain any dangerous permissions
    role_perms = role.permissions
    for perm_name in DANGEROUS_PERMISSIONS:
        if getattr(role_perms, perm_name, False):
            return (
                f"**Security Blocked:** Role `{role.name}` has the `{perm_name}` permission "
                f"and cannot be self-assigned."
            )

    return None  # Safe


async def _toggle_role_by_key(interaction: discord.Interaction, role_key: str) -> None:
    """Generic, secure role toggle resolving logical key -> trusted role ID -> guild.get_role(role_id)."""
    if not isinstance(interaction.user, discord.Member) or not interaction.guild:
        return

    # Check 1: Key exists in validated configuration
    role_entry = SELF_ASSIGNABLE_ROLES.get(role_key)
    if not role_entry:
        await interaction.response.send_message(
            "🚫 **Security Blocked:** This role is not configured for self-assignment.",
            ephemeral=True,
        )
        return

    role_id = role_entry.role_id

    # Check 2: Explicit Allowlist check
    if role_id not in SELF_ASSIGNABLE_ROLE_IDS:
        await interaction.response.send_message(
            "🚫 **Security Blocked:** This role ID is not authorized for self-assignment.",
            ephemeral=True,
        )
        return

    # Check 3: Pure ID-based resolution (Never lookup by name)
    role = interaction.guild.get_role(role_id)
    if not role:
        await interaction.response.send_message(
            f"❌ Configured role `{role_entry.name}` (ID `{role_id}`) not found on this server.",
            ephemeral=True,
        )
        return

    # Check 4: Runtime security validation (hierarchy, permissions, managed, @everyone)
    validation_error = validate_self_assignable_role(role, interaction.guild)
    if validation_error:
        await interaction.response.send_message(f"🚫 {validation_error}", ephemeral=True)
        return

    # Toggle assignment
    if role in interaction.user.roles:
        await interaction.user.remove_roles(role, reason="ZARA: Self-assign role removal")
        await interaction.response.send_message(f"🔕 Removed **{role.name}** from your roles.", ephemeral=True)
    else:
        await interaction.user.add_roles(role, reason="ZARA: Self-assign role addition")
        await interaction.response.send_message(f"🔔 Added **{role.name}** to your roles!", ephemeral=True)


# ==============================================================================
# PERSISTENT VIEWS: SELF-ASSIGN ROLES
# ==============================================================================

class NotificationRolesView(discord.ui.View):
    """Persistent button view for toggling Notification Ping roles."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Announcements Ping",
        style=discord.ButtonStyle.primary,
        emoji="📢",
        custom_id="zara_role_announcements",
    )
    async def announcements_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _toggle_role_by_key(interaction, "announcements_ping")

    @discord.ui.button(
        label="Events Ping",
        style=discord.ButtonStyle.success,
        emoji="🎉",
        custom_id="zara_role_events",
    )
    async def events_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _toggle_role_by_key(interaction, "events_ping")


class GameRolesView(discord.ui.View):
    """Persistent button grid for toggling Gaming roles directly."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Valorant", style=discord.ButtonStyle.secondary, emoji="🎯", custom_id="zara_btn_val", row=0)
    async def val_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _toggle_role_by_key(interaction, "valorant")

    @discord.ui.button(label="League of Legends", style=discord.ButtonStyle.secondary, emoji="⚔️", custom_id="zara_btn_lol", row=0)
    async def lol_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _toggle_role_by_key(interaction, "league_of_legends")

    @discord.ui.button(label="Apex Legends", style=discord.ButtonStyle.secondary, emoji="🏆", custom_id="zara_btn_apex", row=0)
    async def apex_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _toggle_role_by_key(interaction, "apex_legends")

    @discord.ui.button(label="Minecraft", style=discord.ButtonStyle.secondary, emoji="⛏️", custom_id="zara_btn_mc", row=1)
    async def mc_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _toggle_role_by_key(interaction, "minecraft")

    @discord.ui.button(label="Roblox", style=discord.ButtonStyle.secondary, emoji="🧱", custom_id="zara_btn_roblox", row=1)
    async def roblox_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _toggle_role_by_key(interaction, "roblox")

    @discord.ui.button(label="Genshin Impact", style=discord.ButtonStyle.secondary, emoji="✨", custom_id="zara_btn_genshin", row=1)
    async def genshin_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _toggle_role_by_key(interaction, "genshin_impact")

    @discord.ui.button(label="Mobile Legends", style=discord.ButtonStyle.secondary, emoji="🛡️", custom_id="zara_btn_mlbb", row=2)
    async def mlbb_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await _toggle_role_by_key(interaction, "mobile_legends")


# ==============================================================================
# PERSISTENT VIEWS: TICKET CREATION & MANAGEMENT
# ==============================================================================

class CloseTicketView(discord.ui.View):
    """Button inside an active ticket channel allowing authorized user/staff to close & delete it.

    Authorization rules:
    - Channel name must start with 'ticket-' or 'apply-' (ZARA-created tickets only).
    - User must be either the ticket creator (extracted from channel topic) OR
      a staff member with manage_channels permission.
    - A _deleting guard prevents race conditions from double-clicks.
    """

    _TICKET_PREFIXES = ("ticket-", "apply-")
    # Regex to extract creator user ID from channel topic: "... (ID: 123456789)"
    _CREATOR_ID_PATTERN = re.compile(r'\(ID:\s*(\d+)\)')

    def __init__(self) -> None:
        super().__init__(timeout=None)
        self._deleting: bool = False

    @discord.ui.button(
        label="Close & Delete Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="zara_ticket_close_btn",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not isinstance(interaction.channel, discord.TextChannel) or not interaction.guild:
            return

        # Guard: prevent race condition from double-click
        if self._deleting:
            await interaction.response.send_message("⏳ This ticket is already being closed.", ephemeral=True)
            return

        channel = interaction.channel
        user = interaction.user

        # Security: only allow on ZARA-created ticket channels
        if not any(channel.name.startswith(prefix) for prefix in self._TICKET_PREFIXES):
            await interaction.response.send_message(
                "🚫 This button only works inside ZARA ticket channels.", ephemeral=True
            )
            return

        # Security: authorize the user
        is_staff = (
            isinstance(user, discord.Member)
            and user.guild_permissions.manage_channels
        )

        is_creator = False
        if channel.topic:
            match = self._CREATOR_ID_PATTERN.search(channel.topic)
            if match and int(match.group(1)) == user.id:
                is_creator = True

        if not is_staff and not is_creator:
            await interaction.response.send_message(
                "🚫 You are not authorized to close this ticket. Only the ticket creator or staff may close it.",
                ephemeral=True,
            )
            return

        # Mark as deleting to prevent double-close
        self._deleting = True

        await interaction.response.send_message("⚠️ Closing and deleting ticket in **5 seconds**...", ephemeral=False)

        # Log ticket closure to #bot-actions-log
        actions_channel = discord.utils.get(interaction.guild.text_channels, name="bot-actions-log")
        if actions_channel:
            embed = discord.Embed(
                title="🎟️ Ticket Closed & Deleted",
                description=f"Ticket channel `{channel.name}` closed by {user.mention}.",
                color=discord.Color.dark_red(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.add_field(name="Closed By", value=f"{user.mention} (`{user}`)", inline=True)
            embed.add_field(name="Channel", value=f"`{channel.name}`", inline=True)
            embed.add_field(name="Authorization", value="Staff" if is_staff else "Ticket Creator", inline=True)
            embed.set_footer(text="ZARA Ticket Manager (Ephemeral / Not Archived)")
            try:
                await actions_channel.send(embed=embed)
            except Exception:
                pass

        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket closed by {user} ({'staff' if is_staff else 'creator'})")
        except Exception as e:
            self._deleting = False
            try:
                await interaction.followup.send(f"❌ Failed to delete channel: {e}", ephemeral=True)
            except Exception:
                pass


# ==============================================================================
# CONCURRENCY LOCK MANAGER FOR TICKET CREATION
# ==============================================================================

class TicketLockManager:
    """Manages scoped in-memory asyncio locks for ticket creation.

    Locks are scoped by (guild_id, user_id, ticket_type) to prevent race conditions
    where concurrent requests from the same user create duplicate ticket channels.
    Entries are safely pruned when no tasks are waiting to prevent unbounded memory growth.
    """

    def __init__(self) -> None:
        self._locks: dict[tuple[int, int, str], asyncio.Lock] = {}
        self._counts: dict[tuple[int, int, str], int] = {}
        self._meta_lock = asyncio.Lock()

    @contextlib.asynccontextmanager
    async def acquire_ticket_lock(self, guild_id: int, user_id: int, ticket_type: str):
        key = (guild_id, user_id, ticket_type)
        async with self._meta_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
                self._counts[key] = 0
            self._counts[key] += 1
            lock = self._locks[key]

        await lock.acquire()
        try:
            yield
        finally:
            lock.release()
            async with self._meta_lock:
                self._counts[key] -= 1
                if self._counts[key] <= 0:
                    self._locks.pop(key, None)
                    self._counts.pop(key, None)


ticket_lock_manager = TicketLockManager()


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

        # Defer immediately to guarantee Discord 3-second interaction window is satisfied
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        async with ticket_lock_manager.acquire_ticket_lock(guild.id, user.id, "support"):
            # Sanitize channel name for Discord naming rules
            clean_name = re.sub(r'[^a-z0-9_-]', '', user.name.lower().replace(' ', '-'))[:20] or f"user-{user.id % 10000}"
            ticket_channel_name = f"ticket-{clean_name}"

            # Step a: Re-check whether user already has an open support ticket
            for ch in guild.text_channels:
                if ch.name == ticket_channel_name or (ch.topic and f"(ID: {user.id})" in ch.topic and ch.name.startswith("ticket-")):
                    await interaction.followup.send(
                        f"❌ You already have an open ticket: {ch.mention}. Please resolve or close it first.",
                        ephemeral=True,
                    )
                    return

            # Target category: STAFF HEADQUARTERS or fallback
            staff_cat = discord.utils.get(guild.categories, name="⁺‧₊ ✧ STAFF HEADQUARTERS ✧ ₊‧⁺")

            # Resolve Z.A.R.A role strictly by configured ID (Single Source of Truth)
            try:
                zara_role_id = load_zara_role_id()
            except ConfigLoadError:
                await interaction.followup.send(
                    "❌ Server configuration error: ZARA bot role is not properly configured.",
                    ephemeral=True,
                )
                return

            zara_role = guild.get_role(zara_role_id)
            if not zara_role:
                await interaction.followup.send(
                    "❌ Server configuration error: ZARA bot role not found on this server.",
                    ephemeral=True,
                )
                return

            # Explicitly grant bot permissions so least-privilege ZARA can manage the channel
            bot_overwrite = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
                add_reactions=True,
            )

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: bot_overwrite,
                zara_role: bot_overwrite,
                user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                ),
            }

            # Add staff roles (Admin, Executive, Owner, Moderator)
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

            except discord.Forbidden as e:
                await interaction.followup.send(f"❌ Bot lacks permission to create private ticket channels: {e}", ephemeral=True)
            except discord.HTTPException as e:
                await interaction.followup.send(f"❌ Discord API error: {e}", ephemeral=True)


class CreateApplicationTicketView(discord.ui.View):
    """Persistent button view posted in #membership-application for unverified users."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Apply for Membership / Start Interview",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="zara_apply_membership_btn",
    )
    async def apply_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            return

        # Defer immediately to guarantee Discord 3-second interaction window is satisfied
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        async with ticket_lock_manager.acquire_ticket_lock(guild.id, user.id, "application"):
            # Sanitize channel name for Discord naming rules
            clean_name = re.sub(r'[^a-z0-9_-]', '', user.name.lower().replace(' ', '-'))[:20] or f"user-{user.id % 10000}"
            ticket_channel_name = f"apply-{clean_name}"

            # Step a: Re-check whether user already has an active application ticket
            for ch in guild.text_channels:
                if ch.name == ticket_channel_name or (ch.topic and f"(ID: {user.id})" in ch.topic and ch.name.startswith("apply-")):
                    await interaction.followup.send(
                        f"❌ You already have an active application ticket: {ch.mention}.",
                        ephemeral=True,
                    )
                    return

            # Place inside MEMBERSHIP GATEWAY category
            gateway_cat = discord.utils.get(guild.categories, name="⁺‧₊ ✧ MEMBERSHIP GATEWAY ✧ ₊‧⁺")

            # Resolve Z.A.R.A role strictly by configured ID (Single Source of Truth)
            try:
                zara_role_id = load_zara_role_id()
            except ConfigLoadError:
                await interaction.followup.send(
                    "❌ Server configuration error: ZARA bot role is not properly configured.",
                    ephemeral=True,
                )
                return

            zara_role = guild.get_role(zara_role_id)
            if not zara_role:
                await interaction.followup.send(
                    "❌ Server configuration error: ZARA bot role not found on this server.",
                    ephemeral=True,
                )
                return

            # Explicitly grant bot permissions so least-privilege ZARA can manage the channel
            bot_overwrite = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
                add_reactions=True,
            )

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: bot_overwrite,
                zara_role: bot_overwrite,
                user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                ),
            }

            for role_name in ["Owner", "Executive", "Administrator"]:
                role = discord.utils.get(guild.roles, name=role_name)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True,
                    )

            mod_role = discord.utils.get(guild.roles, name="Moderator")
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(view_channel=False)

            try:
                ticket_channel = await guild.create_text_channel(
                    name=ticket_channel_name,
                    category=gateway_cat,
                    overwrites=overwrites,
                    topic=f"Membership interview for {user} (ID: {user.id}). Admin review only.",
                    reason=f"ZARA Application: Created for {user}",
                )

                welcome_embed = discord.Embed(
                    title=f"📋 Membership Application — {user.display_name}",
                    description=(
                        f"Welcome {user.mention}! 👋\n\n"
                        "Please answer the following standard questions so our Administrators can review your application:\n\n"
                        "1. **How did you find our server / community?**\n"
                        "2. **What games or hobbies do you enjoy?**\n"
                        "3. **Have you read and agreed to our server rules & guidelines?**\n\n"
                        "An **Administrator** will review your answers and grant you the **Verified Member** role (`/role add`). "
                        "Once verified, you will immediately gain full access to all server channels!\n\n"
                        "> ⚠️ Once finished or resolved, click the red **Close & Delete Application** button below."
                    ),
                    color=discord.Color.from_rgb(46, 204, 113),
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                )
                welcome_embed.set_thumbnail(url=user.display_avatar.url)
                welcome_embed.set_footer(text="ZARA Gatekeeper System (Admins Only)")

                await ticket_channel.send(
                    content=f"{user.mention} | Admin application review",
                    embed=welcome_embed,
                    view=CloseTicketView(),
                )

                # Log to #bot-actions-log
                actions_channel = discord.utils.get(guild.text_channels, name="bot-actions-log")
                if actions_channel:
                    log_embed = discord.Embed(
                        title="📝 Membership Application Opened",
                        color=discord.Color.green(),
                        timestamp=datetime.datetime.now(datetime.timezone.utc),
                    )
                    log_embed.add_field(name="Applicant", value=f"{user.mention} (`{user}` / ID: `{user.id}`)", inline=True)
                    log_embed.add_field(name="Channel", value=ticket_channel.mention, inline=True)
                    try:
                        await actions_channel.send(embed=log_embed)
                    except Exception:
                        pass

                await interaction.followup.send(f"✅ Your application ticket is open: {ticket_channel.mention}", ephemeral=True)

            except discord.Forbidden as e:
                await interaction.followup.send(f"❌ Bot lacks permission to create application ticket channels: {e}", ephemeral=True)
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
        self.bot.add_view(CreateApplicationTicketView())
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
