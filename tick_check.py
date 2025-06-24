import os
import json
import discord
import aiohttp
import asyncio
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()

CHANNEL_FACTION_MAP = {
    1352212125300297748: "House of Saga",
    1385989063018021075: "Torval Mining Ltd"
}

SYSTEMS_TO_CHECK = ["Wolf 397", "Bast", "LP 98-132", "LHS 3447", "Sol", "Lave", "Cubeo"]
EBGS_API_BASE = "https://elitebgs.app/api/ebgs/v5/systems?name={}"
TICK_CACHE_FILE = "tick_cache/global_tick.json"

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)

async def fetch_latest_system_timestamp(session, system_name):
    try:
        async with session.get(EBGS_API_BASE.format(system_name.replace(" ", "%20")), timeout=15) as response:
            if response.status != 200:
                print(f"[ERROR] HTTP {response.status} while fetching {system_name}")
                return None, None
            data = await response.json()
            if data.get("docs") and len(data["docs"]) > 0:
                ts = data["docs"][0].get("updated_at")
                print(f"[DEBUG] {system_name} updated_at: {ts}")
                return ts, system_name
    except Exception as e:
        print(f"[ERROR] Failed to fetch system {system_name}: {repr(e)}")
    return None, None

def load_last_tick():
    if not os.path.exists(TICK_CACHE_FILE):
        return None
    try:
        with open(TICK_CACHE_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_tick")
    except Exception as e:
        print(f"[ERROR] Failed to load tick cache: {e}")
        return None

def save_tick_time(tick_time):
    os.makedirs(os.path.dirname(TICK_CACHE_FILE), exist_ok=True)
    try:
        with open(TICK_CACHE_FILE, "w") as f:
            json.dump({"last_tick": tick_time}, f)
    except Exception as e:
        print(f"[ERROR] Failed to save tick cache: {e}")

async def fetch_tick_timestamp_from_edcd(session):
    try:
        async with session.get("https://tick.edcd.io/api/tick", timeout=15) as response:
            if response.status != 200:
                print(f"[ERROR] Failed to fetch tick from EDCD: {response.status}")
                return None
            data = await response.text()
            return data.strip('"') if data else None
    except Exception as e:
        print(f"[ERROR] Exception fetching from EDCD: {e}")
        return None

async def post_tick_time():
    async with aiohttp.ClientSession() as session:
        timestamps = []
        for system in SYSTEMS_TO_CHECK:
            ts, name = await fetch_latest_system_timestamp(session, system)
            if ts:
                timestamps.append((ts, name))

        current_tick = None
        source_system = None
        used_edcd = False

        if timestamps:
            current_tick, source_system = min(timestamps)

        last_tick = load_last_tick()

        if not timestamps:
            edcd_tick = await fetch_tick_timestamp_from_edcd(session)
            if edcd_tick and edcd_tick != last_tick:
                current_tick = edcd_tick
                source_system = "EDCD"
                used_edcd = True

        if not current_tick:
            print("⏱️ No current tick timestamp. Skipping post.")
            return

        if last_tick:
            dt_current = datetime.fromisoformat(current_tick.replace("Z", "+00:00"))
            dt_last = datetime.fromisoformat(last_tick.replace("Z", "+00:00"))

            if dt_current.date() == dt_last.date():
                print("⏱️ Tick already posted for this UTC day. Skipping post.")
                return

        formatted_tick = datetime.fromisoformat(current_tick.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"⏱️ New tick detected: {formatted_tick} (via {source_system})")

        description_lines = [
            f"🕒 **Timestamp:** `{formatted_tick}`"
        ]

        if not used_edcd:
            description_lines.append(f"🌐 **First detected in:** `{source_system}`")
            description_lines.append("🔍 Detected via state change in key systems.")
        else:
            description_lines.append("📡 Tick determined via EDCD fallback.")

        description_lines.append("✨ Watch for influence shifts and system activity.")

        embed = discord.Embed(
            title="__**📡 BGS Tick Detected!**__",
            description="\n".join(description_lines),
            color=discord.Color.green()
        )
        embed.set_footer(text="Elite BGS Monitor")

        for channel_id in CHANNEL_FACTION_MAP:
            channel = await client.fetch_channel(channel_id)
            await channel.send(embed=embed)

        save_tick_time(current_tick)

if __name__ == "__main__":
    print("✅ Tick Check gestartet...")

    async def main():
        await client.login(TOKEN)
        await post_tick_time()
        await client.close()

    asyncio.run(main())
