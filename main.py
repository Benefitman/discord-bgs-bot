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
            print(f"[DEBUG] Fraktion API Status: {response.status}")
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
    try:
        async with session.get(url, params=params, timeout=15) as response:
            print(f"[DEBUG] Systemdaten {system_name}: Status {response.status}")
            if response.status != 200:
                return []
            data = await response.json()
            return data.get("docs", [])
    except Exception as e:
        print(f"[FEHLER] Fehler beim Abrufen von Systemdaten ({system_name}): {e}")
        return []

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
        print(f"[FEHLER] Einfluss nicht abrufbar für {faction_name} in {system_name}: {e}")
    return None

async def post_report():
    print("🚀 Starte BGS Report...")
    await client.login(TOKEN)
    print("🔐 Bot erfolgreich eingeloggt!")

    async with aiohttp.ClientSession() as session:
        faction_data = await fetch_faction_data(session)
        if not faction_data:
            print("[FEHLER] Keine Fraktionsdaten erhalten.")
            await client.close()
            return

        faction = faction_data[0]
        print(f"📦 Fraktionsdaten geladen: {faction.get('name')}")

        low_influence_systems = []
        close_competitor_systems = []
        has_conflict = False

        presence_data = faction.get("faction_presence", [])
        print(f"🌌 Systeme mit Präsenz: {len(presence_data)}")

        for presence in presence_data:
            system_name = presence.get("system_name")
            influence = presence.get("influence", 0) * 100
            system_data = await fetch_system_data(session, system_name)
            if not system_data:
                print(f"[WARNUNG] Keine Daten für System {system_name}")
                continue

            system = system_data[0]
            controlling_faction = system.get("controlling_minor_faction", "").lower()
            factions_in_system = system.get("factions", [])

            if controlling_faction == FACTION_NAME.lower():
                # Niedriger Einfluss + Konflikte checken
                if influence < 39:
                    conflict_info = ""
                    for conflict in presence.get("conflicts", []):
                        status = conflict.get("status", "").lower()
                        conflict_type = conflict.get("type", "").lower()
                        if status in ["active", "pending"] and conflict_type in ["war", "election"]:
                            opponent = conflict.get("opposing_faction", {}).get("name", "Unbekannt")
                            conflict_info = f" – {conflict_type.title()} mit {opponent}"
                            has_conflict = True
                            break
                    low_influence_systems.append((system_name, influence, conflict_info))

                # Einfluss anderer Fraktionen parallel abfragen
                async def get_other_faction_info(other):
                    other_name = other.get("name", "")
                    if other_name.lower() == FACTION_NAME.lower():
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

        print(f"🔻 Niedriger Einfluss: {len(low_influence_systems)}")
        print(f"⚠️ Konkurrenzsysteme: {len(close_competitor_systems)}")

        if low_influence_systems or close_competitor_systems:
            print("📡 Sende Embed an Discord...")
            channel = await client.fetch_channel(CHANNEL_ID)

            embeds = []
            current_embed = discord.Embed(
                title="📊 BGS Overview",
                description="**🟠 Systems with Inf below 39%**\n ⚠️ **Enemy close by 19%** **or less**",
                color=0xFF5733 if has_conflict else 0x1B365D
            )

            field_count = 0

            # Füge alle Low-Influence-Systeme ein
            for name, infl, conflict in low_influence_systems:
                value = f"*Influence: {infl:.2f}%*"
                if conflict:
                    value += f"\n**⚔️ Conflict:** {conflict}"
                current_embed.add_field(name=f"🔻 {name}", value=value, inline=False)
                field_count += 1
                if field_count == 25:
                    embeds.append(current_embed)
                    current_embed = discord.Embed(color=current_embed.color)
                    field_count = 0

            # Füge alle Konkurrenzsysteme ein
            for name, own_infl, rival, rival_infl in close_competitor_systems:
                diff = own_infl - rival_infl
                value = f"*House of Saga: {own_infl:.2f}%*\n{rival}: {rival_infl:.2f}%\n⚠️ Inf Distance: {diff:.2f}%"
                current_embed.add_field(name=f"⚠️ {name}", value=value, inline=False)
                field_count += 1
                if field_count == 25:
                    embeds.append(current_embed)
                    current_embed = discord.Embed(color=current_embed.color)
                    field_count = 0

            if field_count > 0:
                embeds.append(current_embed)

            for embed in embeds:
                await channel.send(embed=embed)

            print("✅ Alle Embeds gesendet.")
        else:
            print("🟢 Alle Systeme stabil – kein Bericht gesendet.")

    await client.close()
    print("👋 Verbindung zum Bot getrennt.")

if __name__ == "__main__":
    print("✅ Script geladen und wird gestartet...")
    asyncio.run(post_report())
