import os
import discord
import aiohttp
import asyncio

from dotenv import load_dotenv
load_dotenv()


TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
FACTION_NAME = "House of Saga"
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

BGS_API_URL = "https://elitebgs.app/api/ebgs/v5"

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)


async def fetch_faction_data(session):
    url = f"{BGS_API_URL}/factions"
    params = {"name": FACTION_NAME}
    try:
        async with session.get(url, params=params, timeout=15) as response:
            if response.status != 200:
                print(f"[WARNUNG] API-Status: {response.status}")
                return []
            data = await response.json()
            return data.get("docs", [])
    except Exception as e:
        print(f"[FEHLER] Fehler beim Abrufen der Fraktionsdaten: {e}")
        return []



async def fetch_system_data(session, system_name):
    url = f"{BGS_API_URL}/systems"
    params = {"name": system_name}
    async with session.get(url, params=params) as response:
        data = await response.json()
        return data.get("docs", [])


async def post_report():
    await client.login(TOKEN)

    async with aiohttp.ClientSession() as session:
        faction_data = await fetch_faction_data(session)
        if not faction_data:
            print("[FEHLER] Keine Fraktionsdaten erhalten.")
            await client.close()
            return

        faction = faction_data[0]
        systems_to_report = []
        has_conflict = False

        for presence in faction.get("faction_presence", []):
            system_name = presence.get("system_name")
            system_data = await fetch_system_data(session, system_name)
            if not system_data:
                continue

            system = system_data[0]
            controlling_faction = system.get("controlling_minor_faction", "").lower()
            if controlling_faction == FACTION_NAME.lower():
                influence = presence.get("influence", 0) * 100
                if influence < 49:
                    conflict_info = ""
                    for conflict in presence.get("conflicts", []):
                        status = conflict.get("status", "").lower()
                        conflict_type = conflict.get("type", "").lower()
                        if status in ["active", "pending"] and conflict_type in ["war", "election"]:
                            opponent = conflict.get("opposing_faction", {}).get("name", "Unbekannt")
                            conflict_info = f" – {conflict_type.title()} mit {opponent}"
                            has_conflict = True
                            break

                    systems_to_report.append((system_name, influence, conflict_info))

        if systems_to_report:
            systems_to_report.sort(key=lambda x: x[1], reverse=True)
            embed_color = 0xFF5733 if has_conflict else 0x1B365D

            embed = discord.Embed(
                title=f"⚠️ INFLUENCE BELOW 49% ⚠️ – {FACTION_NAME}",
                description="**Following Systems need Work:**",
                color=embed_color
            )

            for name, influence, conflict in systems_to_report:
                value = f"*Influence: {influence:.2f}%*"
                if conflict:
                    value += f"\n**⚔️ Conflict:** {conflict}"
                embed.add_field(name=f"**{name}**", value=value, inline=False)

            channel = await client.fetch_channel(CHANNEL_ID)
            await channel.send(embed=embed)
        else:
            print("Kein System mit niedrigem Einfluss gefunden.")

    await client.close()


if __name__ == "__main__":
    asyncio.run(post_report())
