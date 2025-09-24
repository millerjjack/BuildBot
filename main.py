import aiosqlite
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
DB_FILE= "database.db"

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def init_db():
    async with aiosqlite.connect('database.db') as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS builds (
        champion TEXT,
        build TEXT,
        author TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        """)
        await db.commit()


@bot.event
async def on_ready():
    await init_db()
    print('Logged in as {0.user}'.format(bot))
    print('------')


@bot.command()
async def hello(message):
    await message.channel.send('Hello {}'.format(message.author.mention))


@bot.command(name="add")
async def add_build(ctx, champion: str, *, build: str):
    async with aiosqlite.connect('database.db') as db:
        await db.execute(
            "INSERT INTO builds (champion, build, author, created_at)",
            (champion.lower(), build.lower(), str(ctx.author), str(ctx.created_at))
        )
        await db.commit()


@bot.command(name="get")
async def get_build(ctx, champion: str):
    async with aiosqlite.connect('database.db') as db:
        async with db.execute(
            "SELECT * FROM builds WHERE champion = ?",
                (champion.lower(),)
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await ctx.send('No such builds found')
        return

    response = "\n".join([f"- {build} *(by {author})*" for build, author in rows])
    await ctx.send(f"**Builds for {champion.title()}**:\n{response}")


@bot.command(name="delete")
async def delete_build(ctx, champion: str):
    async with aiosqlite.connect('database.db') as db:
        await db.execute(
            "DELETE FROM builds WHERE champion = ? AND author = ?",
            (champion.lower(), str(ctx.author))
        )
        await db.commit()
        await ctx.send(f"Deleted builds for {champion.title()}")


if __name__ == '__main__':
    if not token:
        raise Exception("No token provided")
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)
