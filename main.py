import asyncio
import argparse
from tick_check import post_tick_time
from bgs_report import post_report
from discord import Client, Intents
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()

intents = Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = Client(intents=intents)

async def main(mode):
    await client.login(TOKEN)
    if mode == "tick":
        await post_tick_time(client)
    elif mode == "bgs":
        await post_report(client)
    await client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ED BGS Bot")
    parser.add_argument("mode", choices=["tick", "bgs"], help="Which part to run: tick or bgs")
    args = parser.parse_args()
    asyncio.run(main(args.mode))
