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

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)

async def fetch_faction_data(session, faction_name):
    url = f"{BGS_API_URL}/factions"
    params = {"name": faction_name}
    try:
        async with session.get(url, params=params, timeout=15) as response:
            if response.status != 200:
                return []
            data = await response.json()
            return data.get("docs", [])
    except Exception as e:
        print(f"[ERROR] Failed to fetch faction data for {faction_name}: {e}")
        return []

async def fetch_system_data(session, system_name):
    url = f"{BGS_API_URL}/systems"
    params = {"name": system_name}
    try:
        async with session.get(url, params=params, timeout=15) as response:
            if response.status != 200:
                return []
            data = await response.json()
            return data.get("docs", [])
    except Exception as e:
        print(f"[ERROR] Failed to fetch system data for {system_name}: {e}")
        return []

async def fetch_tick_timestamp(session):
    url = f"{BGS_API_URL}/ticks"
    try:
        async with session.get(url, timeout=15) as response:
            if response.status != 200:
                return None
            data = await response.json()
            if data and isinstance(data, list) and len(data) > 0:
                return data[0].get("time")
    except Exception as e:
        print(f"[ERROR] Failed to fetch global tick timestamp: {e}")
    return None

async def get_faction_influence_in_system(session, faction_name, system_name):
    url = f"{BGS_API_URL}/factions"
    params = {"name": faction_name}
    try:
        async with session.get(url, params=params, timeout=15) as response:
            if response.status != 200:
                return None
            data = await response.json()
            for faction in data.get("docs", []):
                for presence in faction.get("faction_presence", []):
                    if presence.get("system_name", "").lower() == system_name.lower():
                        return presence.get("influence", 0) * 100
    except Exception as e:
        print(f"[ERROR] Influence not retrievable for {faction_name} in {system_name}: {e}")
    return None

async def post_report():
    print("\n🚀 Starting BGS Report...")
    await client.login(TOKEN)

    async with aiohttp.ClientSession() as session:
        current_tick = await fetch_tick_timestamp(session)
        if not current_tick:
            print("[ERROR] Could not fetch global tick timestamp.")
            return

        formatted_tick = datetime.fromisoformat(current_tick.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"⏱️ Global Tick timestamp: {formatted_tick}")

        for channel_id, faction_name in CHANNEL_FACTION_MAP.items():
            channel = await client.fetch_channel(channel_id)
            await channel.send(f"⏱️ **Global Tick timestamp**: `{formatted_tick}`")
            await channel.send(f"📈 Preparing BGS report for `{faction_name}`...")

            faction_data = await fetch_faction_data(session, faction_name)
            if not faction_data:
                print(f"[ERROR] No faction data for {faction_name}.")
                continue

            faction = faction_data[0]
            presence_data = faction.get("faction_presence", [])
            low_influence_systems = []
            close_competitor_systems = []
            has_conflict = False

            for presence in presence_data:
                system_name = presence.get("system_name")
                influence = round(presence.get("influence", 0) * 100, 2)

                system_data = await fetch_system_data(session, system_name)
                if not system_data:
                    continue

                system = system_data[0]
                controlling_faction = system.get("controlling_minor_faction", "").lower()
                factions_in_system = system.get("factions", [])

                if controlling_faction == faction_name.lower():
                    if influence < 39:
                        conflict_info = ""
                        for conflict in presence.get("conflicts", []):
                            status = conflict.get("status", "").lower()
                            conflict_type = conflict.get("type", "").lower()
                            if status in ["active", "pending"] and conflict_type in ["war", "election"]:
                                opponent = conflict.get("opposing_faction", {}).get("name", "Unknown")
                                conflict_info = f" – {conflict_type.title()} with {opponent}"
                                has_conflict = True
                                break
                        low_influence_systems.append((system_name, influence, conflict_info))

                    async def get_other_faction_info(other):
                        other_name = other.get("name", "")
                        if other_name.lower() == faction_name.lower():
                            return None
                        other_infl = await get_faction_influence_in_system(session, other_name, system_name)
                        if other_infl is None:
                            return None
                        diff = influence - other_infl
                        if 0 < diff <= 19:
                            return (system_name, influence, other_name, other_infl)
                        return None

                    tasks = [get_other_faction_info(other) for other in factions_in_system]
                    results = await asyncio.gather(*tasks)
                    for result in results:
                        if result:
                            close_competitor_systems.append(result)
                            break

            if low_influence_systems or close_competitor_systems:
                embeds = []
                current_embed = discord.Embed(
                    title=f"📊 {faction_name} – BGS Overview",
                    description="🔻 **Systems with Inf below 39%**\n⚠️ **Enemy close by 19% or less**",
                    color=0xFF5733 if has_conflict else 0x1B365D
                )

                field_count = 0

                for name, infl, conflict in low_influence_systems:
                    title = f"🔻 __**{name}**__"
                    value = f"*Influence: {infl:.2f}%*"
                    if conflict:
                        value += f"\n**⚔️ Conflict:** {conflict}"
                    value += "\n\u200b"
                    current_embed.add_field(name=title, value=value, inline=False)
                    field_count += 1
                    if field_count == 25:
                        embeds.append(current_embed)
                        current_embed = discord.Embed(color=current_embed.color)
                        field_count = 0

                for name, own_infl, rival, rival_infl in close_competitor_systems:
                    diff = own_infl - rival_infl
                    title = f"⚠️ __**{name}**__"
                    value = (
                        f"**{faction_name}: {own_infl:.2f}%**\n"
                        f"*{rival}: {rival_infl:.2f}%*\n"
                        f"*Inf Distance: {diff:.2f}%*\n"
                        "\u200b"
                    )
                    current_embed.add_field(name=title, value=value, inline=False)
                    field_count += 1
                    if field_count == 25:
                        embeds.append(current_embed)
                        current_embed = discord.Embed(color=current_embed.color)
                        field_count = 0

                if field_count > 0:
                    embeds.append(current_embed)

                for embed in embeds:
                    await channel.send(embed=embed)

    await client.close()
    print("\n👋 Bot session ended.")

if __name__ == "__main__":
    print("✅ Script geladen und wird gestartet...")
    asyncio.run(post_report())
