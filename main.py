import os
import json
import discord
import aiohttp
import asyncio
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()

CHANNEL_FACTION_MAP = {
    1352212125300297748: "House of Saga",
    1385989063018021075: "Torval Mining Ltd"
}

BGS_API_URL = "https://elitebgs.app/api/ebgs/v5"
EDCD_TICK_URL = "https://edcd.github.io/tick-detector/ticks.json"
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
            data = await response.json()
            if data and isinstance(data, list) and len(data) > 0:
                return data[0].get("timestamp")
    except Exception as e:
        print(f"[ERROR] Failed to fetch tick from EDCD: {e}")
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

async def post_report():
    async with aiohttp.ClientSession() as session:
        for channel_id, faction_name in CHANNEL_FACTION_MAP.items():
            print(f"\n📡 Bearbeite Fraktion: {faction_name} für Channel: {channel_id}")
            url = f"{BGS_API_URL}/factions"
            params = {"name": faction_name}
            async with session.get(url, params=params) as resp:
                data = await resp.json()
            if not data.get("docs"):
                continue

            faction = data["docs"][0]
            presence = faction.get("faction_presence", [])

            low_inf = []
            close_comp = []
            has_conflict = False

            for p in presence:
                system_name = p.get("system_name")
                influence = p.get("influence", 0) * 100
                sys_url = f"{BGS_API_URL}/systems"
                sys_params = {"name": system_name}
                async with session.get(sys_url, params=sys_params) as sys_resp:
                    sys_data = await sys_resp.json()
                if not sys_data.get("docs"):
                    continue

                sys_info = sys_data["docs"][0]
                factions = sys_info.get("factions", [])
                controlling = sys_info.get("controlling_minor_faction", "").lower()

                if controlling == faction_name.lower() and influence < 39:
                    conflict_text = ""
                    for c in p.get("conflicts", []):
                        if c.get("status") in ["active", "pending"]:
                            conflict_text = f" – {c['type'].title()} with {c['opposing_faction']['name']}"
                            has_conflict = True
                            break
                    low_inf.append((system_name, influence, conflict_text))

                for other in factions:
                    o_name = other.get("name")
                    if o_name.lower() == faction_name.lower():
                        continue
                    other_inf = await get_faction_influence_in_system(session, o_name, system_name)
                    if other_inf is None:
                        continue
                    diff = influence - other_inf
                    if 0 < diff <= 19:
                        close_comp.append((system_name, influence, o_name, other_inf))
                        break

            if low_inf or close_comp:
                channel = await client.fetch_channel(channel_id)
                embed = discord.Embed(
                    title=f"📊 {faction_name} – BGS Overview",
                    description="🔻 **Systems with Inf below 39%**\n⚠️ **Enemy close by 19% or less**",
                    color=0xFF5733 if has_conflict else 0x1B365D
                )

                for name, infl, conflict in low_inf:
                    embed.add_field(
                        name=f"🔻 __**{name}**__",
                        value=f"*Influence: {infl:.2f}%*\n**⚔️ Conflict:** {conflict}\n\u200b",
                        inline=False
                    )

                for name, own, rival, rival_inf in close_comp:
                    diff = own - rival_inf
                    embed.add_field(
                        name=f"⚠️ __**{name}**__",
                        value=f"**{faction_name}: {own:.2f}%**\n*{rival}: {rival_inf:.2f}%*\n*Inf Distance: {diff:.2f}%*\n\u200b",
                        inline=False
                    )

                await channel.send(embed=embed)

async def get_faction_influence_in_system(session, faction_name, system_name):
    url = f"{BGS_API_URL}/factions"
    params = {"name": faction_name}
    async with session.get(url, params=params) as response:
        if response.status != 200:
            return None
        data = await response.json()
        for faction in data.get("docs", []):
            for presence in faction.get("faction_presence", []):
                if presence.get("system_name", "").lower() == system_name.lower():
                    return presence.get("influence", 0) * 100
    return None

if __name__ == "__main__":
    print("✅ Script geladen und wird gestartet...")
    asyncio.run(client.login(TOKEN))
    asyncio.run(post_tick_time())

    now = datetime.utcnow().hour
    if now in [0, 6, 12, 18]:
        asyncio.run(post_report())

    asyncio.run(client.close())
