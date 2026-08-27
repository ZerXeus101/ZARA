#!/usr/bin/env python3
"""
================================================================================
ZARA - Targeted Panel Dispatcher (post_panel.py)
================================================================================
Modular utility to post or refresh specific UI panels without touching
or repopulating other channels or spamming @everyone.

Usage:
  python post_panel.py --roles        # Update only #roles-assignment
  python post_panel.py --tickets      # Update only #create-a-ticket
  python post_panel.py --rules        # Update only #rules-and-guidelines
  python post_panel.py --all          # Refresh all panels
================================================================================
"""

import argparse
import asyncio
import datetime
import os
import sys

import discord
from dotenv import load_dotenv

from cogs.interactive import NotificationRolesView, GameRolesView, CreateTicketView, CreateApplicationTicketView

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID_RAW = os.getenv("DISCORD_GUILD_ID")

if not TOKEN or not GUILD_ID_RAW:
    print("❌ Missing DISCORD_BOT_TOKEN or DISCORD_GUILD_ID in .env.")
    sys.exit(1)

GUILD_ID = int(GUILD_ID_RAW)


async def update_apply_channel(guild: discord.Guild, client: discord.Client) -> None:
    """Updates solely the #membership-application channel."""
    ch = discord.utils.get(guild.text_channels, name="membership-application")
    if not ch:
        print("❌ Channel #membership-application not found!")
        return

    print("Refreshing #membership-application...")
    try:
        await ch.purge(limit=10, check=lambda m: m.author == client.user)
    except Exception:
        pass

    apply_embed = discord.Embed(
        title="🛡️ ⁺‧₊ ✧ Community Membership Application ✧ ₊‧⁺",
        description=(
            "Welcome to **" + guild.name + "**! ✨\n\n"
            "To maintain a safe, friendly, and troll-free community, we conduct a quick **membership interview** "
            "before granting full server access.\n\n"
            "• 📝 **How it works:** Click the button below to start your private interview ticket.\n"
            "• 🔒 **Private:** Only you and the **Server Administrators** can view your application.\n"
            "• ✨ **Instant Access:** Once an administrator verifies you, the entire server will unlock automatically!\n\n"
            "*Click below to begin your interview.*"
        ),
        color=discord.Color.from_rgb(142, 68, 173),
    )
    apply_embed.set_footer(text="ZARA Autonomous Gatekeeper • Verification System")
    await ch.send(embed=apply_embed, view=CreateApplicationTicketView())
    print("✅ #membership-application panel deployed!")


async def update_roles_channel(guild: discord.Guild, client: discord.Client) -> None:
    """Updates solely the #roles-assignment channel with interactive buttons."""
    ch = discord.utils.get(guild.text_channels, name="roles-assignment")
    if not ch:
        print("❌ Channel #roles-assignment not found!")
        return

    print("Refreshing #roles-assignment...")
    try:
        await ch.purge(limit=20, check=lambda m: m.author == client.user)
    except Exception as e:
        print(f"  • Note: Purge skipped: {e}")

    # Header Embed
    roles_header = discord.Embed(
        title="⁺‧₊˚ ཐི⋆♱⋆ཋྀ ˚₊‧⁺  SELF-ASSIGNABLE ROLES  ⁺‧₊˚ ཐི⋆♱⋆ཋྀ ˚₊‧⁺",
        description=(
            "Customize your server experience! Click any button below to toggle your notification pings and game roles.\n"
            "Buttons act as instant on/off switches (Click once to add, click again to remove)."
        ),
        color=discord.Color.from_rgb(52, 152, 219),
    )
    await ch.send(embed=roles_header)

    # Notification Pings
    pings_embed = discord.Embed(
        title="🔔 ⁺‧₊ ✧ Notification Pings ✧ ₊‧⁺",
        description="Click a button to toggle server pings (Never miss important updates):",
        color=discord.Color.gold(),
    )
    await ch.send(embed=pings_embed, view=NotificationRolesView())

    # Game Roles Button Grid
    games_embed = discord.Embed(
        title="🎮 ⁺‧₊ ✧ Game Roles ✧ ₊‧⁺",
        description="Click the buttons below to toggle your games and squad pings (Select multiple):",
        color=discord.Color.from_rgb(231, 76, 60),
    )
    await ch.send(embed=games_embed, view=GameRolesView())
    print("✅ #roles-assignment updated with all notification & game buttons!")


async def update_tickets_channel(guild: discord.Guild, client: discord.Client) -> None:
    """Updates solely the #create-a-ticket channel."""
    ch = discord.utils.get(guild.text_channels, name="create-a-ticket")
    if not ch:
        print("❌ Channel #create-a-ticket not found!")
        return

    print("Refreshing #create-a-ticket...")
    try:
        await ch.purge(limit=10, check=lambda m: m.author == client.user)
    except Exception:
        pass

    ticket_embed = discord.Embed(
        title="🎫 ⁺‧₊ ✧ Support, Inquiries & Reports ✧ ₊‧⁺",
        description=(
            "Need assistance from staff, have a private question, or want to report a rule violation?\n\n"
            "Click the button below to open a **Private Support Ticket**.\n\n"
            "🔒 **Private:** Only you and Server Administration (Owner, Executive, Admins, Mods) can view it.\n"
            "🗑️ **Ephemeral:** When closed, the ticket channel is permanently deleted with zero archival.\n\n"
            "*Please do not open test tickets or spam the ticket button.*"
        ),
        color=discord.Color.from_rgb(155, 89, 182),
    )
    ticket_embed.set_footer(text="ZARA Autonomous Administration System")
    await ch.send(embed=ticket_embed, view=CreateTicketView())
    print("✅ #create-a-ticket panel refreshed!")


def ch_mention(guild: discord.Guild, name: str) -> str:
    """Returns a clickable Discord channel mention or fallback name if not found."""
    ch = discord.utils.get(guild.text_channels, name=name)
    return ch.mention if ch else f"#{name}"


async def update_rules_channel(guild: discord.Guild, client: discord.Client) -> None:
    """Updates solely the #rules-and-guidelines channel."""
    ch = discord.utils.get(guild.text_channels, name="rules-and-guidelines")
    if not ch:
        print("❌ Channel #rules-and-guidelines not found!")
        return

    print("Refreshing #rules-and-guidelines...")
    try:
        await ch.purge(limit=10, check=lambda m: m.author == client.user)
    except Exception:
        pass

    roles_m = ch_mention(guild, "roles-assignment")
    intros_m = ch_mention(guild, "introductions")
    general_m = ch_mention(guild, "general-chat")
    tickets_m = ch_mention(guild, "create-a-ticket")
    stream_m = ch_mention(guild, "stream-promotions")
    clips_m = ch_mention(guild, "clips-and-highlights")

    banner_embed = discord.Embed(
        title="⁺‧₊˚ ཐི⋆♱⋆ཋྀ ˚₊‧⁺  SERVER RULES & CODE OF CONDUCT  ⁺‧₊˚ ཐི⋆♱⋆ཋྀ ˚₊‧⁺",
        description=(
            "Welcome to **" + guild.name + "**! ✨\n"
            "We are dedicated to maintaining a chill, welcoming, and fun community for hanging out, "
            "gaming, and sharing creative moments. To keep things enjoyable for everyone, please abide by our core rules."
        ),
        color=discord.Color.from_rgb(142, 68, 173),
    )

    rules_embed = discord.Embed(
        title="📜 Official Server Guidelines",
        color=discord.Color.from_rgb(41, 128, 185),
    )
    rules_embed.add_field(
        name="1. 🤝 Respect & Decency",
        value="Treat everyone with respect. Harassment, hate speech, bullying, toxicity, excessive drama, and personal attacks are strictly prohibited.",
        inline=False,
    )
    rules_embed.add_field(
        name="2. 🔒 No Doxxing & Privacy Protection",
        value="Doxxing or sharing real-life personal information (real names, physical addresses, phone numbers, private photos, social media, or IP addresses) without explicit consent is strictly prohibited and results in an immediate permanent ban.",
        inline=False,
    )
    rules_embed.add_field(
        name="3. 🚫 No Unsolicited Advertising & No Server Partnerships",
        value="We do **not** do server partnerships, affiliate promotions, or cross-server ad exchanges. Direct-message (DM) advertising and unsolicited promo links anywhere in the server are forbidden.",
        inline=False,
    )
    rules_embed.add_field(
        name="4. 📢 Content Promotion Policy",
        value=f"You **CAN promote your own stuff** (your live streams, YouTube/TikTok videos, music, art, and clips) — but **strictly within designated channels** like {stream_m} and {clips_m}.",
        inline=False,
    )
    rules_embed.add_field(
        name="5. 🛡️ Keep it Safe for Work (SFW)",
        value="NSFW content, 18+ media, gore, illegal material, malware, and harmful links will result in an immediate permanent ban.",
        inline=False,
    )
    rules_embed.add_field(
        name="6. 🎮 Good Sportsmanship & Fair Play",
        value="No cheating, exploiting, griefing, stream-sniping, or rage-quitting toxicity in community lobbies and squad voice channels.",
        inline=False,
    )
    rules_embed.add_field(
        name="7. 🔊 Voice Channel Etiquette",
        value="Avoid loud background noise, voice changers, mic spamming, or ear-rape sounds. Respect room capacities and AFK rooms.",
        inline=False,
    )
    rules_embed.add_field(
        name="8. 👑 Staff Guidance & Support",
        value=f"Moderator decisions are final. If you have an issue, question, or rule violation report, open a private ticket in {tickets_m} rather than arguing publicly.",
        inline=False,
    )

    footer_embed = discord.Embed(
        description=(
            f"> 💡 **Next Steps:**\n"
            f"> • Head to {roles_m} to customize your notification pings and game roles.\n"
            f"> • Introduce yourself in {intros_m} and join the conversation in {general_m}!"
        ),
        color=discord.Color.from_rgb(46, 204, 113),
    )
    footer_embed.set_footer(text="ZARA Autonomous Enforcement • Enforced by Server Staff")

    await ch.send(embed=banner_embed)
    await ch.send(embed=rules_embed)
    await ch.send(embed=footer_embed)
    print("✅ #rules-and-guidelines refreshed!")


async def update_announcements_channel(guild: discord.Guild, client: discord.Client) -> None:
    """Updates solely the #announcements channel with clickable channel links."""
    ann_ch = discord.utils.get(guild.text_channels, name="announcements")
    if not ann_ch:
        print("❌ Channel #announcements not found!")
        return

    print("Refreshing #announcements...")
    try:
        await ann_ch.purge(limit=5, check=lambda m: m.author == client.user)
    except Exception:
        pass

    roles_m = ch_mention(guild, "roles-assignment")
    ticket_m = ch_mention(guild, "create-a-ticket")

    ann_embed = discord.Embed(
        title="📢 ⁺‧₊ ✧ ATTENTION CITIZENS: ZARA HAS ASSUMED CONTROL ✧ ₊‧⁺",
        description=(
            "🚨 **BREAKING NEWS:**\n\n"
            "Our digital overlord **ZARA** has officially booted up, drank 3 digital espressos, "
            "re-wired the entire server infrastructure, and refused to go to sleep.\n\n"
            "🎉 **What does this mean for you?**\n"
            "• 🎮 Squad up in the brand new game lounges without getting 429'd by Discord.\n"
            f"• 🎭 Grab your notification pings and gaming roles in {roles_m} so you stop missing gaming night.\n"
            f"• 🎟️ If something is on fire or someone steals your Minecraft diamonds, hit up {ticket_m}.\n"
            "• 🍕 Pizza is not provided, but good vibes are strictly mandatory.\n\n"
            "Welcome to the renewed community hub! Enjoy your stay or ZARA will put you in timeout for 40,320 minutes. *(Just kidding... or am I? 🤖)*"
        ),
        color=discord.Color.from_rgb(230, 126, 34),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    ann_embed.set_thumbnail(url=client.user.display_avatar.url)
    ann_embed.set_footer(text="Broadcasted by ZARA (ZerXeus Autonomous Role & Administration)")

    await ann_ch.send(content="||@everyone|| 👋", embed=ann_embed)
    print("✅ #announcements refreshed with clickable links!")


sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class ZaraPanelClient(discord.Client):
    def __init__(self, target: str) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.target = target

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (ID: {self.user.id})...", flush=True)
        guild = self.get_guild(GUILD_ID)
        if not guild:
            try:
                guild = await self.fetch_guild(GUILD_ID)
            except Exception as e:
                print(f"❌ Failed to fetch Guild ID {GUILD_ID}: {e}", flush=True)
                await self.close()
                return

        if self.target in ("apply", "all"):
            await update_apply_channel(guild, self)
        if self.target in ("roles", "all"):
            await update_roles_channel(guild, self)
        if self.target in ("tickets", "all"):
            await update_tickets_channel(guild, self)
        if self.target in ("rules", "all"):
            await update_rules_channel(guild, self)
        if self.target in ("announcements", "all"):
            await update_announcements_channel(guild, self)

        print("\n✨ Operation completed successfully.", flush=True)
        await self.close()


def main():
    parser = argparse.ArgumentParser(description="ZARA Targeted Panel Dispatcher")
    parser.add_argument("--apply", action="store_true", help="Post/refresh only #membership-application")
    parser.add_argument("--roles", action="store_true", help="Post/refresh only #roles-assignment")
    parser.add_argument("--tickets", action="store_true", help="Post/refresh only #create-a-ticket")
    parser.add_argument("--rules", action="store_true", help="Post/refresh only #rules-and-guidelines")
    parser.add_argument("--announcements", action="store_true", help="Post/refresh only #announcements")
    parser.add_argument("--all", action="store_true", help="Refresh all panels")
    args = parser.parse_args()

    target = "roles"
    if args.apply:
        target = "apply"
    elif args.tickets:
        target = "tickets"
    elif args.rules:
        target = "rules"
    elif args.announcements:
        target = "announcements"
    elif args.all:
        target = "all"
    elif args.roles:
        target = "roles"

    client = ZaraPanelClient(target=target)
    client.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
