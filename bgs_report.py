import os
import sqlite3
import asyncio
import logging
import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
DB_PATH = os.getenv("BGS_DB_PATH", "bgs.db")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHANNEL_FACTION_MAP = {
    1385989063018021075: "Torval Mining Ltd",
}

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)


async def get_faction_presence_from_db(faction_name):
    logger.info("[DB] Reading faction presence for %s", faction_name)

    def query():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT fp.system_id, s.name AS system_name, fp.influence
            FROM faction_presence fp
            JOIN factions f ON f.id = fp.faction_id
            JOIN systems s ON s.id = fp.system_id
            WHERE f.name = ?
            """,
            (faction_name,),
        )
        rows = cur.fetchall()
        result = []
        for row in rows:
            cur.execute(
                """
                SELECT c.type, c.status,
                       CASE WHEN f1.name = ? THEN f2.name ELSE f1.name END AS opponent
                FROM conflicts c
                JOIN factions f1 ON f1.id = c.faction1_id
                JOIN factions f2 ON f2.id = c.faction2_id
                WHERE c.system_id = ? AND (f1.name = ? OR f2.name = ?)
                """,
                (faction_name, row["system_id"], faction_name, faction_name),
            )
            conflict_rows = cur.fetchall()
            conflicts = [
                {
                    "type": c["type"],
                    "status": c["status"],
                    "opposing_faction": {"name": c["opponent"]},
                }
                for c in conflict_rows
            ]
            result.append(
                {
                    "system_name": row["system_name"],
                    "influence": row["influence"],
                    "conflicts": conflicts,
                }
            )
        conn.close()
        return result

    return await asyncio.to_thread(query)


async def get_system_data_from_db(system_name):
    logger.info("[DB] Reading system data for %s", system_name)

    def query():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, controlling_faction_id FROM systems WHERE name = ?",
            (system_name,),
        )
        system_row = cur.fetchone()
        if not system_row:
            conn.close()
            return None
        system_id = system_row["id"]
        controlling_name = None
        if system_row["controlling_faction_id"]:
            cur.execute(
                "SELECT name FROM factions WHERE id = ?",
                (system_row["controlling_faction_id"],),
            )
            cf_row = cur.fetchone()
            controlling_name = cf_row["name"] if cf_row else None
        cur.execute(
            """
            SELECT f.name FROM faction_presence fp
            JOIN factions f ON f.id = fp.faction_id
            WHERE fp.system_id = ?
            """,
            (system_id,),
        )
        factions = [{"name": r["name"]} for r in cur.fetchall()]
        conn.close()
        return {
            "controlling_minor_faction": controlling_name,
            "factions": factions,
        }

    return await asyncio.to_thread(query)


async def get_faction_influence_in_system(faction_name, system_name):
    logger.info("[DB] Reading influence for %s in %s", faction_name, system_name)

    def query():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT fp.influence
            FROM faction_presence fp
            JOIN factions f ON f.id = fp.faction_id
            JOIN systems s ON s.id = fp.system_id
            WHERE f.name = ? AND s.name = ?
            """,
            (faction_name, system_name),
        )
        row = cur.fetchone()
        conn.close()
        return row["influence"] * 100 if row else None

    return await asyncio.to_thread(query)

async def post_report(client: discord.Client):
    print("\n🚀 Starting BGS Report...")

    for channel_id, faction_name in CHANNEL_FACTION_MAP.items():
        print(f"\n📡 Processing: {faction_name} for Channel {channel_id}")
        presence_data = await get_faction_presence_from_db(faction_name)
        if not presence_data:
            print(f"[ERROR] No faction data for {faction_name}.")
            continue

        low_influence_systems = []
        close_competitor_systems = []
        has_conflict = False

        for presence in presence_data:
            system_name = presence.get("system_name")
            influence = round(presence.get("influence", 0) * 100, 2)

            system = await get_system_data_from_db(system_name)
            if not system:
                continue

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
                    other_infl = await get_faction_influence_in_system(other_name, system_name)
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

        channel = await client.fetch_channel(channel_id)

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
                value += "\n​"
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
                    "\u200b",
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

        else:
            await channel.send(
                embed=discord.Embed().set_image(url="https://media.tenor.com/epKSpUp4d8sAAAAC/anakin-obiwan-star-wars.gif")
            )

    print("\n👋 Bot session ended.")
