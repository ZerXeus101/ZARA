#!/usr/bin/env python3
"""
================================================================================
ZARA (ZerXeus's Autonomous Role & Administration System)
================================================================================
Live 24/7 Administration & Moderation Bot Daemon
================================================================================
"""

import asyncio
import os
import sys
import time

# Enable UTF-8 encoding for standard streams on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

try:
    import colorama
    from colorama import Fore, Style
    colorama.init(autoreset=True)
except ImportError:
    class DummyColor:
        def __getattr__(self, name: str) -> str:
            return ""
    Fore = DummyColor()  # type: ignore
    Style = DummyColor()  # type: ignore

import discord
from discord.ext import commands
from dotenv import load_dotenv

ZARA_BOT_BANNER = rf"""{Fore.CYAN}{Style.BRIGHT}
================================================================================
  ______         _____         _____          _____  
 |___  /   /\   |  __ \ /\    |_   _|   /\   |  __ \ 
    / /   /  \  | |__) /  \     | |    /  \  | |__) |
   / /   / /\ \ |  _  / /\ \    | |   / /\ \ |  _  / 
  / /__ / ____ \| | \ / ____ \ _| |_ / ____ \| | \ \ 
 /_____/_/    \_\_|  /_/    \_\_____/_/    \_\_|  \_\
                                                     
  ZerXeus's Autonomous Role & Administration System
  Live 24/7 Bot Daemon & Moderation Engine | v2.0.0
================================================================================{Style.RESET_ALL}"""


class ZaraDaemon(commands.Bot):
    """Core 24/7 Discord administration bot daemon for ZARA."""

    COGS = [
        "cogs.moderation",
        "cogs.events",
        "cogs.utility",
    ]

    def __init__(self, target_guild_id: int) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix="!zara ",
            intents=intents,
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="over the server | /help",
            ),
        )
        self.target_guild_id = target_guild_id

    async def setup_hook(self) -> None:
        """Loads modular cogs and syncs application slash commands to target guild."""
        print(f"\n{Fore.CYAN}[ZARA - DAEMON]{Style.RESET_ALL} Initializing extensions and cogs...")
        for cog in self.COGS:
            try:
                await self.load_extension(cog)
                print(f"  • {Fore.GREEN}Loaded cog:{Style.RESET_ALL} {cog}")
            except Exception as e:
                print(f"  • {Fore.RED}Failed to load cog {cog}:{Style.RESET_ALL} {e}")

        # Register slash commands directly to target guild for instant availability
        guild_obj = discord.Object(id=self.target_guild_id)
        self.tree.copy_global_to(guild=guild_obj)
        try:
            synced = await self.tree.sync(guild=guild_obj)
            print(f"{Fore.GREEN}[ZARA - SUCCESS]{Style.RESET_ALL} Synced {len(synced)} slash commands to Guild ID `{self.target_guild_id}`.")
        except Exception as e:
            print(f"{Fore.RED}[ZARA - ERROR]{Style.RESET_ALL} Failed to sync slash commands: {e}")

        # Start lightweight HTTP health server if PORT is provided (for cloud hosts like Render/Railway)
        port_env = os.getenv("PORT")
        if port_env:
            try:
                port = int(port_env)
                from aiohttp import web

                async def health_handler(request: web.Request) -> web.Response:
                    return web.Response(text="ZARA Daemon is Healthy & Online 🚀", content_type="text/plain")

                app = web.Application()
                app.router.add_get("/", health_handler)
                app.router.add_get("/health", health_handler)
                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(runner, "0.0.0.0", port)
                await site.start()
                print(f"{Fore.GREEN}[ZARA - HTTP]{Style.RESET_ALL} Healthcheck web service listening on port {port}.")
            except Exception as e:
                print(f"{Fore.YELLOW}[ZARA - HTTP WARN]{Style.RESET_ALL} Could not start HTTP health server: {e}")

    async def on_ready(self) -> None:
        """Fires when bot is connected and ready."""
        guild = self.get_guild(self.target_guild_id)
        guild_name = guild.name if guild else "Unknown Guild"

        print(f"\n{Fore.GREEN}{Style.BRIGHT}[ZARA - ONLINE]{Style.RESET_ALL} Logged in as: {Fore.WHITE}{self.user}{Style.RESET_ALL} (ID: `{self.user.id}`)")
        print(f"{Fore.CYAN}[ZARA - INFO]{Style.RESET_ALL} Target Server: {Fore.WHITE}{guild_name}{Style.RESET_ALL} (ID: `{self.target_guild_id}`)")

        if guild:
            bot_log = discord.utils.get(guild.text_channels, name="bot-actions-log")
            server_log = discord.utils.get(guild.text_channels, name="server-events-log")
            print(f"{Fore.CYAN}[ZARA - LOGGERS]{Style.RESET_ALL} Bot Actions Log: {Fore.GREEN if bot_log else Fore.YELLOW}{'#' + bot_log.name if bot_log else 'NOT FOUND'}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}[ZARA - LOGGERS]{Style.RESET_ALL} Server Events Log: {Fore.GREEN if server_log else Fore.YELLOW}{'#' + server_log.name if server_log else 'NOT FOUND'}{Style.RESET_ALL}")

        print(f"{Fore.GREEN}[ZARA - READY]{Style.RESET_ALL} ZARA 24/7 daemon is actively monitoring the server.\n" + "=" * 80)


def main() -> None:
    print(ZARA_BOT_BANNER)

    load_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id_raw = os.getenv("DISCORD_GUILD_ID")

    if not token or token == "your_discord_bot_token_here":
        print(f"{Fore.RED}[ZARA - ERROR]{Style.RESET_ALL} Missing or placeholder DISCORD_BOT_TOKEN in .env.")
        sys.exit(1)

    if not guild_id_raw or guild_id_raw == "123456789012345678":
        print(f"{Fore.RED}[ZARA - ERROR]{Style.RESET_ALL} Missing or placeholder DISCORD_GUILD_ID in .env.")
        sys.exit(1)

    try:
        guild_id = int(guild_id_raw)
    except ValueError:
        print(f"{Fore.RED}[ZARA - ERROR]{Style.RESET_ALL} DISCORD_GUILD_ID must be a numeric integer.")
        sys.exit(1)

    bot = ZaraDaemon(target_guild_id=guild_id)
    try:
        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        print(f"{Fore.RED}[ZARA - ERROR]{Style.RESET_ALL} Invalid bot token provided.")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[ZARA - SHUTDOWN]{Style.RESET_ALL} Gracefully shutting down daemon...")
    except Exception as e:
        print(f"{Fore.RED}[ZARA - FATAL]{Style.RESET_ALL} Fatal runtime exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
