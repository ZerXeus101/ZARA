"""
================================================================================
ZARA - Moderation Cog
================================================================================
Implements Discord slash commands for server moderation, role assignments,
channel security, and automated logging to #bot-actions-log.
================================================================================
"""

import datetime
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands


class Moderation(commands.Cog):
    """Core administrative and moderation slash commands for ZARA."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.log_channel_name = "bot-actions-log"

    def _get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Finds the designated bot actions audit log channel in the guild."""
        return discord.utils.get(guild.text_channels, name=self.log_channel_name)

    async def _send_log_embed(
        self,
        guild: discord.Guild,
        title: str,
        fields: list[tuple[str, str, bool]],
        color: discord.Color = discord.Color.red(),
        thumbnail_url: Optional[str] = None,
    ) -> None:
        """Dispatches a formatted audit log embed to #bot-actions-log."""
        channel = self._get_log_channel(guild)
        if not channel:
            return

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        embed.set_footer(text="ZARA Audit Logger", icon_url=self.bot.user.display_avatar.url if self.bot.user else None)

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    def _check_hierarchy(self, moderator: discord.Member, target: discord.Member) -> Optional[str]:
        """Verifies role hierarchy rules between moderator, target, and bot."""
        if target.id == moderator.id:
            return "You cannot perform moderation actions on yourself."
        if target.id == moderator.guild.owner_id:
            return "You cannot perform moderation actions on the Server Owner."
        if target.id == self.bot.user.id:
            return "You cannot perform moderation actions on ZARA."
        if moderator.id != moderator.guild.owner_id and target.top_role >= moderator.top_role:
            return f"Cannot moderate {target.mention}: their highest role ({target.top_role.name}) is higher than or equal to yours ({moderator.top_role.name})."
        bot_member = moderator.guild.me
        if target.top_role >= bot_member.top_role:
            return f"Cannot moderate {target.mention}: their highest role is higher than or equal to ZARA's highest role ({bot_member.top_role.name})."
        return None

    # ==========================================================================
    # KICK COMMAND
    # ==========================================================================
    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="The member to kick", reason="Reason for the kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: Optional[str] = "No reason provided.",
    ) -> None:
        if not isinstance(interaction.user, discord.Member):
            return

        hierarchy_error = self._check_hierarchy(interaction.user, member)
        if hierarchy_error:
            await interaction.response.send_message(f"❌ {hierarchy_error}", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)
        try:
            await member.kick(reason=f"{reason} (By: {interaction.user})")
            await interaction.followup.send(f"👢 Successfully kicked **{member}** (`{member.id}`). Reason: *{reason}*")

            await self._send_log_embed(
                guild=interaction.guild,
                title="👢 Member Kicked",
                fields=[
                    ("Target Member", f"{member.mention} (`{member}` / ID: `{member.id}`)", False),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", True),
                    ("Reason", reason, False),
                ],
                color=discord.Color.orange(),
                thumbnail_url=member.display_avatar.url,
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Failed to kick member: Insufficient permissions.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Discord API error: {e}", ephemeral=True)

    # ==========================================================================
    # BAN COMMAND
    # ==========================================================================
    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(
        member="The member to ban",
        reason="Reason for the ban",
        delete_message_days="Days of message history to delete (0-7)",
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: Optional[str] = "No reason provided.",
        delete_message_days: Optional[int] = 0,
    ) -> None:
        if not isinstance(interaction.user, discord.Member):
            return

        hierarchy_error = self._check_hierarchy(interaction.user, member)
        if hierarchy_error:
            await interaction.response.send_message(f"❌ {hierarchy_error}", ephemeral=True)
            return

        days = max(0, min(7, delete_message_days or 0))
        delete_seconds = days * 86400

        await interaction.response.defer(ephemeral=False)
        try:
            await member.ban(reason=f"{reason} (By: {interaction.user})", delete_message_seconds=delete_seconds)
            await interaction.followup.send(f"🔨 Successfully banned **{member}** (`{member.id}`). Reason: *{reason}*")

            await self._send_log_embed(
                guild=interaction.guild,
                title="🔨 Member Banned",
                fields=[
                    ("Target User", f"{member.mention} (`{member}` / ID: `{member.id}`)", False),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", True),
                    ("Messages Purged", f"{days} days", True),
                    ("Reason", reason, False),
                ],
                color=discord.Color.red(),
                thumbnail_url=member.display_avatar.url,
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Failed to ban member: Insufficient permissions.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Discord API error: {e}", ephemeral=True)

    # ==========================================================================
    # UNBAN COMMAND
    # ==========================================================================
    @app_commands.command(name="unban", description="Unban a user by their User ID.")
    @app_commands.describe(user_id="The Discord User ID to unban", reason="Reason for the unban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: Optional[str] = "No reason provided.",
    ) -> None:
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message("❌ Please provide a valid numeric Discord User ID.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)
        try:
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user, reason=f"{reason} (By: {interaction.user})")
            await interaction.followup.send(f"🔓 Successfully unbanned **{user}** (`{user.id}`). Reason: *{reason}*")

            await self._send_log_embed(
                guild=interaction.guild,
                title="🔓 User Unbanned",
                fields=[
                    ("Target User", f"{user.mention} (`{user}` / ID: `{user.id}`)", False),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", True),
                    ("Reason", reason, False),
                ],
                color=discord.Color.green(),
                thumbnail_url=user.display_avatar.url,
            )
        except discord.NotFound:
            await interaction.followup.send(f"❌ User ID `{user_id}` is not banned or does not exist.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Lacking 'Ban Members' permission to unban.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Discord API error: {e}", ephemeral=True)

    # ==========================================================================
    # TIMEOUT (MUTE) COMMAND
    # ==========================================================================
    @app_commands.command(name="timeout", description="Timeout (mute) a member for a duration.")
    @app_commands.describe(
        member="The member to timeout",
        duration_minutes="Duration in minutes (1 - 40320 / 28 days max)",
        reason="Reason for timeout",
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration_minutes: int,
        reason: Optional[str] = "No reason provided.",
    ) -> None:
        if not isinstance(interaction.user, discord.Member):
            return

        hierarchy_error = self._check_hierarchy(interaction.user, member)
        if hierarchy_error:
            await interaction.response.send_message(f"❌ {hierarchy_error}", ephemeral=True)
            return

        if duration_minutes < 1 or duration_minutes > 40320:
            await interaction.response.send_message("❌ Duration must be between 1 minute and 40,320 minutes (28 days).", ephemeral=True)
            return

        until = discord.utils.utcnow() + datetime.timedelta(minutes=duration_minutes)

        await interaction.response.defer(ephemeral=False)
        try:
            await member.timeout(until, reason=f"{reason} (By: {interaction.user})")
            await interaction.followup.send(
                f"⏳ Timed out **{member}** for **{duration_minutes} minutes** (until <t:{int(until.timestamp())}:R>). Reason: *{reason}*"
            )

            await self._send_log_embed(
                guild=interaction.guild,
                title="⏳ Member Timed Out",
                fields=[
                    ("Target Member", f"{member.mention} (`{member}` / ID: `{member.id}`)", False),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", True),
                    ("Duration", f"{duration_minutes} minutes", True),
                    ("Expires", f"<t:{int(until.timestamp())}:F> (<t:{int(until.timestamp())}:R>)", False),
                    ("Reason", reason, False),
                ],
                color=discord.Color.gold(),
                thumbnail_url=member.display_avatar.url,
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot lacks permission to timeout this member.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Discord API error: {e}", ephemeral=True)

    # ==========================================================================
    # UNTIMEOUT COMMAND
    # ==========================================================================
    @app_commands.command(name="untimeout", description="Remove timeout from a member.")
    @app_commands.describe(member="The member to remove timeout from", reason="Reason for removing timeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: Optional[str] = "Timeout removed by moderator.",
    ) -> None:
        if not member.is_timed_out():
            await interaction.response.send_message(f"ℹ️ **{member}** is not currently timed out.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)
        try:
            await member.timeout(None, reason=f"{reason} (By: {interaction.user})")
            await interaction.followup.send(f"🔊 Removed timeout for **{member}**. Reason: *{reason}*")

            await self._send_log_embed(
                guild=interaction.guild,
                title="🔊 Member Timeout Removed",
                fields=[
                    ("Target Member", f"{member.mention} (`{member}` / ID: `{member.id}`)", False),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", True),
                    ("Reason", reason, False),
                ],
                color=discord.Color.green(),
                thumbnail_url=member.display_avatar.url,
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot lacks permission to remove timeout.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Discord API error: {e}", ephemeral=True)

    # ==========================================================================
    # ROLE MANAGEMENT COMMANDS (GROUP)
    # ==========================================================================
    role_group = app_commands.Group(name="role", description="Manage member roles.")

    @role_group.command(name="add", description="Add a role to a member.")
    @app_commands.describe(member="The target member", role="The role to assign", reason="Reason for role assignment")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        reason: Optional[str] = "Role assigned via ZARA.",
    ) -> None:
        if not isinstance(interaction.user, discord.Member):
            return

        if role in member.roles:
            await interaction.response.send_message(f"ℹ️ {member.mention} already has the {role.mention} role.", ephemeral=True)
            return

        # Check moderator hierarchy against assigned role
        if interaction.user.id != interaction.guild.owner_id and role >= interaction.user.top_role:
            await interaction.response.send_message(
                f"❌ You cannot assign {role.mention} because it is higher than or equal to your highest role ({interaction.user.top_role.name}).",
                ephemeral=True,
            )
            return

        # Check bot hierarchy
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                f"❌ Cannot assign {role.mention}: it is higher than or equal to ZARA's highest role ({interaction.guild.me.top_role.name}).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=False)
        try:
            await member.add_roles(role, reason=f"{reason} (By: {interaction.user})")
            await interaction.followup.send(f"✅ Added {role.mention} to **{member}**.")

            await self._send_log_embed(
                guild=interaction.guild,
                title="🛡️ Role Assigned",
                fields=[
                    ("Target Member", f"{member.mention} (`{member}` / ID: `{member.id}`)", False),
                    ("Role Added", f"{role.mention} (`{role.name}`)", True),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", True),
                    ("Reason", reason, False),
                ],
                color=discord.Color.blue(),
                thumbnail_url=member.display_avatar.url,
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot lacks permission to assign this role.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Discord API error: {e}", ephemeral=True)

    @role_group.command(name="remove", description="Remove a role from a member.")
    @app_commands.describe(member="The target member", role="The role to remove", reason="Reason for role removal")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        reason: Optional[str] = "Role removed via ZARA.",
    ) -> None:
        if not isinstance(interaction.user, discord.Member):
            return

        if role not in member.roles:
            await interaction.response.send_message(f"ℹ️ {member.mention} does not possess the {role.mention} role.", ephemeral=True)
            return

        if interaction.user.id != interaction.guild.owner_id and role >= interaction.user.top_role:
            await interaction.response.send_message(
                f"❌ You cannot remove {role.mention} because it is higher than or equal to your highest role.",
                ephemeral=True,
            )
            return

        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                f"❌ Cannot remove {role.mention}: it is higher than or equal to ZARA's highest role.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=False)
        try:
            await member.remove_roles(role, reason=f"{reason} (By: {interaction.user})")
            await interaction.followup.send(f"✅ Removed {role.mention} from **{member}**.")

            await self._send_log_embed(
                guild=interaction.guild,
                title="🛡️ Role Removed",
                fields=[
                    ("Target Member", f"{member.mention} (`{member}` / ID: `{member.id}`)", False),
                    ("Role Removed", f"{role.mention} (`{role.name}`)", True),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", True),
                    ("Reason", reason, False),
                ],
                color=discord.Color.dark_grey(),
                thumbnail_url=member.display_avatar.url,
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot lacks permission to remove this role.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Discord API error: {e}", ephemeral=True)

    # ==========================================================================
    # PURGE (BULK DELETE) COMMAND
    # ==========================================================================
    @app_commands.command(name="purge", description="Bulk delete messages in the current channel.")
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        user="Optional user to filter messages by",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: int,
        user: Optional[discord.Member] = None,
    ) -> None:
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100 messages.", ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Purge can only be used in text channels.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        def check_msg(m: discord.Message) -> bool:
            return user is None or m.author.id == user.id

        try:
            deleted = await interaction.channel.purge(limit=amount, check=check_msg)
            count = len(deleted)
            target_str = f" from {user.mention}" if user else ""
            await interaction.followup.send(f"🧹 Purged **{count}** messages{target_str}.", ephemeral=True)

            await self._send_log_embed(
                guild=interaction.guild,
                title="🧹 Messages Purged",
                fields=[
                    ("Channel", interaction.channel.mention, True),
                    ("Messages Deleted", str(count), True),
                    ("Filtered User", user.mention if user else "None (All Users)", True),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", False),
                ],
                color=discord.Color.purple(),
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Lacking 'Manage Messages' permission.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Discord API error: {e}", ephemeral=True)

    # ==========================================================================
    # SLOWMODE COMMAND
    # ==========================================================================
    @app_commands.command(name="slowmode", description="Set slowmode rate limit for the current channel.")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable, max 21600 / 6h)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int) -> None:
        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message("❌ Seconds must be between 0 and 21,600 (6 hours).", ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Slowmode can only be applied to text channels.", ephemeral=True)
            return

        try:
            await interaction.channel.edit(slowmode_delay=seconds, reason=f"Slowmode set by {interaction.user}")
            msg = f"🐢 Slowmode disabled for {interaction.channel.mention}." if seconds == 0 else f"🐢 Slowmode for {interaction.channel.mention} set to **{seconds}s**."
            await interaction.response.send_message(msg)

            await self._send_log_embed(
                guild=interaction.guild,
                title="🐢 Slowmode Adjusted",
                fields=[
                    ("Channel", interaction.channel.mention, True),
                    ("Slowmode Delay", f"{seconds}s" if seconds > 0 else "Disabled (0s)", True),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", False),
                ],
                color=discord.Color.teal(),
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ Lacking permissions to edit channel slowmode.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ API error: {e}", ephemeral=True)

    # ==========================================================================
    # LOCK & UNLOCK COMMANDS
    # ==========================================================================
    @app_commands.command(name="lock", description="Lock the current channel (prevent @everyone from sending messages).")
    @app_commands.describe(reason="Reason for locking the channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, reason: Optional[str] = "Channel lockdown by staff.") -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Lock can only be used on text channels.", ephemeral=True)
            return

        everyone_role = interaction.guild.default_role
        overwrite = interaction.channel.overwrites_for(everyone_role)
        overwrite.send_messages = False

        try:
            await interaction.channel.set_permissions(everyone_role, overwrite=overwrite, reason=f"{reason} (By: {interaction.user})")
            await interaction.response.send_message(f"🔒 {interaction.channel.mention} has been **locked**. Reason: *{reason}*")

            await self._send_log_embed(
                guild=interaction.guild,
                title="🔒 Channel Locked",
                fields=[
                    ("Channel", interaction.channel.mention, True),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", True),
                    ("Reason", reason, False),
                ],
                color=discord.Color.dark_red(),
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ Lacking permissions to lock channel.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ API error: {e}", ephemeral=True)

    @app_commands.command(name="unlock", description="Unlock the current channel (allow @everyone to send messages).")
    @app_commands.describe(reason="Reason for unlocking the channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction, reason: Optional[str] = "Channel unlocked by staff.") -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Unlock can only be used on text channels.", ephemeral=True)
            return

        everyone_role = interaction.guild.default_role
        overwrite = interaction.channel.overwrites_for(everyone_role)
        overwrite.send_messages = None  # Neutral / Inherited from category

        try:
            await interaction.channel.set_permissions(everyone_role, overwrite=overwrite, reason=f"{reason} (By: {interaction.user})")
            await interaction.response.send_message(f"🔓 {interaction.channel.mention} has been **unlocked**. Reason: *{reason}*")

            await self._send_log_embed(
                guild=interaction.guild,
                title="🔓 Channel Unlocked",
                fields=[
                    ("Channel", interaction.channel.mention, True),
                    ("Moderator", f"{interaction.user.mention} (`{interaction.user}`)", True),
                    ("Reason", reason, False),
                ],
                color=discord.Color.green(),
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ Lacking permissions to unlock channel.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ API error: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
