import os
import logging
import asyncpg
import discord
from discord.ext import commands
from dotenv import load_dotenv

# --- Local imports ---
from items import find_item   # <- our fuzzy matcher

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------------------------------------------------
# Database setup
# -------------------------------------------------------------------
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS builds (
            id SERIAL PRIMARY KEY,
            champion TEXT,
            item_ids TEXT,      -- e.g. "3111,3135"
            author TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.close()

@bot.event
async def on_ready():
    await init_db()
    print(f"Logged in as {bot.user}")

# -------------------------------------------------------------------
# Commands
# -------------------------------------------------------------------
@bot.command()
async def add(ctx, champion: str, *, build: str):
    """
    !add ashe mercury trends, void staff
    -> stores "3111,3135"
    """
    tokens = [token.strip(" ,") for token in build.split()]
    matched_ids = []

    for token in tokens:
        match = find_item(token)
        if match:
            _, item_id = match
            matched_ids.append(item_id)

    if not matched_ids:
        await ctx.send("❌ No valid items found.")
        return

    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO builds (champion, item_ids, author) VALUES ($1, $2, $3)",
        champion.lower(),
        ",".join(matched_ids),
        str(ctx.author)
    )
    await conn.close()
    await ctx.send(f"✅ Build for **{champion.title()}** saved with {len(matched_ids)} items!")

@bot.command()
async def get(ctx, champion: str):
    """
    Retrieve and display item icons for the champion.
    """
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT item_ids, author FROM builds WHERE champion = $1",
        champion.lower()
    )
    await conn.close()

    if not rows:
        await ctx.send(f"No builds found for **{champion.title()}**.")
        return

    for r in rows:
        item_ids = r["item_ids"].split(",")
        author = r["author"]

        # Build the embed with icons
        embed = discord.Embed(
            title=f"Build for {champion.title()}",
            description=f"Submitted by {author}",
            color=discord.Color.blue()
        )
        # Add each icon as a field with a blank name to keep them inline
        for item_id in item_ids:
            icon_url = f"https://ddragon.leagueoflegends.com/cdn/14.18.1/img/item/{item_id}.png"
            embed.set_thumbnail(url=icon_url)  # One thumbnail per embed
            # OR if you prefer multiple icons inline, you can use embed.add_field
            # embed.add_field(name="\u200b", value=f"[⠀]({icon_url})") 

        await ctx.send(embed=embed)

@bot.command()
async def delete(ctx, champion: str):
    conn = await asyncpg.connect(DATABASE_URL)
    result = await conn.execute(
        "DELETE FROM builds WHERE champion = $1 AND author = $2",
        champion.lower(),
        str(ctx.author)
    )
    await conn.close()
    count = int(result.split()[-1])
    await ctx.send(
        f"🗑️ Deleted {count} build(s) for **{champion.title()}** owned by you."
        if count else
        f"No builds found for **{champion.title()}** that you own."
    )

if __name__ == "__main__":
    if not TOKEN or not DATABASE_URL:
        raise RuntimeError("Missing DISCORD_TOKEN or DATABASE_URL")
    bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)
