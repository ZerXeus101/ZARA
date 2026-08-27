# 🔒 Privacy Policy for ZARA (ZerXeus's Autonomous Role & Administration System)

*Last Updated: August 27, 2026*

This Privacy Policy explains how **ZARA (ZerXeus's Autonomous Role & Administration System)** ("the Application", "we", "our") collects, processes, and protects information when operating within your Discord server.

We take privacy seriously and follow a strict **minimal data collection** philosophy.

---

## 1. Information We Process

To perform its moderation, auditing, and server management duties, ZARA interacts with data provided via the Discord Gateway API:

### A. Discord Identifiers
- **User IDs, Usernames, and Avatars:** Used to display member profiles, identify targets of moderation actions, and format event audit logs.
- **Server (Guild) IDs, Channel IDs, and Role IDs:** Used to route commands, verify permissions, and apply Infrastructure-as-Code (IaC) configuration.

### B. Gateway Event Data
- **Message Content & Timestamps:** Processed in real-time solely to detect message edits and deletions for `#server-events-log`.
- **Voice State Information:** Processed to log voice channel joins, leaves, and switches.
- **Role & Nickname Changes:** Processed to log administrative member updates.

---

## 2. How Information is Used

The information accessed by ZARA is used exclusively for:
1. Executing server moderation actions requested by authorized staff (e.g. kicks, bans, timeouts).
2. Posting structured, color-coded embed logs to `#bot-actions-log` and `#server-events-log` within the user's Discord server.
3. Checking and enforcing Discord role hierarchy and permission levels.
4. Responding to user slash commands (`/serverinfo`, `/userinfo`, `/ping`).

---

## 3. Data Storage & Retention

- **Zero External Database Storage:** ZARA does **NOT** store personal user data, chat histories, or telemetry on external servers, third-party databases, or cloud storage buckets.
- **In-Server Audit Logs:** All moderation logs and event notifications are dispatched directly to designated channels (`#bot-actions-log` and `#server-events-log`) within your Discord server. Discord Inc. manages the retention of these channel messages in accordance with Discord's Privacy Policy.
- **Ephemeral Support Tickets:** Private support ticket channels created via ZARA (`ticket-<username>`) exist solely within Discord during the support session. Upon ticket resolution and closure by the user or staff, the entire channel is permanently deleted without archiving or external persistence.
- **Ephemeral State:** Real-time event caching in memory is strictly ephemeral and discarded upon bot restart or completion of the event handler.

---

## 4. Third-Party Sharing & Data Selling

- **We DO NOT sell, rent, monetize, or trade your personal data under any circumstances.**
- **We DO NOT share collected data with third-party advertising networks, analytics trackers, or data brokers.**
- Information is only transmitted between your Discord server and the Discord API.

---

## 5. User Rights & Data Deletion

Because ZARA does not maintain an external database of user records:
- **To delete log history:** Server administrators can clear or delete the `#bot-actions-log` and `#server-events-log` channels in Discord at any time.
- **To remove ZARA from your server:** Server administrators can kick or ban the bot from Server Settings -> Integrations / Members.

---

## 6. Security

ZARA is architected following security best practices:
- Secret keys (such as `DISCORD_BOT_TOKEN`) are managed strictly via local environment variables (`.env`) and excluded from source control.
- Docker containers run isolated processes with least-privilege configurations.

---

## 7. Updates to this Policy

We may update this Privacy Policy periodically to reflect new features or regulatory requirements. Any modifications will be committed directly to the project's documentation.

---

## 8. Contact

For inquiries regarding this Privacy Policy or ZARA's data handling practices, please open an issue on the [GitHub Repository](https://github.com/ZerXeus101/ZARA).
