"""
================================================================================
ZARA - Utility Cog
================================================================================
Implements general utility, diagnostic, and information slash commands.
================================================================================
"""

import datetime
import platform
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    """Utility and informational commands for ZARA."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.start_time = time.time()

    # ==========================================================================
    # PING COMMAND
    # ==========================================================================
    @app_commands.command(name="ping", description="Check bot latency and API heartbeat.")
    async def ping(self, interaction: discord.Interaction) -> None:
        ws_latency = round(self.bot.latency * 1000, 1)
        uptime_seconds = int(time.time() - self.start_time)
        uptime_str = str(datetime.timedelta(seconds=uptime_seconds))

        embed = discord.Embed(
            title="🏓 ZARA System Status",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="WebSocket Latency", value=f"`{ws_latency} ms`", inline=True)
        embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="Python Runtime", value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="discord.py", value=f"`v{discord.__version__}`", inline=True)

        embed.set_footer(text="ZARA Status Monitor")
        await interaction.response.send_message(embed=embed)

    # ==========================================================================
    # SERVERINFO COMMAND
    # ==========================================================================
    @app_commands.command(name="serverinfo", description="Display detailed server statistics and architecture info.")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if not guild:
            return

        created_ts = int(guild.created_at.timestamp())
        bots_count = sum(1 for m in guild.members if m.bot)
        humans_count = guild.member_count - bots_count if guild.member_count else 0
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        roles_count = len(guild.roles)

        embed = discord.Embed(
            title=f"📊 Server Info: {guild.name}",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="👑 Server Owner", value=f"{guild.owner.mention if guild.owner else 'Unknown'}", inline=True)
        embed.add_field(name="🆔 Guild ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="📅 Created On", value=f"<t:{created_ts}:D> (<t:{created_ts}:R>)", inline=True)

        embed.add_field(name="👥 Total Members", value=f"**{guild.member_count}** ({humans_count} humans, {bots_count} bots)", inline=True)
        embed.add_field(name="📁 Categories", value=str(categories), inline=True)
        embed.add_field(name="💬 Channels", value=f"**{text_channels}** text | **{voice_channels}** voice", inline=True)

        embed.add_field(name="🛡️ Roles", value=f"**{roles_count}** roles", inline=True)
        embed.add_field(name="🚀 Boost Level", value=f"Tier {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)

        embed.set_footer(text="ZARA Server Information")
        await interaction.response.send_message(embed=embed)

    # ==========================================================================
    # USERINFO COMMAND
    # ==========================================================================
    @app_commands.command(name="userinfo", description="View user profile, roles, and account information.")
    @app_commands.describe(member="Optional member to view (defaults to yourself)")
    async def userinfo(self, interaction: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        target = member or interaction.user
        if not isinstance(target, discord.Member):
            return

        created_ts = int(target.created_at.timestamp())
        joined_ts = int(target.joined_at.timestamp()) if target.joined_at else None
        joined_str = f"<t:{joined_ts}:D> (<t:{joined_ts}:R>)" if joined_ts else "Unknown"

        roles = [r.mention for r in target.roles if r.name != "@everyone"]
        roles_str = ", ".join(roles) if roles else "None"
        if len(roles_str) > 1000:
            roles_str = f"{len(roles)} roles"

        embed = discord.Embed(
            title=f"👤 User Info: {target.display_name}",
            color=target.color if target.color.value != 0 else discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="Username", value=f"{target} (`{target.id}`)", inline=True)
        embed.add_field(name="Top Role", value=target.top_role.mention if target.top_role else "None", inline=True)
        embed.add_field(name="Account Created", value=f"<t:{created_ts}:D> (<t:{created_ts}:R>)", inline=False)
        embed.add_field(name="Joined Server", value=joined_str, inline=False)
        embed.add_field(name=f"Roles ({len(roles)})", value=roles_str, inline=False)

        embed.set_footer(text="ZARA User Profile")
        await interaction.response.send_message(embed=embed)

    # ==========================================================================
    # HELP COMMAND
    # ==========================================================================
    @app_commands.command(name="help", description="Overview of ZARA management and moderation commands.")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🛡️ ZARA Command Manual & Overview",
            description=(
                "**ZARA** (ZerXeus's Autonomous Role & Administration system) is equipped with a complete "
                "moderation suite, dual-channel event logging, and Infrastructure-as-Code automation.\n\n"
                "For the full command manual, syntax, and permission flags, refer to `docs/COMMANDS_MANUAL.md`."
            ),
            color=discord.Color.cyan(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(
            name="🔨 Moderation Commands",
            value=(
                "• `/kick [member] [reason]`\n"
                "• `/ban [member] [reason] [delete_days]`\n"
                "• `/unban [user_id] [reason]`\n"
                "• `/timeout [member] [minutes] [reason]`\n"
                "• `/untimeout [member] [reason]`\n"
                "• `/role add [member] [role]`\n"
                "• `/role remove [member] [role]`\n"
                "• `/purge [amount] [optional_user]`\n"
                "• `/slowmode [seconds]`\n"
                "• `/lock` & `/unlock`"
            ),
            inline=False,
        )
        embed.add_field(
            name="📊 Information & Utility",
            value=(
                "• `/ping`: Bot heartbeat and latency\n"
                "• `/serverinfo`: Guild stats and channel breakdown\n"
                "• `/userinfo [member]`: Member profile, join date, roles\n"
                "• `/help`: Display this command overview"
            ),
            inline=False,
        )
        embed.add_field(
            name="📁 Dual Logging Channels",
            value=(
                "• `#bot-actions-log`: Command execution audit trails\n"
                "• `#server-events-log`: Real-time gateway event streams"
            ),
            inline=False,
        )

        embed.set_footer(text="ZARA Administrator Suite")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
