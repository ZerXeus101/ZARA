"""
================================================================================
ZARA - Security Hardening Test Suite
================================================================================
Validates authorization boundaries, self-assignable role protection,
provisioning security policies, and audit log secret redaction.
================================================================================
"""

import os
import re
import tempfile
import unittest
from unittest.mock import MagicMock

# Import components under test
from cogs.events import sanitize_content
from cogs.interactive import (
    DANGEROUS_PERMISSIONS,
    CloseTicketView,
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


class TestSelfAssignableRoleValidation(unittest.TestCase):
    """Tests that dangerous or privileged roles cannot be self-assigned."""

    def _create_mock_role(
        self,
        name="TestRole",
        is_default=False,
        managed=False,
        position=5,
        dangerous_perms=None,
    ):
        role = MagicMock()
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

    def test_clean_cosmetic_role_allowed(self):
        role = self._create_mock_role(name="Valorant", position=3)
        guild = self._create_mock_guild(bot_role_position=10)
        role.__ge__ = lambda self, other: self.position >= other.position

        err = validate_self_assignable_role(role, guild)
        self.assertIsNone(err)

    def test_everyone_role_rejected(self):
        role = self._create_mock_role(name="@everyone", is_default=True)
        guild = self._create_mock_guild()
        err = validate_self_assignable_role(role, guild)
        self.assertIsNotNone(err)
        self.assertIn("@everyone", err)

    def test_managed_integration_role_rejected(self):
        role = self._create_mock_role(name="Server Booster", managed=True)
        guild = self._create_mock_guild()
        err = validate_self_assignable_role(role, guild)
        self.assertIsNotNone(err)
        self.assertIn("managed", err)

    def test_role_above_bot_rejected(self):
        role = self._create_mock_role(name="HighRole", position=15)
        guild = self._create_mock_guild(bot_role_position=10)
        role.__ge__ = lambda self, other: self.position >= other.position

        err = validate_self_assignable_role(role, guild)
        self.assertIsNotNone(err)
        self.assertIn("highest role", err)

    def test_dangerous_permission_rejected(self):
        for danger_perm in ["administrator", "ban_members", "manage_roles", "manage_channels"]:
            with self.subTest(perm=danger_perm):
                role = self._create_mock_role(
                    name="ExploitRole",
                    position=3,
                    dangerous_perms={danger_perm},
                )
                guild = self._create_mock_guild(bot_role_position=10)
                role.__ge__ = lambda self, other: self.position >= other.position

                err = validate_self_assignable_role(role, guild)
        self.assertIsNotNone(err)
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


if __name__ == "__main__":
    unittest.main()
