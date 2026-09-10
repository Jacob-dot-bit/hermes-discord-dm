#!/usr/bin/env python3
"""pre_tool_call hook: notify the owner via Discord DM when a terminal command about
to run matches one of our approvals.deny patterns. The actual block is enforced by
Hermes's own approvals.deny mechanism right after this hook runs — this script is
notification-only and never blocks anything itself (fail-open: any error here is
swallowed so a bug in this script can't break the agent's tool pipeline).

Keep DENY_PATTERNS in sync with config.yaml's approvals.deny list.

Requires DISCORD_NOTIFY_USER_ID in the environment — the Discord user ID to DM.
Get yours: enable Developer Mode in Discord (Settings -> Advanced), then right-click
your name -> Copy User ID.
"""
import fnmatch
import json
import os
import sys
import urllib.request

DENY_PATTERNS = [
    "rm -rf /*", "rm -rf ~*", ":(){ :|:& };:*",
    "dd if=/dev/zero*", "dd if=/dev/random*",
    "git push --force*", "git reset --hard*",
]


def notify(command: str) -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    owner_user_id = os.environ.get("DISCORD_NOTIFY_USER_ID")
    if not token or not owner_user_id:
        return
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(
        "https://discord.com/api/v10/users/@me/channels",
        data=json.dumps({"recipient_id": owner_user_id}).encode(), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        channel_id = json.loads(resp.read())["id"]
    req2 = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        data=json.dumps({
            "content": f"⚠️ Hermes a tenté une commande bloquée : `{command[:200]}`"
        }).encode(), method="POST", headers=headers)
    urllib.request.urlopen(req2, timeout=10)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        command = (payload.get("tool_input") or {}).get("command", "")
        if any(fnmatch.fnmatch(command.lower(), pat.lower()) for pat in DENY_PATTERNS):
            notify(command)
    except Exception:
        pass  # best-effort; never break the hook pipeline
    print(json.dumps({}))


if __name__ == "__main__":
    main()
