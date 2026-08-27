#!/usr/bin/env python3
"""
================================================================================
ZARA (ZerXeus's Autonomous Role & Administration System)
================================================================================
Production-ready, idempotent Discord server provisioning automation engine
built on discord.py. Treats Discord infrastructure as code (IaC).
================================================================================
"""

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# Enable UTF-8 encoding for standard streams on Windows if supported
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
    # Fallback to dummy styling if colorama is not yet installed
    class DummyColor:
        def __getattr__(self, name: str) -> str:
            return ""
    Fore = DummyColor()  # type: ignore
    Style = DummyColor()  # type: ignore

import discord
from dotenv import load_dotenv

# ==============================================================================
# BRANDING & LOGGING
# ==============================================================================

ZARA_BANNER = rf"""{Fore.CYAN}{Style.BRIGHT}
================================================================================
  ______         _____         _____          _____  
 |___  /   /\   |  __ \ /\    |_   _|   /\   |  __ \ 
    / /   /  \  | |__) /  \     | |    /  \  | |__) |
   / /   / /\ \ |  _  / /\ \    | |   / /\ \ |  _  / 
  / /__ / ____ \| | \ / ____ \ _| |_ / ____ \| | \ \ 
 /_____/_/    \_\_|  /_/    \_\_____/_/    \_\_|  \_\
                                                     
  ZerXeus's Autonomous Role & Administration System (IaC Engine)
  Version: 1.0.0 | Production Release
================================================================================{Style.RESET_ALL}"""


class ZaraLogger:
    """Branded, structured logger for ZARA automation operations."""

    @staticmethod
    def _timestamp() -> str:
        return time.strftime("%H:%M:%S")

    @classmethod
    def info(cls, message: str) -> None:
        print(f"{Fore.BLUE}[{cls._timestamp()}] {Fore.CYAN}[ZARA - INFO]{Style.RESET_ALL} {message}")

    @classmethod
    def success(cls, message: str) -> None:
        print(f"{Fore.BLUE}[{cls._timestamp()}] {Fore.GREEN}{Style.BRIGHT}[ZARA - SUCCESS]{Style.RESET_ALL} {message}")

    @classmethod
    def skip(cls, message: str) -> None:
        print(f"{Fore.BLUE}[{cls._timestamp()}] {Fore.MAGENTA}[ZARA - SKIP]{Style.RESET_ALL} {message}")

    @classmethod
    def warn(cls, message: str) -> None:
        print(f"{Fore.BLUE}[{cls._timestamp()}] {Fore.YELLOW}{Style.BRIGHT}[ZARA - WARN]{Style.RESET_ALL} {message}")

    @classmethod
    def error(cls, message: str) -> None:
        print(f"{Fore.BLUE}[{cls._timestamp()}] {Fore.RED}{Style.BRIGHT}[ZARA - ERROR]{Style.RESET_ALL} {message}")

    @classmethod
    def header(cls, title: str) -> None:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}>>> {title.upper()} <<<{Style.RESET_ALL}")


# ==============================================================================
# CONFIGURATION VALIDATOR & PARSER
# ==============================================================================

class ConfigValidationError(Exception):
    """Raised when server_structure.json fails structural or semantic validation."""
    pass


def parse_hex_color(hex_str: Optional[str]) -> discord.Colour:
    """Parses a hex color string into a discord.Colour instance."""
    if not hex_str:
        return discord.Colour.default()
    cleaned = hex_str.lstrip("#")
    try:
        return discord.Colour(int(cleaned, 16))
    except ValueError:
        ZaraLogger.warn(f"Invalid hex color '{hex_str}', defaulting to #000000.")
        return discord.Colour.default()


def build_permissions(perm_list: List[str]) -> discord.Permissions:
    """Converts a list of string permission names into a discord.Permissions instance."""
    valid_flags = set(discord.Permissions.VALID_FLAGS.keys())
    perm_kwargs = {}

    for flag in perm_list:
        flag_clean = flag.strip().lower()
        if flag_clean in valid_flags:
            perm_kwargs[flag_clean] = True
        else:
            ZaraLogger.warn(f"Unknown permission flag '{flag}' - skipping.")

    return discord.Permissions(**perm_kwargs)


def validate_config(config_path: str) -> Dict[str, Any]:
    """Validates the schema and values of the server_structure.json file."""
    if not os.path.exists(config_path):
        raise ConfigValidationError(f"Configuration file '{config_path}' does not exist.")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigValidationError(f"Invalid JSON syntax in '{config_path}': {e}")

    if not isinstance(config, dict):
        raise ConfigValidationError("Root configuration must be a JSON object.")

    # Validate Roles
    roles = config.get("roles", [])
    if not isinstance(roles, list):
        raise ConfigValidationError("'roles' must be an array.")

    valid_flags = set(discord.Permissions.VALID_FLAGS.keys())
    for idx, role in enumerate(roles):
        if not isinstance(role, dict) or "name" not in role:
            raise ConfigValidationError(f"Role at index {idx} must be an object with a 'name' field.")
        perms = role.get("permissions", [])
        if not isinstance(perms, list):
            raise ConfigValidationError(f"Permissions for role '{role['name']}' must be a list.")
        for p in perms:
            if p.lower() not in valid_flags:
                ZaraLogger.warn(f"Role '{role['name']}' references unknown permission flag: '{p}'")

    # Validate Categories & Channels
    categories = config.get("categories", [])
    if not isinstance(categories, list):
        raise ConfigValidationError("'categories' must be an array.")

    valid_channel_types = {"text", "voice", "stage", "announcement", "forum"}
    for c_idx, cat in enumerate(categories):
        if not isinstance(cat, dict) or "name" not in cat:
            raise ConfigValidationError(f"Category at index {c_idx} must be an object with a 'name' field.")
        channels = cat.get("channels", [])
        if not isinstance(channels, list):
            raise ConfigValidationError(f"Channels in category '{cat['name']}' must be an array.")
        for ch_idx, ch in enumerate(channels):
            if not isinstance(ch, dict) or "name" not in ch:
                raise ConfigValidationError(f"Channel at index {ch_idx} in category '{cat['name']}' must have a 'name'.")
            ch_type = ch.get("type", "text").lower()
            if ch_type not in valid_channel_types:
                raise ConfigValidationError(f"Invalid channel type '{ch_type}' in channel '{ch['name']}'.")

    return config


# ==============================================================================
# PROVISIONING ENGINE
# ==============================================================================

class ProvisioningMetrics:
    """Tracks execution statistics for the provisioning run."""

    def __init__(self) -> None:
        self.roles_created = 0
        self.roles_updated = 0
        self.roles_skipped = 0
        self.categories_created = 0
        self.categories_updated = 0
        self.categories_skipped = 0
        self.channels_created = 0
        self.channels_updated = 0
        self.channels_skipped = 0
        self.errors = 0

    def print_summary(self) -> None:
        ZaraLogger.header("Provisioning Execution Summary")
        print(f"  • {Fore.GREEN}Roles Created:{Style.RESET_ALL}      {self.roles_created}")
        print(f"  • {Fore.CYAN}Roles Updated:{Style.RESET_ALL}      {self.roles_updated}")
        print(f"  • {Fore.MAGENTA}Roles Skipped:{Style.RESET_ALL}      {self.roles_skipped}")
        print(f"  • {Fore.GREEN}Categories Created:{Style.RESET_ALL} {self.categories_created}")
        print(f"  • {Fore.CYAN}Categories Updated:{Style.RESET_ALL} {self.categories_updated}")
        print(f"  • {Fore.MAGENTA}Categories Skipped:{Style.RESET_ALL} {self.categories_skipped}")
        print(f"  • {Fore.GREEN}Channels Created:{Style.RESET_ALL}   {self.channels_created}")
        print(f"  • {Fore.CYAN}Channels Updated:{Style.RESET_ALL}   {self.channels_updated}")
        print(f"  • {Fore.MAGENTA}Channels Skipped:{Style.RESET_ALL}   {self.channels_skipped}")
        if self.errors > 0:
            print(f"  • {Fore.RED}{Style.BRIGHT}Errors Encountered:{Style.RESET_ALL} {self.errors}")
        else:
            print(f"  • {Fore.GREEN}{Style.BRIGHT}All resources synchronized with 0 errors.{Style.RESET_ALL}")
        print("=" * 80)


class ZaraProvisioner:
    """Core idempotency and orchestration engine for Discord server resources."""

    API_WRITE_DELAY = 0.5  # Asynchronous delay between API writes to avoid rate limits

    def __init__(self, guild: discord.Guild, config: Dict[str, Any], dry_run: bool = False) -> None:
        self.guild = guild
        self.config = config
        self.dry_run = dry_run
        self.metrics = ProvisioningMetrics()
        self.role_map: Dict[str, discord.Role] = {}

    async def _throttle(self) -> None:
        """Throttles API write requests to maintain stability and comply with Discord limits."""
        if not self.dry_run:
            await asyncio.sleep(self.API_WRITE_DELAY)

    async def provision_all(self) -> None:
        """Runs the end-to-end provisioning pipeline."""
        ZaraLogger.info(f"Target Guild: {Fore.WHITE}{Style.BRIGHT}{self.guild.name}{Style.RESET_ALL} (ID: {self.guild.id})")
        ZaraLogger.info(f"Execution Mode: {Fore.YELLOW}{'DRY RUN (Simulated)' if self.dry_run else 'LIVE PROVISIONING'}{Style.RESET_ALL}")

        await self.sync_roles()
        await self.sync_categories_and_channels()

    # --------------------------------------------------------------------------
    # ROLES SYNCHRONIZATION
    # --------------------------------------------------------------------------

    async def sync_roles(self) -> None:
        ZaraLogger.header("Synchronizing Roles")

        # Map existing roles
        existing_roles = {role.name: role for role in self.guild.roles}
        self.role_map = existing_roles.copy()

        desired_roles: List[Dict[str, Any]] = self.config.get("roles", [])

        # Process desired roles in order
        for role_spec in desired_roles:
            name = role_spec["name"]
            desired_color = parse_hex_color(role_spec.get("color"))
            desired_hoist = bool(role_spec.get("hoist", False))
            desired_mentionable = bool(role_spec.get("mentionable", False))
            desired_perms = build_permissions(role_spec.get("permissions", []))

            # Handle @everyone special case
            if name == "@everyone":
                everyone_role = self.guild.default_role
                self.role_map["@everyone"] = everyone_role
                if everyone_role.permissions.value != desired_perms.value:
                    if self.dry_run:
                        ZaraLogger.info(f"[DRY-RUN] Would update base permissions for @everyone")
                        self.metrics.roles_updated += 1
                    else:
                        try:
                            ZaraLogger.info(f"Updating base permissions for @everyone...")
                            await everyone_role.edit(permissions=desired_perms, reason="ZARA: Base @everyone permissions sync")
                            ZaraLogger.success(f"Updated base permissions for @everyone")
                            self.metrics.roles_updated += 1
                            await self._throttle()
                        except (discord.Forbidden, discord.HTTPException) as e:
                            ZaraLogger.error(f"Failed to update @everyone permissions: {e}")
                            self.metrics.errors += 1
                else:
                    ZaraLogger.skip(f"Role '@everyone' baseline is up to date.")
                    self.metrics.roles_skipped += 1
                continue

            # Handle standard custom roles
            if name in existing_roles:
                existing_role = existing_roles[name]
                self.role_map[name] = existing_role

                # Evaluate state diff
                needs_update = False
                update_kwargs = {}

                if existing_role.colour.value != desired_color.value:
                    update_kwargs["colour"] = desired_color
                    needs_update = True
                if existing_role.hoist != desired_hoist:
                    update_kwargs["hoist"] = desired_hoist
                    needs_update = True
                if existing_role.mentionable != desired_mentionable:
                    update_kwargs["mentionable"] = desired_mentionable
                    needs_update = True
                if existing_role.permissions.value != desired_perms.value:
                    update_kwargs["permissions"] = desired_perms
                    needs_update = True

                if needs_update:
                    if self.dry_run:
                        ZaraLogger.info(f"[DRY-RUN] Would update role '{name}' with changes: {list(update_kwargs.keys())}")
                        self.metrics.roles_updated += 1
                    else:
                        try:
                            ZaraLogger.info(f"Updating role '{name}' ({', '.join(update_kwargs.keys())})...")
                            updated_role = await existing_role.edit(
                                reason="ZARA: Synchronizing role specification",
                                **update_kwargs
                            )
                            self.role_map[name] = updated_role
                            ZaraLogger.success(f"Updated role '{name}'")
                            self.metrics.roles_updated += 1
                            await self._throttle()
                        except discord.Forbidden:
                            ZaraLogger.warn(f"Insufficient bot permissions / role hierarchy to update role '{name}'.")
                            self.metrics.errors += 1
                        except discord.HTTPException as e:
                            ZaraLogger.error(f"Discord API error updating role '{name}': {e}")
                            self.metrics.errors += 1
                else:
                    ZaraLogger.skip(f"Role '{name}' already in desired state.")
                    self.metrics.roles_skipped += 1
            else:
                # Create missing role
                if self.dry_run:
                    ZaraLogger.info(f"[DRY-RUN] Would create role '{name}' (Color: {role_spec.get('color')}, Hoist: {desired_hoist})")
                    self.metrics.roles_created += 1
                else:
                    try:
                        ZaraLogger.info(f"Creating role '{name}'...")
                        new_role = await self.guild.create_role(
                            name=name,
                            colour=desired_color,
                            hoist=desired_hoist,
                            mentionable=desired_mentionable,
                            permissions=desired_perms,
                            reason="ZARA: Provisioning new role"
                        )
                        self.role_map[name] = new_role
                        ZaraLogger.success(f"Created role '{name}' (ID: {new_role.id})")
                        self.metrics.roles_created += 1
                        await self._throttle()
                    except discord.Forbidden:
                        ZaraLogger.error(f"Bot lacks 'Manage Roles' permission to create role '{name}'.")
                        self.metrics.errors += 1
                    except discord.HTTPException as e:
                        ZaraLogger.error(f"Discord API error creating role '{name}': {e}")
                        self.metrics.errors += 1

    # --------------------------------------------------------------------------
    # CATEGORIES & CHANNELS SYNCHRONIZATION
    # --------------------------------------------------------------------------

    def _build_overwrites(self, overwrites_spec: Dict[str, Dict[str, bool]]) -> Dict[Any, discord.PermissionOverwrite]:
        """Resolves role names in overwrites specification to discord.Role objects."""
        resolved: Dict[Any, discord.PermissionOverwrite] = {}
        for target_name, perms in overwrites_spec.items():
            target_obj = None
            if target_name == "@everyone":
                target_obj = self.guild.default_role
            elif target_name in self.role_map:
                target_obj = self.role_map[target_name]
            else:
                # Try finding in guild directly
                target_obj = discord.utils.get(self.guild.roles, name=target_name)

            if target_obj is None:
                ZaraLogger.warn(f"Cannot apply permission overwrite: Role '{target_name}' not found.")
                continue

            overwrite = discord.PermissionOverwrite()
            valid_overwrite_attrs = set(discord.Permissions.VALID_FLAGS.keys())

            for perm_name, perm_val in perms.items():
                perm_clean = perm_name.strip().lower()
                if perm_clean in valid_overwrite_attrs:
                    setattr(overwrite, perm_clean, perm_val)
                else:
                    ZaraLogger.warn(f"Unknown permission overwrite flag '{perm_name}' for '{target_name}'.")

            resolved[target_obj] = overwrite

        return resolved

    async def sync_categories_and_channels(self) -> None:
        ZaraLogger.header("Synchronizing Categories & Channels")

        categories_spec: List[Dict[str, Any]] = self.config.get("categories", [])
        existing_categories = {cat.name: cat for cat in self.guild.categories}

        for cat_spec in categories_spec:
            cat_name = cat_spec["name"]
            cat_overwrites_spec = cat_spec.get("overwrites", {})
            cat_overwrites = self._build_overwrites(cat_overwrites_spec)

            category: Optional[discord.CategoryChannel] = None

            # Category Evaluation
            if cat_name in existing_categories:
                category = existing_categories[cat_name]
                ZaraLogger.skip(f"Category '{cat_name}' exists.")
                self.metrics.categories_skipped += 1

                # Update overwrites if specified and live mode
                if cat_overwrites and not self.dry_run:
                    try:
                        for target, overwrite in cat_overwrites.items():
                            current_overwrite = category.overwrites_for(target)
                            if current_overwrite != overwrite:
                                await category.set_permissions(target, overwrite=overwrite, reason="ZARA: Sync category permissions")
                                ZaraLogger.info(f"Synchronized overwrites for '{getattr(target, 'name', str(target))}' on category '{cat_name}'")
                                await self._throttle()
                    except discord.Forbidden:
                        ZaraLogger.warn(f"Lacking permission to update overwrites for category '{cat_name}'.")
                    except discord.HTTPException as e:
                        ZaraLogger.error(f"API error updating category overwrites: {e}")
            else:
                if self.dry_run:
                    ZaraLogger.info(f"[DRY-RUN] Would create category '{cat_name}'")
                    self.metrics.categories_created += 1
                else:
                    try:
                        ZaraLogger.info(f"Creating category '{cat_name}'...")
                        category = await self.guild.create_category(
                            name=cat_name,
                            overwrites=cat_overwrites,
                            reason="ZARA: Provisioning new category"
                        )
                        existing_categories[cat_name] = category
                        ZaraLogger.success(f"Created category '{cat_name}' (ID: {category.id})")
                        self.metrics.categories_created += 1
                        await self._throttle()
                    except discord.Forbidden:
                        ZaraLogger.error(f"Bot lacks 'Manage Channels' permission to create category '{cat_name}'.")
                        self.metrics.errors += 1
                        continue
                    except discord.HTTPException as e:
                        ZaraLogger.error(f"Discord API error creating category '{cat_name}': {e}")
                        self.metrics.errors += 1
                        continue

            # Channels under Category
            channels_spec: List[Dict[str, Any]] = cat_spec.get("channels", [])
            existing_channels = {}
            if category:
                for ch in category.channels:
                    existing_channels[ch.name] = ch

            for ch_spec in channels_spec:
                ch_name = ch_spec["name"]
                ch_type = ch_spec.get("type", "text").lower()
                ch_topic = ch_spec.get("topic", "")
                ch_slowmode = int(ch_spec.get("slowmode_delay", 0))
                ch_nsfw = bool(ch_spec.get("nsfw", False))
                ch_user_limit = int(ch_spec.get("user_limit", 0))
                ch_bitrate = int(ch_spec.get("bitrate", 64000))
                ch_overwrites_spec = ch_spec.get("overwrites", {})
                ch_overwrites = self._build_overwrites(ch_overwrites_spec)

                if ch_name in existing_channels:
                    existing_ch = existing_channels[ch_name]
                    needs_update = False
                    update_kwargs: Dict[str, Any] = {}

                    if isinstance(existing_ch, discord.TextChannel):
                        if ch_topic and existing_ch.topic != ch_topic:
                            update_kwargs["topic"] = ch_topic
                            needs_update = True
                        if existing_ch.slowmode_delay != ch_slowmode:
                            update_kwargs["slowmode_delay"] = ch_slowmode
                            needs_update = True
                        if existing_ch.nsfw != ch_nsfw:
                            update_kwargs["nsfw"] = ch_nsfw
                            needs_update = True
                    elif isinstance(existing_ch, discord.VoiceChannel):
                        if existing_ch.user_limit != ch_user_limit:
                            update_kwargs["user_limit"] = ch_user_limit
                            needs_update = True

                    if needs_update:
                        if self.dry_run:
                            ZaraLogger.info(f"[DRY-RUN] Would update channel '{cat_name}/{ch_name}' with {list(update_kwargs.keys())}")
                            self.metrics.channels_updated += 1
                        else:
                            try:
                                ZaraLogger.info(f"Updating channel '{cat_name}/{ch_name}' ({', '.join(update_kwargs.keys())})...")
                                await existing_ch.edit(reason="ZARA: Synchronizing channel settings", **update_kwargs)
                                ZaraLogger.success(f"Updated channel '{cat_name}/{ch_name}'")
                                self.metrics.channels_updated += 1
                                await self._throttle()
                            except discord.Forbidden:
                                ZaraLogger.warn(f"Bot lacks permissions to edit channel '{cat_name}/{ch_name}'.")
                                self.metrics.errors += 1
                            except discord.HTTPException as e:
                                ZaraLogger.error(f"API error updating channel '{cat_name}/{ch_name}': {e}")
                                self.metrics.errors += 1
                    else:
                        ZaraLogger.skip(f"Channel '{cat_name}/{ch_name}' is up to date.")
                        self.metrics.channels_skipped += 1

                    # Apply custom channel overwrites if any
                    if ch_overwrites and not self.dry_run:
                        try:
                            for target, overwrite in ch_overwrites.items():
                                await existing_ch.set_permissions(target, overwrite=overwrite, reason="ZARA: Sync channel permissions")
                                await self._throttle()
                        except (discord.Forbidden, discord.HTTPException) as e:
                            ZaraLogger.warn(f"Could not apply overwrites to '{ch_name}': {e}")

                else:
                    # Create channel
                    if self.dry_run:
                        ZaraLogger.info(f"[DRY-RUN] Would create {ch_type} channel '{cat_name}/{ch_name}'")
                        self.metrics.channels_created += 1
                    else:
                        try:
                            ZaraLogger.info(f"Creating {ch_type} channel '{cat_name}/{ch_name}'...")
                            if ch_type == "voice":
                                new_ch = await self.guild.create_voice_channel(
                                    name=ch_name,
                                    category=category,
                                    overwrites=ch_overwrites or None,
                                    user_limit=ch_user_limit if ch_user_limit > 0 else None,
                                    bitrate=min(ch_bitrate, self.guild.bitrate_limit),
                                    reason="ZARA: Provisioning new voice channel"
                                )
                            elif ch_type == "stage":
                                new_ch = await self.guild.create_stage_channel(
                                    name=ch_name,
                                    category=category,
                                    overwrites=ch_overwrites or None,
                                    topic=ch_topic or None,
                                    reason="ZARA: Provisioning new stage channel"
                                )
                            elif ch_type == "announcement":
                                new_ch = await self.guild.create_text_channel(
                                    name=ch_name,
                                    category=category,
                                    overwrites=ch_overwrites or None,
                                    topic=ch_topic or None,
                                    news=True,
                                    reason="ZARA: Provisioning new announcement channel"
                                )
                            else:  # Standard text
                                new_ch = await self.guild.create_text_channel(
                                    name=ch_name,
                                    category=category,
                                    overwrites=ch_overwrites or None,
                                    topic=ch_topic or None,
                                    slowmode_delay=ch_slowmode,
                                    nsfw=ch_nsfw,
                                    reason="ZARA: Provisioning new text channel"
                                )

                            ZaraLogger.success(f"Created channel '{cat_name}/{ch_name}' (ID: {new_ch.id})")
                            self.metrics.channels_created += 1
                            await self._throttle()
                        except discord.Forbidden:
                            ZaraLogger.error(f"Bot lacks permissions to create channel '{ch_name}'.")
                            self.metrics.errors += 1
                        except discord.HTTPException as e:
                            ZaraLogger.error(f"Discord API error creating channel '{ch_name}': {e}")
                            self.metrics.errors += 1


# ==============================================================================
# DISCORD BOT CLIENT RUNNER
# ==============================================================================

class ZaraClient(discord.Client):
    """Custom Discord Client for managing ZARA provisioning lifecycle."""

    def __init__(self, target_guild_id: int, config: Dict[str, Any], dry_run: bool = False) -> None:
        # Standard intents required for role & channel management
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True

        super().__init__(intents=intents)
        self.target_guild_id = target_guild_id
        self.config = config
        self.dry_run = dry_run
        self.exit_code = 0

    async def on_ready(self) -> None:
        ZaraLogger.success(f"Logged in as {Fore.WHITE}{Style.BRIGHT}{self.user}{Style.RESET_ALL} (ID: {self.user.id})")

        guild = self.get_guild(self.target_guild_id)
        if guild is None:
            ZaraLogger.error(
                f"Target Guild with ID '{self.target_guild_id}' not found! "
                "Ensure the bot is invited to the target server with Administrator permissions."
            )
            self.exit_code = 1
            await self.close()
            return

        try:
            provisioner = ZaraProvisioner(guild, self.config, dry_run=self.dry_run)
            await provisioner.provision_all()
            provisioner.metrics.print_summary()
            if provisioner.metrics.errors > 0:
                self.exit_code = 1
            else:
                self.exit_code = 0
        except Exception as e:
            ZaraLogger.error(f"Unexpected error during provisioning pipeline: {e}")
            self.exit_code = 1
        finally:
            ZaraLogger.info("Provisioning pipeline completed. Initiating graceful shutdown...")
            await self.close()


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================

def main() -> None:
    print(ZARA_BANNER)

    parser = argparse.ArgumentParser(
        description="ZARA - ZerXeus's Autonomous Role & Administration System (Discord IaC Provisioner)"
    )
    parser.add_argument(
        "--config", "-c",
        default="server_structure.json",
        help="Path to the JSON server structure configuration (default: server_structure.json)"
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration schema and exit without connecting to Discord."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate provisioning changes against the Discord server without making actual API writes."
    )
    args = parser.parse_args()

    # Step 1: Validate Configuration
    ZaraLogger.info(f"Loading configuration from '{args.config}'...")
    try:
        config = validate_config(args.config)
        ZaraLogger.success(f"Configuration '{args.config}' is valid and ready.")
    except ConfigValidationError as e:
        ZaraLogger.error(f"Configuration Validation Error: {e}")
        sys.exit(1)

    if args.validate_config:
        ZaraLogger.success("Configuration check passed successfully.")
        sys.exit(0)

    # Step 2: Load Environment Secrets
    load_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id_raw = os.getenv("DISCORD_GUILD_ID")

    if not token or token == "your_discord_bot_token_here":
        ZaraLogger.error("Missing or placeholder DISCORD_BOT_TOKEN in environment (.env).")
        ZaraLogger.info("Please copy .env.example to .env and set your valid bot token.")
        sys.exit(1)

    if not guild_id_raw or guild_id_raw == "123456789012345678":
        ZaraLogger.error("Missing or placeholder DISCORD_GUILD_ID in environment (.env).")
        ZaraLogger.info("Please set DISCORD_GUILD_ID to your target Discord Server ID in .env.")
        sys.exit(1)

    try:
        guild_id = int(guild_id_raw)
    except ValueError:
        ZaraLogger.error(f"DISCORD_GUILD_ID '{guild_id_raw}' must be a valid integer.")
        sys.exit(1)

    # Step 3: Run Client
    client = ZaraClient(target_guild_id=guild_id, config=config, dry_run=args.dry_run)
    try:
        client.run(token, log_handler=None)
    except discord.LoginFailure:
        ZaraLogger.error("Failed to authenticate with Discord: Invalid DISCORD_BOT_TOKEN provided.")
        sys.exit(1)
    except Exception as e:
        ZaraLogger.error(f"Fatal error during runtime: {e}")
        sys.exit(1)

    sys.exit(client.exit_code)


if __name__ == "__main__":
    main()
