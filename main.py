import asyncpg
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")  # Provided automatically by Railway's Postgres plugin

# Logging
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")

# Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def init_db():
    """Create the builds table if it doesn't already exist."""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS builds (
            id SERIAL PRIMARY KEY,
            champion TEXT,
            build TEXT,
            author TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.close()

@bot.event
async def on_ready():
    await init_db()
    print(f"Logged in as {bot.user}")
    print("------")

@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}!")

@bot.command(name="add")
async def add_build(ctx, champion: str, *, build: str):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO builds (champion, build, author) VALUES ($1, $2, $3)",
        champion.lower(), build, str(ctx.author)
    )
    await conn.close()
    await ctx.send(f"Build for **{champion.title()}** added!")

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

    response = "\n".join([f"- {r['build']} *(by {r['author']})*" for r in rows])
    await ctx.send(f"**Builds for {champion.title()}**:\n{response}")

@bot.command(name="delete")
async def delete_build(ctx, champion: str):
    conn = await asyncpg.connect(DATABASE_URL)
    result = await conn.execute(
        "DELETE FROM builds WHERE champion = $1 AND author = $2",
        champion.lower(), str(ctx.author)
    )
    await conn.close()
    await ctx.send(
        f"Deleted your builds for **{champion.title()}**."
        if result.endswith("0") is False else
        f"No builds found for **{champion.title()}** owned by you."
    )

if __name__ == "__main__":
    if not TOKEN:
        raise Exception("No DISCORD_TOKEN provided in environment variables")
    if not DATABASE_URL:
        raise Exception("No DATABASE_URL provided. Add a PostgreSQL plugin and set env vars in Railway.")
    bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)
