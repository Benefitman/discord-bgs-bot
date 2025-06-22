import os
import discord
import aiohttp
import asyncio
from dotenv import load_dotenv

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

# --- Hier kommen fetch_faction_data, fetch_system_data,
#     get_faction_influence_in_system aus deinem bestehenden Code rein ---
#     (wegen Platz und Redundanz ausgelassen, da du sie ja schon hast)

async def post_report():
    print("🚀 Starte BGS Report...")
    await client.login(TOKEN)
    print("🔐 Bot erfolgreich eingeloggt!")

    async with aiohttp.ClientSession() as session:
        for channel_id, faction_name in CHANNEL_FACTION_MAP.items():
            # Hier folgt dein gesamter bestehender Code zum Generieren und Posten der Embeds
            # Alles, was du bisher für den BGS Report gemacht hast, unverändert
            pass  # <-- durch echten Code ersetzen

    await client.close()
    print("👋 Verbindung zum Bot getrennt.")

if __name__ == "__main__":
    print("✅ Script geladen und wird gestartet...")
    asyncio.run(post_report())
