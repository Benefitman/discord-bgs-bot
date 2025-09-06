import os
import json
import discord
import aiohttp
import asyncio
from dotenv import load_dotenv
from datetime import datetime
import re

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
CHANNEL_IDS = [1352212125300297748, 1385989063018021075]
TICK_URL = "http://tick.infomancer.uk/galtick.json"

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True

client = discord.Client(intents=intents)

async def fetch_last_tick_from_channel(client: discord.Client, channel: discord.TextChannel) -> str | None:
    async for message in channel.history(limit=50):
        if message.author == client.user and message.embeds:
            embed = message.embeds[0]
            if embed.title and "Tick Just Happened" in embed.title:
                footer_text = embed.footer.text or ""
                match = re.search(r"ISO:\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)", footer_text)
                if match:
                    return match.group(1)
    return None

async def post_tick_time(client: discord.Client):
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

    for channel_id in CHANNEL_IDS:
        channel = await client.fetch_channel(channel_id)
        last_tick = await fetch_last_tick_from_channel(client, channel)

        print(f"[DEBUG] Channel {channel.name} last_tick: {last_tick}")
        print(f"[DEBUG] Current fetched tick: {current_tick}")

        if current_tick == last_tick:
            print(f"⏱️ Tick in {channel.name} unchanged. Skipping post.")
            continue

        try:
            dt = datetime.fromisoformat(current_tick.replace("Z", "+00:00"))
            day = dt.day
            suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
            display_tick = dt.strftime(f"%B {day}{suffix} %Y, at %H:%M")
        except Exception as e:
            display_tick = current_tick
            print(f"[WARN] Failed to format tick timestamp: {e}")

        embed = discord.Embed(
            title="__**📡 Tick Just Happened!**__",
            description=f"🕒 Tick just happened on **{display_tick}**.\nAnother day, another opportunity to shape the Galaxy!",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"ISO: {current_tick} UTC")

        await channel.send(embed=embed)
        print(f"✅ Tick posted in {channel.name}")

if __name__ == "__main__":
    print("✅ Tick Check gestartet...")

    async def main():
        await client.login(TOKEN)
        await post_tick_time(client)
        await client.close()

    asyncio.run(main())
