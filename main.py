import os
import discord
import aiohttp
import asyncio
from discord.ext import commands

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
if not TOKEN:
    raise ValueError(
        "[FEHLER] Die Umgebungsvariable DISCORD_BOT_TOKEN ist nicht gesetzt!")

FACTION_NAME = "House of Saga"
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
if CHANNEL_ID is None:
    raise ValueError(
        "[FEHLER] Die Umgebungsvariable DISCORD_CHANNEL_ID ist nicht gesetzt!")
CHANNEL_ID = int(CHANNEL_ID)

BGS_API_URL = "https://elitebgs.app/api/ebgs/v5"

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)


async def fetch_faction_data(session):
    url = f"{BGS_API_URL}/factions"
    params = {"name": FACTION_NAME}
    async with session.get(url, params=params) as response:
        if response.status == 200:
            data = await response.json()
            return data.get("docs", [])
        else:
            print(
                f"[FEHLER] Fehler beim Abrufen der Fraktionsdaten: {response.status}"
            )
            return []


async def fetch_system_data(session, system_name):
    url = f"{BGS_API_URL}/systems"
    params = {"name": system_name}
    async with session.get(url, params=params) as response:
        if response.status == 200:
            data = await response.json()
            return data.get("docs", [])
        else:
            print(
                f"[FEHLER] Fehler beim Abrufen der Systemdaten für {system_name}: {response.status}"
            )
            return []


async def check_faction_influence():
    async with aiohttp.ClientSession() as session:
        faction_data = await fetch_faction_data(session)
        if not faction_data:
            print("[FEHLER] Keine Daten für die Fraktion gefunden.")
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
            controlling_faction = system.get("controlling_minor_faction",
                                             "").lower()
            if controlling_faction == FACTION_NAME.lower():
                influence = presence.get("influence", 0) * 100
                if influence < 49:
                    conflict_info = ""
                    for conflict in presence.get("conflicts", []):
                        status = conflict.get("status", "").lower()
                        conflict_type = conflict.get("type", "").lower()
                        if status in [
                                "active", "pending"
                        ] and conflict_type in ["war", "election"]:
                            opponent = conflict.get("opposing_faction",
                                                    {}).get(
                                                        "name", "Unbekannt")
                            conflict_info = f" – {conflict_type.title()} mit {opponent}"
                            has_conflict = True
                            break

                    systems_to_report.append(
                        (system_name, influence, conflict_info))

        if systems_to_report:
            systems_to_report.sort(key=lambda x: x[1], reverse=True)

            embed_color = 0xFF5733 if has_conflict else 0x1B365D  # Inara-Stil
            embed = discord.Embed(
                title=f"⚠️ INFLUENCE BELOW 49% ⚠️",
                description="**Following Systems need Work:**",
                color=embed_color)

            for name, influence, conflict in systems_to_report:
                value = f"*influence: {influence:.2f}%*"
                if conflict:
                    value += f"\n**⚔️ Conflict:** {conflict}"
                embed.add_field(name=f"**{name}**", value=value, inline=False)

            channel = client.get_channel(CHANNEL_ID)
            if channel:
                await channel.send(embed=embed)
        else:
            print(f"'{FACTION_NAME}' has no controlling System below 49 %.")


@client.event
async def on_ready():
    print(f'{client.user} hat sich erfolgreich eingeloggt.')
    await check_faction_influence()


if __name__ == "__main__":
    client.run(TOKEN)
