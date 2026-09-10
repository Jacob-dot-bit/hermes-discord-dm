#!/usr/bin/env python3
"""Standalone Discord presence-tracking daemon.

Discord's REST API does not expose per-member online status at all — that data only
flows through the real-time gateway (websocket) when the GUILD_PRESENCES privileged
intent is granted. This script opens its OWN gateway session (same bot token, a
second concurrent connection alongside the main Hermes Discord platform connection —
Discord allows this for a bot of this size), keeps an in-memory member/presence
cache, and periodically dumps a snapshot to disk. The discord_dm tool's
`list_online` action just reads that file — no REST call, no waiting.

Requires: GUILD_PRESENCES *and* GUILD_MEMBERS privileged intents enabled for this
bot in the Discord Developer Portal.
"""
import asyncio
import json
import os
import sys
import time

import discord

CACHE_PATH = "/opt/data/discord_presence_cache.json"
WRITE_INTERVAL_SECONDS = 15

intents = discord.Intents.default()
intents.members = True
intents.presences = True

client = discord.Client(intents=intents)


def _snapshot() -> dict:
    out = {}
    for guild in client.guilds:
        members = []
        for m in guild.members:
            if m.bot:
                continue
            members.append({
                "user_id": str(m.id),
                "username": m.name,
                "display_name": m.display_name,
                "status": str(m.status),  # "online", "idle", "dnd", "offline"
            })
        out[str(guild.id)] = {"guild_name": guild.name, "members": members}
    return out


def _write_cache() -> None:
    data = {"updated_at": time.time(), "guilds": _snapshot()}
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, CACHE_PATH)


async def _periodic_writer() -> None:
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            _write_cache()
        except Exception as e:
            print(f"presence-daemon: write failed: {e}", file=sys.stderr, flush=True)
        await asyncio.sleep(WRITE_INTERVAL_SECONDS)


@client.event
async def on_ready() -> None:
    print(f"presence-daemon: connected as {client.user} ({len(client.guilds)} guild(s))", flush=True)
    client.loop.create_task(_periodic_writer())


def main() -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("presence-daemon: DISCORD_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
