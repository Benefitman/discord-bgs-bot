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

async def announce_maintenance(mode):
    status_text = {
        "on": "__**🛠️ Maintenance Mode Active**__\nSome services may be temporarily unavailable or display inaccurate data.",
        "off": "__**✅ Maintenance Completed**__\nAll systems operational again. Thank you for your patience!"
    }

    if mode not in status_text:
        print(f"[ERROR] Invalid maintenance mode: {mode}")
        return

    for channel_id in [1352212125300297748, 1385989063018021075]:
        channel = await client.fetch_channel(channel_id)
        await channel.send(status_text[mode])
    print(f"[INFO] Maintenance announcement sent: {mode}")

async def main(mode, submode=None):
    await client.login(TOKEN)

    if mode == "tick":
        await post_tick_time(client)
    elif mode == "bgs":
        await post_report(client)
    elif mode == "maintenance" and submode in {"on", "off"}:
        await announce_maintenance(submode)
    else:
        print("[ERROR] Unknown or incomplete mode.")

    await client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ED BGS Bot")
    parser.add_argument("mode", choices=["tick", "bgs", "maintenance"], help="Which part to run")
    parser.add_argument("submode", nargs="?", help="If mode is maintenance: on or off")
    args = parser.parse_args()
    asyncio.run(main(args.mode, args.submode))
