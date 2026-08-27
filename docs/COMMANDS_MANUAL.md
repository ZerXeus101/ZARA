# 📖 ZARA — Commands & Administration Manual

This manual provides an in-depth reference for all **ZARA** slash commands, permission requirements, role hierarchy constraints, and dual-channel audit logs.

---

## 📑 Table of Contents

1. [Role Hierarchy & Safety System](#-role-hierarchy--safety-system)
2. [Moderation Slash Commands](#-moderation-slash-commands)
   - [/kick](#1-kick)
   - [/ban](#2-ban)
   - [/unban](#3-unban)
   - [/timeout](#4-timeout)
   - [/untimeout](#5-untimeout)
   - [/role add](#6-role-add)
   - [/role remove](#7-role-remove)
   - [/purge](#8-purge)
   - [/slowmode](#9-slowmode)
   - [/lock](#10-lock)
   - [/unlock](#11-unlock)
3. [Utility & Diagnostic Commands](#-utility--diagnostic-commands)
   - [/ping](#12-ping)
   - [/serverinfo](#13-serverinfo)
   - [/userinfo](#14-userinfo)
   - [/help](#15-help)
4. [Dual Logging Architecture](#-dual-logging-architecture)
   - [#bot-actions-log](#1-bot-actions-log)
   - [#server-events-log](#2-server-events-log)

---

## 🛡️ Role Hierarchy & Safety System

ZARA enforces Discord's role hierarchy:

- **Self-Target Protection:** Moderators cannot moderate or ban themselves.
- **Server Owner Protection:** The Server Owner is immune to all moderation commands.
- **Bot Immunity:** ZARA will reject moderation commands targeted at itself.
- **Hierarchy Check:** A moderator cannot target a member whose highest role is **greater than or equal to** their own highest role.
- **Bot Position Check:** ZARA cannot assign or remove a role positioned **higher than or equal to** the bot's highest role.

---

## 🔨 Moderation Slash Commands

### 1. `/kick`
Removes a member from the server. The user can rejoin using an invite link.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `member` | Member | Yes | Target member to kick. |
| `reason` | String | No | Reason recorded in the audit log (default: "No reason provided."). |

- **Permission Required:** `Kick Members`
- **Audit Log:** Dispatches an embed to `#bot-actions-log`.

---

### 2. `/ban`
Permanently bans a user from the server and optionally deletes their recent message history.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `member` | Member | Yes | Target member to ban. |
| `reason` | String | No | Reason for the ban. |
| `delete_message_days` | Integer | No | Days of message history to delete (`0` to `7` days, default: `0`). |

- **Permission Required:** `Ban Members`
- **Audit Log:** Dispatches an embed to `#bot-actions-log`.

---

### 3. `/unban`
Lifts a ban for a specified Discord User ID.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `user_id` | String | Yes | Numeric Discord User ID of the banned account. |
| `reason` | String | No | Reason for the unban. |

- **Permission Required:** `Ban Members`
- **Audit Log:** Dispatches an embed to `#bot-actions-log`.

---

### 4. `/timeout`
Applies Discord's native communication timeout to a member (disabling chatting, reacting, and joining voice).

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `member` | Member | Yes | Target member to timeout. |
| `duration_minutes` | Integer | Yes | Duration in minutes (`1` to `40320` / up to 28 days). |
| `reason` | String | No | Reason for the timeout. |

- **Permission Required:** `Moderate Members` (`Timeout Members`)
- **Audit Log:** Dispatches an embed to `#bot-actions-log` with expiration timestamp.

---

### 5. `/untimeout`
Immediately clears a communication timeout from a member.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `member` | Member | Yes | Target member to restore. |
| `reason` | String | No | Reason for removing timeout. |

- **Permission Required:** `Moderate Members`
- **Audit Log:** Dispatches an embed to `#bot-actions-log`.

---

### 6. `/role add`
Assigns a server role to a target member.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `member` | Member | Yes | Member receiving the role. |
| `role` | Role | Yes | The role to assign. |
| `reason` | String | No | Reason for role assignment. |

- **Permission Required:** `Manage Roles`
- **Audit Log:** Dispatches an embed to `#bot-actions-log`.

---

### 7. `/role remove`
Removes a server role from a member.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `member` | Member | Yes | Member losing the role. |
| `role` | Role | Yes | The role to remove. |
| `reason` | String | No | Reason for role removal. |

- **Permission Required:** `Manage Roles`
- **Audit Log:** Dispatches an embed to `#bot-actions-log`.

---

### 8. `/purge`
Bulk deletes up to 100 messages from the current channel, with optional user filtering.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `amount` | Integer | Yes | Number of messages to delete (`1` to `100`). |
| `user` | Member | No | Only delete messages authored by this user. |

- **Permission Required:** `Manage Messages`
- **Audit Log:** Dispatches an embed to `#bot-actions-log` stating deleted count and filter.

---

### 9. `/slowmode`
Adjusts the slowmode rate limit for the current text channel.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `seconds` | Integer | Yes | Slowmode delay (`0` to disable, up to `21600` / 6 hours). |

- **Permission Required:** `Manage Channels`
- **Audit Log:** Dispatches an embed to `#bot-actions-log`.

---

### 10. `/lock`
Locks the current channel, preventing `@everyone` from sending messages.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `reason` | String | No | Reason for channel lockdown. |

- **Permission Required:** `Manage Channels`
- **Audit Log:** Dispatches an embed to `#bot-actions-log`.

---

### 11. `/unlock`
Unlocks the current channel, restoring message permissions for `@everyone`.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `reason` | String | No | Reason for unlocking. |

- **Permission Required:** `Manage Channels`
- **Audit Log:** Dispatches an embed to `#bot-actions-log`.

---

## 📊 Utility & Diagnostic Commands

### 12. `/ping`
Checks ZARA's WebSocket latency, system uptime, and Python runtime versions.

---

### 13. `/serverinfo`
Displays comprehensive server statistics:
- Server Owner & Guild ID
- Account Creation Date & Boost Tier
- Member Breakdown (Humans vs. Bots)
- Total Roles & Channel Breakdown (Text vs. Voice)

---

### 14. `/userinfo`
Inspects profile details for yourself or another member:
- User ID & Display Avatar
- Account Creation Date & Server Join Date
- Top Role & Full Roles List

---

### 15. `/help`
Displays a quick reference sheet linking to this manual.

---

## 📁 Dual Logging Architecture

ZARA routes audit events into two dedicated staff channels:

### 1. `#bot-actions-log`
Captures every command executed through ZARA by staff members:
- **Details Logged:** Command name, executing moderator, target user, reason, duration, and timestamp.
- **Color Coding:**
  - 🟢 **Green:** Unbans, Untimeouts, Unlocks
  - 🟡 **Gold:** Timeouts, Slowmode changes
  - 🟠 **Orange:** Kicks
  - 🔴 **Red:** Bans, Channel Locks
  - 🟣 **Purple:** Message Purges

### 2. `#server-events-log`
Real-time passive event monitor listening to the Discord Gateway:
- **Member Joins & Leaves:** Account age, join date, roles held.
- **Message Edits & Deletions:** Author, channel, deleted content diff, jump links.
- **Nickname & Role Updates:** Before vs. after state.
- **Voice Activity:** Join, leave, and switch between voice rooms.
- **Channel Lifecycle:** Channel creations and deletions.
