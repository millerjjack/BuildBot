import os
import logging
import asyncpg
import aiohttp
import discord
import random
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
async def hello(ctx):
    await ctx.send(f"Hey bitch {ctx.author.mention}!")

@bot.command()
async def crypto(ctx):
    """Fetch global cryptocurrency market stats from CoinGecko."""
    url = "https://api.coingecko.com/api/v3/global"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                market_data = data.get("data", {})

                # Extract useful info
                total_market_cap = market_data.get("total_market_cap", {}).get("usd", 0)
                total_volume = market_data.get("total_volume", {}).get("usd", 0)
                btc_dominance = market_data.get("market_cap_percentage", {}).get("btc", 0)
                eth_dominance = market_data.get("market_cap_percentage", {}).get("eth", 0)
                active_cryptos = market_data.get("active_cryptocurrencies", 0)

                # Format nicely
                msg = (
                    f"🌐 **Global Crypto Market Stats** 🌐\n"
                    f"💰 Total Market Cap: ${total_market_cap:,.0f}\n"
                    f"📊 24h Volume: ${total_volume:,.0f}\n"
                    f"🪙 BTC Dominance: {btc_dominance:.2f}% | ETH: {eth_dominance:.2f}%\n"
                    f"🔢 Active Cryptocurrencies: {active_cryptos}"
                )

                await ctx.send(msg)
            else:
                await ctx.send("⚠️ Failed to fetch crypto stats.")

@bot.command()
async def meme(ctx):
    """Fetch a meme from r/darkmemers and send the image URL."""
    url = "https://www.reddit.com/r/darkmemers/hot.json?limit=50"
    headers = {"User-Agent": "discord-bot/0.1 by yourusername"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                posts = data.get("data", {}).get("children", [])
                if not posts:
                    await ctx.send("⚠️ No memes found.")
                    return

                # Pick a random post
                post = random.choice(posts)["data"]
                meme_url = post.get("url_overridden_by_dest")

                if meme_url and (meme_url.endswith(".jpg") or meme_url.endswith(".png") or meme_url.endswith(".gif")):
                    await ctx.send(meme_url)
                else:
                    await ctx.send("⚠️ Couldn't find a valid meme image.")
            else:
                await ctx.send("⚠️ Failed to fetch memes from Reddit.")


@bot.command()
async def add(ctx, champion: str, *, build: str):
    """
    Add a build for a champion using comma-separated item names.
    Example: !add zoe sorcerer's boots, void staff, deathcap, lich bane, hourglass
    """
    # Split input by commas to support multi-word item names
    tokens = [token.strip().lower() for token in build.split(",")]
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
    Retrieve and display item icons for the champion using raw image URLs.
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

        icon_urls = [
            f"https://ddragon.leagueoflegends.com/cdn/15.19.1/img/item/{item_id.strip()}.png"
            for item_id in item_ids
        ]

        # Send a single message with all image URLs (Discord will auto-embed)
        message = (
            f"**Build for {champion.title()}**\n"
            f"Submitted by `{author}`:\n\n" +
            "\n".join(icon_urls)
        )

        await ctx.send(message)

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








