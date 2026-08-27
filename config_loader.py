"""
================================================================================
ZARA - Central Configuration Loader & Single Source of Truth
================================================================================
Authoritative loader for server_structure.json. Supplies validated, immutable
self-assignable role mappings for both runtime bot operations (cogs/interactive.py)
and provisioning infrastructure (provision.py).
================================================================================
"""

import json
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple, Optional, Union


class SelfAssignableRole(NamedTuple):
    """Immutable representation of a configured self-assignable role."""
    key: str
    role_id: int
    name: str


class ConfigLoadError(Exception):
    """Raised when configuration fails loading, parsing, or structural validation."""
    pass


# Default path resolved safely relative to this module's directory (repository root)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "server_structure.json"


def load_self_assignable_roles(
    config_path: Optional[Union[Path, str]] = None,
) -> tuple[MappingProxyType[str, SelfAssignableRole], frozenset[int]]:
    """Load and strictly validate self-assignable roles from server_structure.json.

    Returns:
        tuple of:
          - MappingProxyType[str, SelfAssignableRole]: Immutable key -> role mapping
          - frozenset[int]: Immutable set of valid role IDs (for O(1) allowlist checks)

    Raises:
        ConfigLoadError: If file is missing, JSON is malformed, role IDs are missing/invalid,
                         or duplicate role IDs / keys are detected.
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    if not path.is_file():
        raise ConfigLoadError(f"Configuration file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigLoadError(f"Malformed JSON in configuration file '{path}': {e}")
    except Exception as e:
        raise ConfigLoadError(f"Failed to read configuration file '{path}': {e}")

    if not isinstance(data, dict):
        raise ConfigLoadError(f"Root configuration in '{path}' must be a JSON object.")

    roles_dict: dict[str, SelfAssignableRole] = {}
    seen_ids: dict[int, str] = {}  # role_id -> key to detect duplicate IDs
    seen_keys: set[str] = set()

    # Source 1: Check top-level "self_assignable_roles" array
    sa_list = data.get("self_assignable_roles")
    if isinstance(sa_list, list) and sa_list:
        for idx, entry in enumerate(sa_list):
            if not isinstance(entry, dict):
                raise ConfigLoadError(f"Entry at self_assignable_roles[{idx}] must be a JSON object.")

            key = entry.get("key")
            name = entry.get("name", "")
            raw_id = entry.get("id")

            if not key or not isinstance(key, str) or not key.strip():
                raise ConfigLoadError(f"Self-assignable role entry at index {idx} has missing or invalid 'key'.")
            key = key.strip().lower()

            if key in seen_keys:
                raise ConfigLoadError(f"Duplicate self-assignable role key '{key}' detected in configuration.")
            seen_keys.add(key)

            if raw_id is None:
                raise ConfigLoadError(f"Self-assignable role '{key}' ({name}) is missing required 'id'.")

            try:
                role_id = int(raw_id)
                if role_id <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ConfigLoadError(f"Self-assignable role '{key}' has invalid Discord snowflake ID: '{raw_id}'.")

            if role_id in seen_ids:
                raise ConfigLoadError(
                    f"Duplicate Discord role ID '{role_id}' configured for multiple self-assignable roles "
                    f"('{seen_ids[role_id]}' and '{key}'). Each self-assignable role ID must be unique."
                )
            seen_ids[role_id] = key

            roles_dict[key] = SelfAssignableRole(key=key, role_id=role_id, name=name or key)

    else:
        # Source 2: Check "roles" list with "self_assignable": true
        roles_list = data.get("roles", [])
        if not isinstance(roles_list, list):
            raise ConfigLoadError("'roles' in configuration must be a list.")

        for idx, role in enumerate(roles_list):
            if not isinstance(role, dict):
                continue

            sa_val = role.get("self_assignable")
            if sa_val is None:
                continue

            # Strict boolean check
            if not isinstance(sa_val, bool):
                raise ConfigLoadError(
                    f"Role '{role.get('name', idx)}' has invalid 'self_assignable' value: {sa_val!r} (must be a boolean True/False)."
                )

            if sa_val is True:
                name = role.get("name")
                raw_id = role.get("id")
                if not name or not isinstance(name, str):
                    raise ConfigLoadError(f"Self-assignable role at index {idx} is missing 'name'.")

                key = name.strip().lower().replace(" ", "_").replace("-", "_")
                if key in seen_keys:
                    raise ConfigLoadError(f"Duplicate self-assignable role key '{key}' derived from '{name}'.")
                seen_keys.add(key)

                if raw_id is None:
                    raise ConfigLoadError(f"Self-assignable role '{name}' is missing required 'id'.")

                try:
                    role_id = int(raw_id)
                    if role_id <= 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise ConfigLoadError(f"Self-assignable role '{name}' has invalid Discord snowflake ID: '{raw_id}'.")

                if role_id in seen_ids:
                    raise ConfigLoadError(
                        f"Duplicate Discord role ID '{role_id}' configured for multiple self-assignable roles "
                        f"('{seen_ids[role_id]}' and '{name}')."
                    )
                seen_ids[role_id] = name

                roles_dict[key] = SelfAssignableRole(key=key, role_id=role_id, name=name)

    immutable_mapping = MappingProxyType(roles_dict)
    immutable_ids = frozenset(seen_ids.keys())

    return immutable_mapping, immutable_ids
