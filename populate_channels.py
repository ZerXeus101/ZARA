#!/usr/bin/env python3
"""
ZARA Channel Content Populator
Posts aesthetic, creative content into:
1. #rules-and-guidelines (Server rules & conduct embed)
2. #announcements (Goofy inaugural welcome announcement)
3. #roles-assignment (Interactive persistent button & dropdown role panels)
4. #create-a-ticket (Interactive support ticket creation panel)
"""

import asyncio
import datetime
import os
import sys
import discord
from dotenv import load_dotenv

# Import interactive views
from cogs.interactive import (
    NotificationRolesView,
    GameRolesView,
    LifestyleRolesView,
    CreateTicketView,
)

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))


async def populate():
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user} - Populating channel contents...")
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print("Guild not found!")
            await client.close()
            return

        # ----------------------------------------------------------------------
        # 1. #rules-and-guidelines
        # ----------------------------------------------------------------------
        rules_ch = discord.utils.get(guild.text_channels, name="rules-and-guidelines")
        if rules_ch:
            print("Populating #rules-and-guidelines...")
            # Purge previous bot messages if any
            try:
                await rules_ch.purge(limit=10, check=lambda m: m.author == client.user)
            except Exception:
                pass

            def get_mention(name: str) -> str:
                c = discord.utils.get(guild.text_channels, name=name)
                return c.mention if c else f"#{name}"

            roles_m = get_mention("roles-assignment")
            intros_m = get_mention("introductions")
            general_m = get_mention("general-chat")
            tickets_m = get_mention("create-a-ticket")
            stream_m = get_mention("stream-promotions")
            clips_m = get_mention("clips-and-highlights")

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
                    f"> • Head to {roles_m} to customize your notification pings and games.\n"
                    f"> • Introduce yourself in {intros_m} and join the conversation in {general_m}!"
                ),
                color=discord.Color.from_rgb(46, 204, 113),
            )
            footer_embed.set_footer(text="ZARA Autonomous Enforcement • Enforced by Server Staff")

            await rules_ch.send(embed=banner_embed)
            await rules_ch.send(embed=rules_embed)
            await rules_ch.send(embed=footer_embed)
            print("Done #rules-and-guidelines!")

        # ----------------------------------------------------------------------
        # 2. #announcements (Goofy Announcement)
        # ----------------------------------------------------------------------
        ann_ch = discord.utils.get(guild.text_channels, name="announcements")
        if ann_ch:
            print("Populating #announcements...")
            try:
                await ann_ch.purge(limit=5, check=lambda m: m.author == client.user)
            except Exception:
                pass

            roles_m = get_mention("roles-assignment")
            ticket_m = get_mention("create-a-ticket")

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
            print("Done #announcements!")

        # ----------------------------------------------------------------------
        # 3. #roles-assignment
        # ----------------------------------------------------------------------
        roles_ch = discord.utils.get(guild.text_channels, name="roles-assignment")
        if roles_ch:
            print("Populating #roles-assignment...")
            try:
                await roles_ch.purge(limit=10, check=lambda m: m.author == client.user)
            except Exception:
                pass

            roles_header = discord.Embed(
                title="⁺‧₊˚ ཐི⋆♱⋆ཋྀ ˚₊‧⁺  SELF-ASSIGNABLE ROLES  ⁺‧₊˚ ཐི⋆♱⋆ཋྀ ˚₊‧⁺",
                description=(
                    "Customize your experience! Toggle your notification pings and game roles below.\n"
                    "Clicking a button or selecting an option will **add/remove** the role automatically."
                ),
                color=discord.Color.from_rgb(52, 152, 219),
            )
            await roles_ch.send(embed=roles_header)

            pings_embed = discord.Embed(
                title="🔔 ⁺‧₊ ✧ Notification Pings ✧ ₊‧⁺",
                description="Click a button to toggle server pings (Never get spammed unnecessarily):",
                color=discord.Color.gold(),
            )
            await roles_ch.send(embed=pings_embed, view=NotificationRolesView())

            games_embed = discord.Embed(
                title="🎮 ⁺‧₊ ✧ Game Roles ✧ ₊‧⁺",
                description="Click the buttons below to toggle your game roles and squad pings:",
                color=discord.Color.from_rgb(231, 76, 60),
            )
            await roles_ch.send(embed=games_embed, view=GameRolesView())

            lifestyle_embed = discord.Embed(
                title="💼 ⁺‧₊ ✧ Lifestyle & Occupation ✧ ₊‧⁺",
                description="Click the buttons below to toggle your current occupation or study status:",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await roles_ch.send(embed=lifestyle_embed, view=LifestyleRolesView())
            print("Done #roles-assignment!")

        # ----------------------------------------------------------------------
        # 4. #create-a-ticket
        # ----------------------------------------------------------------------
        ticket_ch = discord.utils.get(guild.text_channels, name="create-a-ticket")
        if ticket_ch:
            print("Populating #create-a-ticket...")
            try:
                await ticket_ch.purge(limit=5, check=lambda m: m.author == client.user)
            except Exception:
                pass

            ticket_embed = discord.Embed(
                title="🎫 ⁺‧₊ ✧ Support, Inquiries & Reports ✧ ₊‧⁺",
                description=(
                    "Need assistance from staff, have a private question, or want to report a rule violation?\n\n"
                    "Click the button below to open a **Private Support Ticket**.\n\n"
                    "🔒 **Private:** Only you and the Server Administration (Owner, Executive, Admins, Mods) can view it.\n"
                    "🗑️ **Clean & Ephemeral:** When the ticket is resolved, clicking the close button will permanently delete the channel without archiving.\n\n"
                    "*Please do not open test tickets or spam the ticket button.*"
                ),
                color=discord.Color.from_rgb(155, 89, 182),
            )
            ticket_embed.set_footer(text="ZARA Autonomous Administration System")
            await ticket_ch.send(embed=ticket_embed, view=CreateTicketView())
            print("Done #create-a-ticket!")

        print("\nAll channel contents populated successfully!")
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(populate())
