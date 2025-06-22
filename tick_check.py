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

EDCD_TICK_URL = "https://tick.edcd.io/api/tick"
TICK_CACHE_FILE = "tick_cache/global_tick.json"

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)

async def fetch_tick_timestamp(session):
    try:
        async with session.get(EDCD_TICK_URL, timeout=15) as response:
            if response.status != 200:
                return None
            data = await response.text()
            return data.strip('"') if data else None
    except Exception as e:
        print(f"[ERROR] Failed to fetch EDCD tick from API: {e}")
    return None

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

async def post_tick_time():
    async with aiohttp.ClientSession() as session:
        current_tick = await fetch_tick_timestamp(session)
        if not current_tick:
            print("[ERROR] Could not fetch EDCD tick timestamp.")
            return

        last_tick = load_last_tick()
        if current_tick == last_tick:
            print("⏱️ Tick has not changed. Skipping post.")
            return

        formatted_tick = datetime.fromisoformat(current_tick.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"⏱️ New EDCD Tick detected: {formatted_tick}")

        for channel_id in CHANNEL_FACTION_MAP:
            channel = await client.fetch_channel(channel_id)
            await channel.send(f"⏱️ **Global Tick timestamp** (via EDCD): `{formatted_tick}`")

        save_tick_time(current_tick)

if __name__ == "__main__":
    print("✅ Tick Check gestartet...")

    async def main():
        await client.login(TOKEN)
        await post_tick_time()
        await client.close()

    asyncio.run(main())