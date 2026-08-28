"""
================================================================================
ZARA - Security Hardening Test Suite
================================================================================
Validates authorization boundaries, self-assignable role protection,
provisioning security policies, and audit log secret redaction.
================================================================================
"""

import asyncio
import json
import os
import re
import tempfile
import unittest
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

import discord

# Import components under test
from config_loader import (
    ConfigLoadError,
    SelfAssignableRole,
    load_self_assignable_roles,
    load_zara_role_id,
)
from cogs.events import sanitize_content
from cogs.interactive import (
    DANGEROUS_PERMISSIONS,
    SELF_ASSIGNABLE_ROLE_IDS,
    SELF_ASSIGNABLE_ROLES,
    CloseTicketView,
    CreateApplicationTicketView,
    CreateTicketView,
    ticket_lock_manager,
    validate_self_assignable_role,
)
from provision import (
    PRIVILEGED_ROLE_ALLOWLIST,
    ConfigValidationError,
    validate_config,
)


class TestSecretSanitization(unittest.TestCase):
    """Tests that sensitive tokens and keys are redacted from audit log content."""

    def test_discord_bot_token_redacted(self):
        # Dynamically construct synthetic token format to test regex redaction
        part1 = "M" + "TE1MjM2MDgwODA4NzEwMTU3MA"
        part2 = "Gm" + "1aB2"
        part3 = "K9x" + "YzAbCdEfGhIjKlMnOpQrStUvWxYz01234"
        token = f"{part1}.{part2}.{part3}"
        raw_msg = f"My bot token is {token}, please don't leak it!"
        sanitized = sanitize_content(raw_msg)
        self.assertNotIn(token, sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_bearer_token_redacted(self):
        raw_msg = "Authorization: Bearer secret_api_token_1234567890abcdef"
        sanitized = sanitize_content(raw_msg)
        self.assertNotIn("secret_api_token_1234567890abcdef", sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_api_key_pattern_redacted(self):
        raw_msg = "api_key = 'abcdef1234567890abcdef1234567890'"
        sanitized = sanitize_content(raw_msg)
        self.assertNotIn("abcdef1234567890abcdef1234567890", sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_benign_message_preserved(self):
        raw_msg = "Hey guys, let's play some Valorant tonight at 8 PM!"
        sanitized = sanitize_content(raw_msg)
        self.assertEqual(sanitized, raw_msg)


class TestConfigLoader(unittest.TestCase):
    """Tests that server_structure.json acts as the Single Source of Truth for self-assignable roles."""

    def test_production_config_loads_all_roles(self):
        """Production server_structure.json loads cleanly with all 12 expected roles and immutable types."""
        roles, ids = load_self_assignable_roles()
        self.assertEqual(len(roles), 12)
        self.assertEqual(len(ids), 12)
        self.assertIn("valorant", roles)
        self.assertIn("announcements_ping", roles)
        self.assertIn("student", roles)
        self.assertIn("working", roles)
        self.assertIn("working_student", roles)
        self.assertIsInstance(ids, frozenset)

    def test_runtime_ids_match_json_config(self):
        """Proves runtime configuration directly reflects server_structure.json."""
        with open("server_structure.json", "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        sa_list = raw_data.get("self_assignable_roles", [])
        expected_ids = {entry["id"] for entry in sa_list}

        _, loaded_ids = load_self_assignable_roles()
        self.assertEqual(loaded_ids, frozenset(expected_ids))

    def test_configuration_change_alters_resolved_id(self):
        """Modifying the JSON config changes the resolved runtime role ID without changing Python code."""
        custom_config = {
            "self_assignable_roles": [
                {
                    "key": "valorant",
                    "id": 111111111111111111,
                    "name": "Valorant"
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(custom_config, f)
            temp_path = f.name

        try:
            roles, ids = load_self_assignable_roles(temp_path)
            self.assertEqual(roles["valorant"].role_id, 111111111111111111)
            self.assertIn(111111111111111111, ids)

            # Update JSON to new ID
            custom_config["self_assignable_roles"][0]["id"] = 222222222222222222
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(custom_config, f)

            # Reload reflects the new ID
            roles_updated, ids_updated = load_self_assignable_roles(temp_path)
            self.assertEqual(roles_updated["valorant"].role_id, 222222222222222222)
            self.assertIn(222222222222222222, ids_updated)
            self.assertNotIn(111111111111111111, ids_updated)
        finally:
            os.remove(temp_path)

    def test_missing_config_file_raises(self):
        """Attempting to load a nonexistent file raises ConfigLoadError."""
        with self.assertRaises(ConfigLoadError) as ctx:
            load_self_assignable_roles("nonexistent_file_path_xyz.json")
        self.assertIn("not found", str(ctx.exception).lower())

    def test_malformed_json_raises(self):
        """Malformed JSON raises ConfigLoadError."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            f.write("{ invalid json")
            temp_path = f.name

        try:
            with self.assertRaises(ConfigLoadError) as ctx:
                load_self_assignable_roles(temp_path)
            self.assertIn("Malformed JSON", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_missing_role_id_raises(self):
        """Entry with missing ID raises ConfigLoadError."""
        bad_config = {
            "self_assignable_roles": [
                {"key": "valorant", "name": "Valorant"}  # missing 'id'
            ]
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(bad_config, f)
            temp_path = f.name

        try:
            with self.assertRaises(ConfigLoadError) as ctx:
                load_self_assignable_roles(temp_path)
            self.assertIn("missing required 'id'", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_invalid_role_id_type_raises(self):
        """Entry with non-numeric or negative ID raises ConfigLoadError."""
        bad_config = {
            "self_assignable_roles": [
                {"key": "valorant", "id": "not-a-snowflake", "name": "Valorant"}
            ]
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(bad_config, f)
            temp_path = f.name

        try:
            with self.assertRaises(ConfigLoadError) as ctx:
                load_self_assignable_roles(temp_path)
            self.assertIn("invalid Discord snowflake ID", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_duplicate_role_ids_rejected(self):
        """Two self-assignable entries sharing the same Discord role ID are rejected (fail closed)."""
        bad_config = {
            "self_assignable_roles": [
                {"key": "valorant", "id": 123456789012345678, "name": "Valorant"},
                {"key": "league", "id": 123456789012345678, "name": "League of Legends"},  # Duplicate ID
            ]
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(bad_config, f)
            temp_path = f.name

        try:
            with self.assertRaises(ConfigLoadError) as ctx:
                load_self_assignable_roles(temp_path)
            self.assertIn("Duplicate Discord role ID", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_duplicate_role_keys_rejected(self):
        """Two entries with the same logical key are rejected."""
        bad_config = {
            "self_assignable_roles": [
                {"key": "valorant", "id": 111111111111111111, "name": "Valorant"},
                {"key": "valorant", "id": 222222222222222222, "name": "Valorant 2"},
            ]
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(bad_config, f)
            temp_path = f.name

        try:
            with self.assertRaises(ConfigLoadError) as ctx:
                load_self_assignable_roles(temp_path)
            self.assertIn("Duplicate self-assignable role key", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_invalid_self_assignable_boolean_type_raises(self):
        """Non-boolean 'self_assignable' value in roles array (e.g. 'yes') is rejected."""
        bad_config = {
            "roles": [
                {
                    "name": "Valorant",
                    "id": 111111111111111111,
                    "self_assignable": "yes",  # Invalid type
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(bad_config, f)
            temp_path = f.name

        try:
            with self.assertRaises(ConfigLoadError) as ctx:
                load_self_assignable_roles(temp_path)
            self.assertIn("must be a boolean", str(ctx.exception))
        finally:
            os.remove(temp_path)


class TestSelfAssignableRoleValidation(unittest.TestCase):
    """Tests that dangerous, privileged, or un-allowlisted roles cannot be self-assigned."""

    def _create_mock_role(
        self,
        name="Valorant",
        role_id=1542394615619919873,  # Default to valid allowlisted Valorant role ID
        is_default=False,
        managed=False,
        position=5,
        dangerous_perms=None,
    ):
        role = MagicMock()
        role.id = role_id
        role.name = name
        role.is_default.return_value = is_default
        role.managed = managed
        role.position = position

        # Mock permissions
        perms = MagicMock()
        for perm in DANGEROUS_PERMISSIONS:
            setattr(perms, perm, perm in (dangerous_perms or set()))
        role.permissions = perms
        return role

    def _create_mock_guild(self, bot_role_position=10):
        guild = MagicMock()
        bot_member = MagicMock()
        bot_top_role = MagicMock()
        bot_top_role.position = bot_role_position
        bot_member.top_role = bot_top_role
        guild.me = bot_member
        return guild

    def test_clean_allowlisted_role_allowed(self):
        """A configured safe role in SELF_ASSIGNABLE_ROLE_IDS is accepted."""
        role = self._create_mock_role(
            name="Valorant",
            role_id=SELF_ASSIGNABLE_ROLES["valorant"].role_id,
            position=3,
        )
        guild = self._create_mock_guild(bot_role_position=10)
        role.__ge__ = lambda self, other: self.position >= other.position

        err = validate_self_assignable_role(role, guild)
        self.assertIsNone(err)

    def test_unknown_role_id_rejected(self):
        """A role with an ID not in the explicit allowlist is rejected."""
        unlisted_role_id = 999999999999999999
        self.assertNotIn(unlisted_role_id, SELF_ASSIGNABLE_ROLE_IDS)

        role = self._create_mock_role(
            name="UnlistedRole",
            role_id=unlisted_role_id,
            position=3,
        )
        guild = self._create_mock_guild(bot_role_position=10)
        role.__ge__ = lambda self, other: self.position >= other.position

        err = validate_self_assignable_role(role, guild)
        self.assertIsNotNone(err)
        self.assertIn("not in the self-assignable allowlist", err)

    def test_same_name_spoofed_role_rejected(self):
        """If an attacker creates a role with the same name as a self-role, it is rejected by ID check."""
        legit_id = SELF_ASSIGNABLE_ROLES["valorant"].role_id
        attacker_spoofed_id = 888888888888888888

        # Attacker role has same name "Valorant", but unlisted ID
        spoofed_role = self._create_mock_role(
            name="Valorant",
            role_id=attacker_spoofed_id,
            position=3,
        )
        guild = self._create_mock_guild(bot_role_position=10)
        spoofed_role.__ge__ = lambda self, other: self.position >= other.position

        err = validate_self_assignable_role(spoofed_role, guild)
        self.assertIsNotNone(err)
        self.assertIn("not in the self-assignable allowlist", err)

        # Legitimate role with matching allowlisted ID is accepted
        legit_role = self._create_mock_role(
            name="Valorant",
            role_id=legit_id,
            position=3,
        )
        legit_role.__ge__ = lambda self, other: self.position >= other.position
        self.assertIsNone(validate_self_assignable_role(legit_role, guild))

    def test_role_id_resolution_ignores_name_collision(self):
        """Demonstrates that guild.get_role(role_id) strictly targets the configured ID."""
        guild = MagicMock()
        legit_id = SELF_ASSIGNABLE_ROLES["valorant"].role_id
        spoof_id = 777777777777777777

        role_legit = MagicMock(id=legit_id, name="Valorant")
        role_spoof = MagicMock(id=spoof_id, name="Valorant")

        # Guild contains spoof role first in role list
        guild.roles = [role_spoof, role_legit]
        guild.get_role.side_effect = lambda rid: {legit_id: role_legit, spoof_id: role_spoof}.get(rid)

        resolved_role = guild.get_role(legit_id)
        self.assertEqual(resolved_role.id, legit_id)
        self.assertEqual(resolved_role, role_legit)
        self.assertNotEqual(resolved_role, role_spoof)

    def test_configuration_mismatch_discord_name_differs(self):
        """If Discord role is renamed, ID-based resolution still accepts it because ID is the security identity."""
        legit_id = SELF_ASSIGNABLE_ROLES["valorant"].role_id
        role = self._create_mock_role(
            name="Renamed Valorant Squad",
            role_id=legit_id,
            position=3,
        )
        guild = self._create_mock_guild(bot_role_position=10)
        role.__ge__ = lambda self, other: self.position >= other.position

        err = validate_self_assignable_role(role, guild)
        self.assertIsNone(err)

    def test_missing_discord_role_rejected(self):
        """If get_role returns None (role deleted or not found), validation fails closed."""
        guild = self._create_mock_guild()
        err = validate_self_assignable_role(None, guild)
        self.assertIsNotNone(err)
        self.assertIn("not found", err)

    def test_everyone_role_rejected(self):
        """The @everyone default role must never be self-assignable."""
        role = self._create_mock_role(
            name="@everyone",
            role_id=SELF_ASSIGNABLE_ROLES["valorant"].role_id,  # Even if ID matched
            is_default=True,
        )
        guild = self._create_mock_guild()
        err = validate_self_assignable_role(role, guild)
        self.assertIsNotNone(err)
        self.assertIn("@everyone", err)

    def test_managed_integration_role_rejected(self):
        """Bot/integration/booster managed roles must never be self-assignable."""
        role = self._create_mock_role(
            name="Server Booster",
            role_id=SELF_ASSIGNABLE_ROLES["valorant"].role_id,
            managed=True,
        )
        guild = self._create_mock_guild()
        err = validate_self_assignable_role(role, guild)
        self.assertIsNotNone(err)
        self.assertIn("managed", err)

    def test_role_above_bot_rejected(self):
        """Roles positioned at or above ZARA's highest role must be rejected."""
        role = self._create_mock_role(
            name="HighRole",
            role_id=SELF_ASSIGNABLE_ROLES["valorant"].role_id,
            position=15,
        )
        guild = self._create_mock_guild(bot_role_position=10)
        role.__ge__ = lambda self, other: self.position >= other.position

        err = validate_self_assignable_role(role, guild)
        self.assertIsNotNone(err)
        self.assertIn("highest role", err)

    def test_administrator_rejected(self):
        """Administrator permission is explicitly rejected."""
        role = self._create_mock_role(
            name="AdminRole",
            role_id=SELF_ASSIGNABLE_ROLES["valorant"].role_id,
            position=3,
            dangerous_perms={"administrator"},
        )
        guild = self._create_mock_guild(bot_role_position=10)
        role.__ge__ = lambda self, other: self.position >= other.position

        err = validate_self_assignable_role(role, guild)
        self.assertIsNotNone(err)
        self.assertIn("Security Blocked", err)
        self.assertIn("administrator", err)

    def test_all_dangerous_permissions_independently_rejected(self):
        """Every permission in DANGEROUS_PERMISSIONS is independently tested and verified rejected."""
        guild = self._create_mock_guild(bot_role_position=10)

        for danger_perm in sorted(DANGEROUS_PERMISSIONS):
            with self.subTest(perm=danger_perm):
                role = self._create_mock_role(
                    name=f"ExploitRole_{danger_perm}",
                    role_id=SELF_ASSIGNABLE_ROLES["valorant"].role_id,
                    position=3,
                    dangerous_perms={danger_perm},
                )
                role.__ge__ = lambda self, other: self.position >= other.position

                err = validate_self_assignable_role(role, guild)
                self.assertIsNotNone(err, f"Permission '{danger_perm}' was not rejected!")
                self.assertIn("Security Blocked", err)
                self.assertIn(danger_perm, err)


class TestProvisioningSecurityPolicy(unittest.TestCase):
    """Tests that the provisioning validator rejects unsafe configurations."""

    def test_valid_production_config_passes(self):
        config = validate_config("server_structure.json")
        self.assertIsInstance(config, dict)
        self.assertIn("roles", config)

    def test_reject_administrator_on_non_allowlisted_role(self):
        fake_config = """
        {
            "roles": [
                {
                    "name": "Member",
                    "permissions": ["administrator"]
                }
            ],
            "categories": []
        }
        """
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            f.write(fake_config)
            temp_path = f.name

        try:
            with self.assertRaises(ConfigValidationError) as ctx:
                validate_config(temp_path)
            self.assertIn("SECURITY VIOLATION", str(ctx.exception))
            self.assertIn("Member", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_allow_administrator_on_allowlisted_role(self):
        for allowed_role in PRIVILEGED_ROLE_ALLOWLIST:
            fake_config = f"""
            {{
                "roles": [
                    {{
                        "name": "{allowed_role}",
                        "permissions": ["administrator"]
                    }}
                ],
                "categories": []
            }}
            """
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
                f.write(fake_config)
                temp_path = f.name

            try:
                config = validate_config(temp_path)
                self.assertIsInstance(config, dict)
            finally:
                os.remove(temp_path)

    def test_reject_dangerous_perms_on_everyone(self):
        fake_config = """
        {
            "roles": [
                {
                    "name": "@everyone",
                    "permissions": ["ban_members", "send_messages"]
                }
            ],
            "categories": []
        }
        """
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            f.write(fake_config)
            temp_path = f.name

        try:
            with self.assertRaises(ConfigValidationError) as ctx:
                validate_config(temp_path)
            self.assertIn("SECURITY VIOLATION", str(ctx.exception))
            self.assertIn("@everyone", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_reject_dangerous_perms_on_self_assignable_role(self):
        fake_config = """
        {
            "roles": [
                {
                    "name": "Valorant",
                    "id": 12345,
                    "self_assignable": true,
                    "permissions": ["manage_roles"]
                }
            ],
            "categories": []
        }
        """
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            f.write(fake_config)
            temp_path = f.name

        try:
            with self.assertRaises(ConfigValidationError) as ctx:
                validate_config(temp_path)
            self.assertIn("SECURITY VIOLATION", str(ctx.exception))
            self.assertIn("Self-assignable role 'Valorant'", str(ctx.exception))
            self.assertIn("manage_roles", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_reject_dangerous_perms_in_self_assignable_roles_list(self):
        fake_config = """
        {
            "roles": [
                {
                    "name": "Minecraft",
                    "id": 123456,
                    "permissions": ["ban_members"]
                }
            ],
            "self_assignable_roles": [
                {
                    "key": "minecraft",
                    "id": 123456,
                    "name": "Minecraft"
                }
            ],
            "categories": []
        }
        """
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            f.write(fake_config)
            temp_path = f.name

        try:
            with self.assertRaises(ConfigValidationError) as ctx:
                validate_config(temp_path)
            self.assertIn("SECURITY VIOLATION", str(ctx.exception))
            self.assertIn("Self-assignable role 'Minecraft'", str(ctx.exception))
            self.assertIn("ban_members", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_reject_duplicate_ids_in_provisioning_config(self):
        """validate_config catches duplicate role IDs across self-assignable definitions."""
        fake_config = """
        {
            "roles": [
                {"name": "Valorant", "id": 12345, "self_assignable": true, "permissions": []},
                {"name": "League", "id": 12345, "self_assignable": true, "permissions": []}
            ],
            "categories": []
        }
        """
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            f.write(fake_config)
            temp_path = f.name

        try:
            with self.assertRaises(ConfigValidationError) as ctx:
                validate_config(temp_path)
            self.assertIn("Duplicate Discord role ID", str(ctx.exception))
        finally:
            os.remove(temp_path)


class TestTicketTopicCreatorExtraction(unittest.TestCase):
    """Tests regex extraction of ticket creator IDs from channel topics."""

    def test_standard_ticket_topic(self):
        topic = "Private ticket created by ZerX (ID: 1542360808087101570). Closes & deletes automatically upon resolution."
        match = CloseTicketView._CREATOR_ID_PATTERN.search(topic)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), 1542360808087101570)

    def test_application_ticket_topic(self):
        topic = "Membership interview for NewApplicant (ID: 987654321098765432). Admin review only."
        match = CloseTicketView._CREATOR_ID_PATTERN.search(topic)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), 987654321098765432)

    def test_invalid_topic_yields_no_match(self):
        topic = "General discussion topic without ID tag."
        match = CloseTicketView._CREATOR_ID_PATTERN.search(topic)
        self.assertIsNone(match)


class TestZaraRoleResolution(unittest.TestCase):
    """Validates that the Z.A.R.A bot role is resolved strictly by ID from server_structure.json."""

    def test_load_zara_role_id_from_production_config(self):
        """Production server_structure.json returns the valid snowflake ID for Z.A.R.A."""
        role_id = load_zara_role_id()
        self.assertIsInstance(role_id, int)
        self.assertEqual(role_id, 1542366509517639745)

    def test_load_zara_role_id_from_custom_config(self):
        """Custom configuration with bot_role object returns the configured role ID."""
        custom_config = {
            "bot_role": {"name": "Z.A.R.A", "id": 999888777666555444},
            "roles": [],
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(custom_config, f)
            temp_path = f.name
        try:
            role_id = load_zara_role_id(temp_path)
            self.assertEqual(role_id, 999888777666555444)
        finally:
            os.remove(temp_path)

    def test_load_zara_role_id_from_roles_list_fallback(self):
        """Configuration with Z.A.R.A inside roles array returns the configured role ID."""
        custom_config = {
            "roles": [
                {"name": "Owner", "id": 111},
                {"name": "Z.A.R.A", "id": 888777666555444333},
            ],
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(custom_config, f)
            temp_path = f.name
        try:
            role_id = load_zara_role_id(temp_path)
            self.assertEqual(role_id, 888777666555444333)
        finally:
            os.remove(temp_path)

    def test_load_zara_role_id_missing_raises_config_load_error(self):
        """Missing bot role in configuration raises ConfigLoadError (fails closed)."""
        custom_config = {
            "roles": [{"name": "Owner", "id": 111}],
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(custom_config, f)
            temp_path = f.name
        try:
            with self.assertRaises(ConfigLoadError) as ctx:
                load_zara_role_id(temp_path)
            self.assertIn("Z.A.R.A bot role configuration not found", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_load_zara_role_id_invalid_type_raises(self):
        """Non-numeric ID in configuration raises ConfigLoadError."""
        custom_config = {
            "bot_role": {"name": "Z.A.R.A", "id": "invalid_not_an_id"},
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(custom_config, f)
            temp_path = f.name
        try:
            with self.assertRaises(ConfigLoadError) as ctx:
                load_zara_role_id(temp_path)
            self.assertIn("invalid Discord snowflake ID", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_no_hardcoded_zara_role_id_in_interactive_source(self):
        """Verifies interactive.py does not contain a hardcoded Z.A.R.A role ID literal."""
        with open("cogs/interactive.py", "r", encoding="utf-8") as f:
            source = f.read()

        # Ensure literal snowflake ID is not hardcoded in interactive.py
        self.assertNotIn("1542366509517639745", source)
        # Ensure no name-based resolution of Z.A.R.A
        self.assertNotIn('name="Z.A.R.A"', source)
        self.assertNotIn("name='Z.A.R.A'", source)
        # Ensure load_zara_role_id is imported and used
        self.assertIn("load_zara_role_id", source)


class TestTicketConcurrencyAndSecurity(unittest.IsolatedAsyncioTestCase):
    """Validates asyncio-based concurrency locks and ID-based security for ticket creation."""

    def _create_mock_guild_and_user(self, user_id=123456789, guild_id=987654321, user_name="testuser"):
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.text_channels = []
        guild.categories = []
        guild.roles = []
        guild.default_role = MagicMock(spec=discord.Role)

        # Bot role and member
        bot_role = MagicMock(spec=discord.Role)
        bot_role.id = 1542366509517639745
        bot_role.name = "Z.A.R.A"
        guild.roles.append(bot_role)
        guild.get_role = MagicMock(side_effect=lambda rid: bot_role if rid == 1542366509517639745 else None)

        bot_member = MagicMock(spec=discord.Member)
        bot_member.id = 1542360808087101570
        guild.me = bot_member

        user = MagicMock(spec=discord.Member)
        user.id = user_id
        user.name = user_name
        user.display_name = user_name
        user.mention = f"<@{user_id}>"

        async def mock_create_channel(name, category=None, overwrites=None, topic=None, reason=None):
            await asyncio.sleep(0.01)  # Simulate network latency
            ch = MagicMock(spec=discord.TextChannel)
            ch.name = name
            ch.topic = topic
            ch.mention = f"<#{name}>"
            ch.send = AsyncMock()
            guild.text_channels.append(ch)
            return ch

        guild.create_text_channel = AsyncMock(side_effect=mock_create_channel)
        return guild, user

    def _create_mock_interaction(self, guild, user):
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = user
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    async def test_concurrent_duplicate_support_ticket_creation(self):
        """Two concurrent ticket requests from the same user create exactly one channel."""
        guild, user = self._create_mock_guild_and_user()
        view = CreateTicketView()

        inter1 = self._create_mock_interaction(guild, user)
        inter2 = self._create_mock_interaction(guild, user)

        # Dispatch both requests concurrently
        await asyncio.gather(
            view.create_ticket.callback(inter1),
            view.create_ticket.callback(inter2),
        )

        # Exactly 1 channel created
        self.assertEqual(guild.create_text_channel.call_count, 1)
        self.assertEqual(len(guild.text_channels), 1)

        # The second interaction was rejected with existing ticket message
        inter2.followup.send.assert_called()
        call_msg = inter2.followup.send.call_args[0][0]
        self.assertIn("already have an open ticket", call_msg)

    async def test_concurrent_different_users_independent(self):
        """Two concurrent ticket requests from different users both succeed independently."""
        guild, user1 = self._create_mock_guild_and_user(user_id=11111, user_name="alice")
        _, user2 = self._create_mock_guild_and_user(user_id=22222, user_name="bob")

        view = CreateTicketView()

        inter1 = self._create_mock_interaction(guild, user1)
        inter2 = self._create_mock_interaction(guild, user2)

        await asyncio.gather(
            view.create_ticket.callback(inter1),
            view.create_ticket.callback(inter2),
        )

        # Both channels created
        self.assertEqual(guild.create_text_channel.call_count, 2)
        self.assertEqual(len(guild.text_channels), 2)

    async def test_concurrent_different_ticket_types_independent(self):
        """Same user requesting support and application tickets use independent lock keys."""
        guild, user = self._create_mock_guild_and_user()

        support_view = CreateTicketView()
        apply_view = CreateApplicationTicketView()

        inter1 = self._create_mock_interaction(guild, user)
        inter2 = self._create_mock_interaction(guild, user)

        await asyncio.gather(
            support_view.create_ticket.callback(inter1),
            apply_view.apply_ticket.callback(inter2),
        )

        # Both support and application tickets created
        self.assertEqual(guild.create_text_channel.call_count, 2)
        self.assertEqual(len(guild.text_channels), 2)
        names = {ch.name for ch in guild.text_channels}
        self.assertTrue(any(n.startswith("ticket-") for n in names))
        self.assertTrue(any(n.startswith("apply-") for n in names))

    async def test_lock_released_on_failure(self):
        """When channel creation raises an error, lock is released and subsequent request can proceed."""
        guild, user = self._create_mock_guild_and_user()
        view = CreateTicketView()

        success_ch = MagicMock(spec=discord.TextChannel)
        success_ch.name = "ticket-testuser"
        success_ch.topic = f"(ID: {user.id})"
        success_ch.send = AsyncMock()

        # First call fails with HTTPException, second succeeds
        guild.create_text_channel = AsyncMock(side_effect=[
            discord.HTTPException(MagicMock(), "Discord 500 API error"),
            success_ch,
        ])

        inter1 = self._create_mock_interaction(guild, user)
        await view.create_ticket.callback(inter1)

        inter1.followup.send.assert_called()
        self.assertIn("Discord API error", inter1.followup.send.call_args[0][0])

        # Second attempt must not be blocked by a stale lock and succeeds
        inter2 = self._create_mock_interaction(guild, user)
        await view.create_ticket.callback(inter2)

        self.assertEqual(guild.create_text_channel.call_count, 2)
        self.assertIn("Your ticket has been created", inter2.followup.send.call_args[0][0])

    async def test_ticket_lock_manager_prunes_idle_locks(self):
        """Verifies ticket_lock_manager removes lock entries from internal dict when idle."""
        guild, user = self._create_mock_guild_and_user()
        view = CreateTicketView()

        inter = self._create_mock_interaction(guild, user)
        await view.create_ticket.callback(inter)

        # After execution, the lock dictionary is pruned (no memory leak)
        key = (guild.id, user.id, "support")
        self.assertNotIn(key, ticket_lock_manager._locks)
        self.assertNotIn(key, ticket_lock_manager._counts)

    async def test_zara_role_resolved_by_id_ignoring_same_name_spoof(self):
        """Proves Z.A.R.A role is looked up by ID, ignoring an attacker's spoof role with the same name."""
        guild, user = self._create_mock_guild_and_user()
        legit_role = MagicMock(spec=discord.Role)
        legit_role.id = 1542366509517639745
        legit_role.name = "Legit Z.A.R.A"

        spoof_role = MagicMock(spec=discord.Role)
        spoof_role.id = 999999999999999999
        spoof_role.name = "Z.A.R.A"

        guild.roles = [spoof_role, legit_role]
        guild.get_role = MagicMock(side_effect=lambda rid: legit_role if rid == 1542366509517639745 else None)

        view = CreateTicketView()
        inter = self._create_mock_interaction(guild, user)

        await view.create_ticket.callback(inter)

        # Overwrites must contain legit_role (ID 1542366509517639745), not spoof_role
        created_call_kwargs = guild.create_text_channel.call_args[1]
        overwrites = created_call_kwargs["overwrites"]
        self.assertIn(legit_role, overwrites)
        self.assertNotIn(spoof_role, overwrites)

    async def test_zara_role_resolved_even_if_renamed_in_discord(self):
        """If the ZARA bot role is renamed in Discord, ID-based lookup still resolves it."""
        guild, user = self._create_mock_guild_and_user()
        renamed_role = MagicMock(spec=discord.Role)
        renamed_role.id = 1542366509517639745
        renamed_role.name = "Custom Bot Name"

        guild.roles = [renamed_role]
        guild.get_role = MagicMock(side_effect=lambda rid: renamed_role if rid == 1542366509517639745 else None)

        view = CreateTicketView()
        inter = self._create_mock_interaction(guild, user)

        await view.create_ticket.callback(inter)

        created_call_kwargs = guild.create_text_channel.call_args[1]
        overwrites = created_call_kwargs["overwrites"]
        self.assertIn(renamed_role, overwrites)

    async def test_missing_zara_role_fails_safely_without_name_fallback(self):
        """If ZARA role does not exist on Discord, ticket creation fails safely and never searches by name."""
        guild, user = self._create_mock_guild_and_user()
        guild.get_role = MagicMock(return_value=None)

        # Attacker placed a role named Z.A.R.A
        spoof_role = MagicMock(spec=discord.Role)
        spoof_role.name = "Z.A.R.A"
        guild.roles = [spoof_role]

        view = CreateTicketView()
        inter = self._create_mock_interaction(guild, user)

        await view.create_ticket.callback(inter)

        # No channel created
        self.assertEqual(guild.create_text_channel.call_count, 0)
        inter.followup.send.assert_called()
        self.assertIn("ZARA bot role not found on this server", inter.followup.send.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
