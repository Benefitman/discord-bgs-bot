import os
import json
import discord
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
CHANNEL_IDS = [1352212125300297748, 1385989063018021075]
TICK_CACHE_FILE = "tick_cache/global_tick.json"
TICK_URL = "http://tick.infomancer.uk/galtick.json"

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
client = discord.Client(intents=intents)

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
        try:
            async with session.get(TICK_URL, timeout=15) as response:
                if response.status != 200:
                    print(f"[ERROR] Failed to fetch tick: {response.status}")
                    return
                data = await response.json()
                current_tick = data.get("lastGalaxyTick")
                if not current_tick:
                    print("[ERROR] No 'lastGalaxyTick' field in response.")
                    return
        except Exception as e:
            print(f"[ERROR] Exception while fetching tick: {e}")
            return

        # Remove trailing .000Z for display, but store full timestamp for accurate comparison
        display_tick = current_tick.replace(".000Z", "Z")

        last_tick = load_last_tick()

        if current_tick == last_tick:
            print("⏱️ Tick unchanged. Skipping post.")
            return

        print(f"⏱️ New tick detected: {current_tick}")

        embed = discord.Embed(
            title="__**📡 Tick Just Happened!**__",
            description=f"🕒 Tick just happened at **{display_tick}**.\nAnother day, another opportunity to shape the Galaxy!",
            color=discord.Color.green()
        )
        embed.set_footer(text="Elite BGS Monitor")

        for channel_id in CHANNEL_IDS:
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
