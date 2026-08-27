"""
================================================================================
ZARA - Server Events Listener Cog
================================================================================
Listens to real-time Discord gateway events (member joins/leaves, role changes,
message edits/deletions, voice activity) and posts rich embeds to #server-events-log.
================================================================================
"""

import datetime
from typing import Optional

import discord
from discord.ext import commands


class ServerEvents(commands.Cog):
    """Real-time server activity and security event monitor."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.log_channel_name = "server-events-log"

    def _get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Finds the designated server events audit log channel."""
        return discord.utils.get(guild.text_channels, name=self.log_channel_name)

    async def _send_event_embed(
        self,
        guild: discord.Guild,
        title: str,
        fields: list[tuple[str, str, bool]],
        color: discord.Color = discord.Color.blue(),
        thumbnail_url: Optional[str] = None,
        author_name: Optional[str] = None,
        author_icon_url: Optional[str] = None,
    ) -> None:
        """Helper to construct and dispatch event log embeds."""
        channel = self._get_log_channel(guild)
        if not channel:
            return

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if author_name:
            embed.set_author(name=author_name, icon_url=author_icon_url)

        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        embed.set_footer(text="ZARA Server Event Monitor")

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ==========================================================================
    # MEMBER JOIN & LEAVE
    # ==========================================================================
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        created_ts = int(member.created_at.timestamp())
        # 1. Staff Audit Log
        await self._send_event_embed(
            guild=member.guild,
            title="📥 Member Joined",
            fields=[
                ("User", f"{member.mention} (`{member}` / ID: `{member.id}`)", False),
                ("Account Created", f"<t:{created_ts}:F> (<t:{created_ts}:R>)", False),
                ("Total Members", str(member.guild.member_count), True),
            ],
            color=discord.Color.green(),
            thumbnail_url=member.display_avatar.url,
        )

        # 2. Public Welcome Greeting
        welcome_channel = (
            discord.utils.get(member.guild.text_channels, name="introductions")
            or discord.utils.get(member.guild.text_channels, name="welcome")
            or discord.utils.get(member.guild.text_channels, name="general-chat")
        )
        if welcome_channel:
            rules_channel = discord.utils.get(member.guild.text_channels, name="rules-and-guidelines")
            roles_channel = discord.utils.get(member.guild.text_channels, name="roles-assignment")
            general_channel = discord.utils.get(member.guild.text_channels, name="general-chat")

            rules_mention = rules_channel.mention if rules_channel else "#rules-and-guidelines"
            roles_mention = roles_channel.mention if roles_channel else "#roles-assignment"
            general_mention = general_channel.mention if general_channel else "#general-chat"

            welcome_embed = discord.Embed(
                title="⁺‧₊ ✧ Welcome to the Community! ✧ ₊‧⁺",
                description=(
                    f"Hey {member.mention}, welcome to **{member.guild.name}**! 🎉\n\n"
                    f"• 📜 Read through our {rules_mention} to get familiar with our rules.\n"
                    f"• 🎭 Pick up your game roles and pings in {roles_mention}.\n"
                    f"• 💬 Say hello here or jump straight into the chat in {general_mention}!\n\n"
                    f"We're glad to have you here! ✨"
                ),
                color=discord.Color.from_rgb(142, 68, 173),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            welcome_embed.set_thumbnail(url=member.display_avatar.url)
            welcome_embed.set_footer(text=f"Member #{member.guild.member_count}")

            try:
                await welcome_channel.send(content=f"Welcome {member.mention}! 👋", embed=welcome_embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        joined_ts = int(member.joined_at.timestamp()) if member.joined_at else None
        joined_str = f"<t:{joined_ts}:F> (<t:{joined_ts}:R>)" if joined_ts else "Unknown"
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        roles_str = ", ".join(roles) if roles else "None"

        await self._send_event_embed(
            guild=member.guild,
            title="📤 Member Left",
            fields=[
                ("User", f"**{member}** (`{member.id}`)", False),
                ("Joined Server", joined_str, False),
                ("Roles Held", roles_str, False),
                ("Remaining Members", str(member.guild.member_count), True),
            ],
            color=discord.Color.red(),
            thumbnail_url=member.display_avatar.url,
        )

    # ==========================================================================
    # MESSAGE EDIT & DELETE
    # ==========================================================================
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        content = message.content if message.content else "*[No text content / embed only]*"
        if len(content) > 1000:
            content = content[:997] + "..."

        fields = [
            ("Author", f"{message.author.mention} (`{message.author}` / ID: `{message.author.id}`)", True),
            ("Channel", message.channel.mention, True),
            ("Deleted Content", content, False),
        ]

        if message.attachments:
            att_names = ", ".join([f"`{a.filename}`" for a in message.attachments])
            fields.append(("Attachments", att_names, False))

        await self._send_event_embed(
            guild=message.guild,
            title="🗑️ Message Deleted",
            fields=fields,
            color=discord.Color.orange(),
            thumbnail_url=message.author.display_avatar.url,
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if not before.guild or before.author.bot or before.content == after.content:
            return

        before_content = before.content if before.content else "*[Empty]*"
        after_content = after.content if after.content else "*[Empty]*"

        if len(before_content) > 500:
            before_content = before_content[:497] + "..."
        if len(after_content) > 500:
            after_content = after_content[:497] + "..."

        await self._send_event_embed(
            guild=before.guild,
            title="✏️ Message Edited",
            fields=[
                ("Author", f"{before.author.mention} (`{before.author}`)", True),
                ("Channel", before.channel.mention, True),
                ("Jump Link", f"[View Message]({after.jump_url})", True),
                ("Before", before_content, False),
                ("After", after_content, False),
            ],
            color=discord.Color.gold(),
            thumbnail_url=before.author.display_avatar.url,
        )

    # ==========================================================================
    # MEMBER UPDATE (NICKNAMES & ROLES)
    # ==========================================================================
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        # Nickname Change
        if before.nick != after.nick:
            await self._send_event_embed(
                guild=after.guild,
                title="🏷️ Nickname Changed",
                fields=[
                    ("Member", f"{after.mention} (`{after}`)", False),
                    ("Old Nickname", before.nick or "*[None]*", True),
                    ("New Nickname", after.nick or "*[None]*", True),
                ],
                color=discord.Color.teal(),
                thumbnail_url=after.display_avatar.url,
            )

        # Role Changes
        if before.roles != after.roles:
            added_roles = [r for r in after.roles if r not in before.roles]
            removed_roles = [r for r in before.roles if r not in after.roles]

            if added_roles:
                roles_str = ", ".join([r.mention for r in added_roles])
                await self._send_event_embed(
                    guild=after.guild,
                    title="🛡️ Member Role(s) Added",
                    fields=[
                        ("Member", f"{after.mention} (`{after}`)", False),
                        ("Role(s) Added", roles_str, False),
                    ],
                    color=discord.Color.blue(),
                    thumbnail_url=after.display_avatar.url,
                )

            if removed_roles:
                roles_str = ", ".join([r.mention for r in removed_roles])
                await self._send_event_embed(
                    guild=after.guild,
                    title="🛡️ Member Role(s) Removed",
                    fields=[
                        ("Member", f"{after.mention} (`{after}`)", False),
                        ("Role(s) Removed", roles_str, False),
                    ],
                    color=discord.Color.dark_grey(),
                    thumbnail_url=after.display_avatar.url,
                )

    # ==========================================================================
    # VOICE ACTIVITY
    # ==========================================================================
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if before.channel == after.channel:
            return

        if before.channel is None and after.channel is not None:
            # Joined voice channel
            await self._send_event_embed(
                guild=member.guild,
                title="🔊 Voice Channel Joined",
                fields=[
                    ("Member", f"{member.mention} (`{member}`)", True),
                    ("Channel", after.channel.name, True),
                ],
                color=discord.Color.green(),
                thumbnail_url=member.display_avatar.url,
            )
        elif before.channel is not None and after.channel is None:
            # Left voice channel
            await self._send_event_embed(
                guild=member.guild,
                title="🔇 Voice Channel Left",
                fields=[
                    ("Member", f"{member.mention} (`{member}`)", True),
                    ("Channel", before.channel.name, True),
                ],
                color=discord.Color.red(),
                thumbnail_url=member.display_avatar.url,
            )
        elif before.channel is not None and after.channel is not None:
            # Switched voice channels
            await self._send_event_embed(
                guild=member.guild,
                title="🔀 Voice Channel Switched",
                fields=[
                    ("Member", f"{member.mention} (`{member}`)", False),
                    ("From", before.channel.name, True),
                    ("To", after.channel.name, True),
                ],
                color=discord.Color.teal(),
                thumbnail_url=member.display_avatar.url,
            )

    # ==========================================================================
    # CHANNEL LIFECYCLE
    # ==========================================================================
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        cat_name = channel.category.name if channel.category else "None (No Category)"
        await self._send_event_embed(
            guild=channel.guild,
            title="📁 Channel Created",
            fields=[
                ("Channel Name", channel.name, True),
                ("Type", str(channel.type).capitalize(), True),
                ("Category", cat_name, True),
            ],
            color=discord.Color.purple(),
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        cat_name = channel.category.name if channel.category else "None"
        await self._send_event_embed(
            guild=channel.guild,
            title="🗑️ Channel Deleted",
            fields=[
                ("Channel Name", channel.name, True),
                ("Type", str(channel.type).capitalize(), True),
                ("Category", cat_name, True),
            ],
            color=discord.Color.dark_red(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerEvents(bot))
