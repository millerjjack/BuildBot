import asyncpg
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

from items import find_item  # <-- NEW

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS builds (
            id SERIAL PRIMARY KEY,
            champion TEXT,
            build TEXT,        -- stores comma-separated item IDs
            author TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.close()


@bot.event
async def on_ready():
    await init_db()
    print(f"Logged in as {bot.user}")


@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}!")


@bot.command(name="add")
async def add_build(ctx, champion: str, *, build: str):
    """
    Example: !add ashe mercury trends, void staff
    Fuzzy-matches each token/phrase to known items and stores their IDs.
    """
    item_inputs = [x.strip() for x in build.split(",")]
    matched_ids = []
    unmatched = []

    for raw in item_inputs:
        result = find_item(raw)
        if result:
            _, item_id = result
            matched_ids.append(item_id)
        else:
            unmatched.append(raw)

    if not matched_ids:
        await ctx.send("❌ No valid items found.")
        return

    build_str = ",".join(matched_ids)
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO builds (champion, build, author) VALUES ($1, $2, $3)",
        champion.lower(), build_str, str(ctx.author)
    )
    await conn.close()

    msg = f"✅ Build for **{champion.title()}** added: {', '.join(matched_ids)}"
    if unmatched:
        msg += f"\n⚠️ Unmatched: {', '.join(unmatched)}"
    await ctx.send(msg)


@bot.command(name="get")
async def get_build(ctx, champion: str):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT build, author FROM builds WHERE champion = $1",
        champion.lower()
    )
    await conn.close()

    if not rows:
        await ctx.send(f"No builds found for **{champion.title()}**.")
        return

    messages = []
    for r in rows:
        ids = r["build"].split(",")
        # Turn each ID into an image URL
        icons = " ".join(
            f"https://ddragon.leagueoflegends.com/cdn/14.18.1/img/item/{iid}.png"
            for iid in ids
        )
        messages.append(f"By {r['author']}:\n{icons}")

    await ctx.send(f"**Builds for {champion.title()}**:\n" + "\n\n".join(messages))


@bot.command(name="delete")
async def delete_build(ctx, champion: str):
    conn = await asyncpg.connect(DATABASE_URL)
    result = await conn.execute(
        "DELETE FROM builds WHERE champion = $1 AND author = $2",
        champion.lower(), str(ctx.author)
    )
    await conn.close()
    if result.endswith("0"):
        await ctx.send(f"No builds found for **{champion.title()}** owned by you.")
    else:
        await ctx.send(f"Deleted your builds for **{champion.title()}**.")


if __name__ == "__main__":
    if not TOKEN:
        raise Exception("No DISCORD_TOKEN provided")
    if not DATABASE_URL:
        raise Exception("No DATABASE_URL provided")
    bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)
