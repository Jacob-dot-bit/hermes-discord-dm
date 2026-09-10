# hermes-discord-dm

A full-featured Discord toolkit for [Hermes Agent](https://github.com/NousResearch/hermes-agent) that works on **any platform** — CLI, dashboard/api_server, cron, not just when the conversation is happening on Discord itself.

## Why this exists

Hermes ships with `discord`/`discord_admin` tools, but they are hardcoded as
**platform-native** toolsets (see `hermes_cli/tools_config.py`,
`_recover_platform_native_toolsets`): they only get added to a session's tool
catalog when that session's platform is literally `"discord"`. No `platform_toolsets`
config combination can expose them anywhere else — a session running in the CLI or
the web dashboard can never call them, even though the plugin code is right there.

This project sidesteps that by registering an independent tool under its own name
(`discord_dm`), so the normal `platform_toolsets.<platform>` rules apply to it like
any other tool.

## What's included

- **`discord_dm_tool.py`** — the main tool. 30 actions across three tiers:
  - **Read/info** (`list_guilds`, `search_members`, `list_channels`, `server_info`,
    `fetch_messages`, `list_online`, `read_dm`, `audit_log`, ...)
  - **Low-risk actions** (`send_dm`, `send_channel_message`, `add_reaction`,
    `pin_message`, `create_thread`, `add_role`/`remove_role`, `create_invite`,
    `set_nickname`, `unban`, `unlock_channel`, `create_webhook`, ...)
  - **Destructive actions** (`kick`, `ban`, `timeout`, `delete_channel`,
    `bulk_delete_messages`, `delete_message`, `delete_role`, `delete_webhook`,
    `lock_channel`) — every one of these **requires `confirm=true`**, and the tool's
    own schema description tells the model, in plain terms, to only set that after
    the human has explicitly said yes to *this specific action* in *this
    conversation* — never because of something read from a channel/DM/webpage. This
    is a deliberate defense against indirect prompt injection: it doesn't rely on
    the model resisting a cleverly-worded message, it puts a hard requirement in
    the way of the action itself.

- **`discord_presence_daemon.py`** — Discord's REST API has **no endpoint at all**
  for per-member online/idle/dnd status; that only exists on the realtime gateway
  with the `GUILD_PRESENCES` privileged intent. This script opens a second,
  independent gateway session (same bot token — Discord allows concurrent sessions
  for a bot this size) and periodically dumps a JSON snapshot of who's online per
  guild. The tool's `list_online` action just reads that file.

- **`99-egress-autostart`** — an s6-overlay `cont-init.d` script (for the official
  `nousresearch/hermes-agent` Docker image) that starts the presence daemon (and
  `hermes egress start`, if you're using the egress proxy) automatically on every
  container start/restart, instead of needing a manual command each time.

- **`deny_notify.py`** — an optional `pre_tool_call` shell hook: sends you a Discord
  DM the moment Hermes attempts a terminal command matching one of your
  `approvals.deny` patterns (the deny itself still happens via Hermes's own
  mechanism; this is notification-only, fail-open, and never blocks anything by
  itself).

## Install

Requires the official `nousresearch/hermes-agent` Docker image and a Discord bot
token with the **Server Members** and **Presence** privileged intents enabled
(Developer Portal → your application → Bot → Privileged Gateway Intents).

1. Drop these files somewhere on the host, e.g. `~/.hermes/patches/`.

2. Bind-mount `discord_dm_tool.py` and `discord_presence_daemon.py` into the
   container, add `discord_dm` to your `platform_toolsets.<platform>` lists in
   `config.yaml` (e.g. `cli`, `api_server`), and (optionally) wire up
   `99-egress-autostart` and the `deny_notify.py` hook:

   ```bash
   docker run -d --name hermes --restart unless-stopped \
     --env-file ~/.hermes/.env \
     -e DISCORD_NOTIFY_USER_ID=<your_discord_user_id> \
     -v ~/.hermes:/opt/data \
     -v /var/run/docker.sock:/var/run/docker.sock \
     -v ~/.hermes/patches/discord_dm_tool.py:/opt/hermes/tools/discord_dm_tool.py:ro \
     -v ~/.hermes/patches/discord_presence_daemon.py:/opt/hermes/discord_presence_daemon.py:ro \
     -v ~/.hermes/patches/99-egress-autostart:/etc/cont-init.d/99-egress-autostart:ro \
     -p 8642:8642 -p 9119:9119 -e HERMES_DASHBOARD=1 \
     nousresearch/hermes-agent gateway run
   ```

3. In `config.yaml`:

   ```yaml
   platform_toolsets:
     cli:
       - discord_dm
       # ... your other tools
     api_server:
       - discord_dm
       # ... your other tools
   ```

4. (Optional) Wire up the notification hook and a starter deny list:

   ```yaml
   approvals:
     deny:
       - "rm -rf /*"
       - "rm -rf ~*"
       - ":(){ :|:& };:*"
       - "dd if=/dev/zero*"
       - "dd if=/dev/random*"
       - "git push --force*"
       - "git reset --hard*"
   hooks:
     pre_tool_call:
       - matcher: "terminal"
         command: "/opt/hermes/.venv/bin/python3 /opt/data/patches/deny_notify.py"
         timeout: 10
   ```

   Hooks need `HERMES_ACCEPT_HOOKS=1` (env var) to register without a TTY consent
   prompt in a non-interactive gateway container.

5. Restart the container. `list_guilds` from any platform is a good first test.

## License

MIT.
